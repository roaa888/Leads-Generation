import asyncio
import io
import json
import pandas as pd
from bootstrap import configure_runtime

configure_runtime()

from crewai import Crew, Task, Process
from pyisemail import is_email
from agents.agents import LeadGenAgents
from models import SearchCriteria, LeadStatus
import os
import requests
from crewai.tools import tool
import litellm
from dotenv import load_dotenv

load_dotenv()

# -----------------------
# Local validation helpers
# -----------------------

def _extract_json_candidate(text: str) -> str | None:
    s = (text or "").strip()
    if not s:
        return None

    if "```" in s:
        parts = s.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            if stripped.startswith("[") or stripped.startswith("{"):
                return stripped

    start = s.find("[")
    end = s.rfind("]")
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1]

    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1]

    return None


def _parse_json_output(text: object) -> object:
    candidate = _extract_json_candidate(str(text))
    if not candidate:
        raise ValueError("No JSON found in output")
    return json.loads(candidate)


def _clean_str(value: object) -> str:
    if value is None:
        return "N/A"
    s = str(value).strip()
    return s if s else "N/A"


def validate_and_clean_leads(raw: object, *, limit: int) -> list[dict]:
    """
    Deterministic validation layer to avoid brittle LLM-only output and rate limits.
    Accepts either a JSON string/obj with list[dict] or any text containing JSON.
    """
    try:
        data = raw if isinstance(raw, (list, dict)) else _parse_json_output(raw)
    except Exception:
        return []

    if isinstance(data, dict):
        # Some agents may return { "leads": [...] }
        if isinstance(data.get("leads"), list):
            data = data["leads"]
        else:
            data = [data]

    if not isinstance(data, list):
        return []

    cleaned: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in data:
        if not isinstance(item, dict):
            continue

        company = _clean_str(item.get("Company Name") or item.get("company_name") or item.get("company"))
        website = _clean_str(item.get("website") or item.get("Website"))
        contact = _clean_str(item.get("Contact Name") or item.get("contact_name") or item.get("name"))
        title = _clean_str(item.get("Title") or item.get("title") or item.get("position"))
        email = _clean_str(item.get("Email") or item.get("email"))
        phone = _clean_str(item.get("Phone") or item.get("phone"))
        location = _clean_str(item.get("Location") or item.get("location"))
        company_size = _clean_str(item.get("Company Size") or item.get("company_size"))

        email_valid = email != "N/A" and is_email(email, check_dns=False)
        if not email_valid:
            email = "N/A"

        if email != "N/A" and contact != "N/A" and title != "N/A":
            status = "Verified"
        elif email != "N/A":
            status = "New"
        else:
            status = "Missing Email"

        dedupe_key = (company.lower(), email.lower())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        cleaned.append(
            {
                "Company Name": company,
                "Website": website,
                "Contact Name": contact,
                "Title": title,
                "Email": email,
                "Phone": phone,
                "Location": location,
                "Company Size": company_size,
                "Status": status,
            }
        )

        if len(cleaned) >= limit:
            break

    return cleaned


# Define the Hunter.io tool function directly here
@tool("hunter_find_email")
def hunter_find_email(domain: str):
    """Finds emails for a given company domain. Input must be a single string (e.g., 'stripe.com')."""
    api_key = os.getenv("HUNTER_API_KEY")
    if not api_key:
        return "Hunter API key not found in environment."
        
    url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={api_key}&limit=5"
    
    response = requests.get(url)
    if response.status_code != 200:
        return f"Error from Hunter: {response.status_code}"
        
    data = response.json().get('data', {})
    emails = data.get('emails', [])
    
    if not emails:
        return "No emails found on Hunter."
        
    formatted_results = []
    for e in emails:
        first = e.get('first_name', 'N/A')
        last = e.get('last_name', 'N/A')
        title = e.get('position', 'N/A')
        email = e.get('value', 'N/A')
        confidence = e.get('confidence', 0)
        formatted_results.append(f"Name: {first} {last} | Title: {title} | Email: {email} | Confidence: {confidence}%")
        
    return "\n".join(formatted_results)

class LeadOrchestrator:
    def __init__(self, criteria: SearchCriteria, websocket):
        self.criteria = criteria
        self.websocket = websocket
        self.agents = LeadGenAgents()
        self.last_error: dict | None = None
        self.last_success: dict | None = None

    async def send_status(self, step, label, data=None, *, status: str | None = None, code: str | None = None):
        message = {"step": step, "label": label}
        if status:
            message["status"] = status
        if code:
            message["code"] = code
        if data:
            message.update(data)
        if step == 0 or status == "error":
            details = None
            if isinstance(data, dict):
                details = data.get("details")
            self.last_error = {
                "status": "error",
                "code": code or "PIPELINE_ERROR",
                "message": label,
                **({"details": details} if details else {}),
            }
        try:
            await self.websocket.send_json(message)
        except Exception:
            # Client disconnected or network error; avoid crashing the pipeline.
            pass

    async def run_pipeline(self):
        try:
            # STEP 1: Search
            await self.send_status(1, "Searching for companies...")
            await asyncio.sleep(15)
            search_agent = self.agents.search_agent()
            search_task = Task(
                description=(
                    f"Find {self.criteria.num_leads * 2} companies. "
                    f"The search query should be based on: industry='{self.criteria.industry}', "
                    f"location='{self.criteria.location}', lead_type='{self.criteria.lead_type}', "
                    f"company_size='{self.criteria.company_size}', and keywords='{self.criteria.keywords}'. "
                    "Return ONLY valid JSON (no markdown, no commentary): "
                    "[{'company_name': '...', 'website': 'https://...'}, ...]"
                ),
                expected_output="A JSON array of company names and websites.",
                agent=search_agent
            )
            search_crew = Crew(
                agents=[search_agent], 
                tasks=[search_task], 
                verbose=True,
                process=Process.sequential,
                llm=self.agents.llm
            )
            search_result = search_crew.kickoff()
            await asyncio.sleep(15)

            # STEP 2: Enrichment
            await self.send_status(2, "Enriching company data...")
            await asyncio.sleep(15)
            enrichment_agent = self.agents.enrichment_agent()
            enrichment_task = Task(
                description=f"Given this list of companies: {search_result}. "
                            f"For each company, scrape their website to find phone, location, size, and description. "
                            "Return ONLY valid JSON (no markdown, no commentary): "
                            "[{'company_name':'...','website':'...','phone':'...','location':'...','company_size':'...','description':'...'}, ...]",
                expected_output="A JSON array of enriched company data.",
                agent=enrichment_agent
            )
            enrichment_crew = Crew(
                agents=[enrichment_agent], 
                tasks=[enrichment_task], 
                verbose=True,
                llm=self.agents.llm
            )
            enriched_result = enrichment_crew.kickoff()
            await asyncio.sleep(15)

            # STEP 3: Contact Discovery
            await self.send_status(3, "Finding contacts & emails...")
            await asyncio.sleep(15)
            contact_agent = self.agents.contact_agent()
            contact_task = Task(
                description=f"Given these enriched companies: {enriched_result}. "
                            f"Find a contact matching the role '{self.criteria.target_role}' for each company. "
                            "Use the hunter_find_email tool with each company's domain. "
                            "IMPORTANT: You MUST preserve ALL enriched fields for every company AND add the contact fields. "
                            "Return ONLY a valid JSON array (no markdown, no commentary) using exactly these keys: "
                            "[{'company_name':'...','website':'...','phone':'...','location':'...','company_size':'...','contact_name':'...','title':'...','email':'...'}, ...]",
                expected_output="A JSON array of companies with contact person details and emails.",
                agent=contact_agent
            )
            contact_crew = Crew(
                agents=[contact_agent], 
                tasks=[contact_task], 
                verbose=True,
                llm=self.agents.llm
            )
            contact_result = contact_crew.kickoff()
            await asyncio.sleep(15)

            # STEP 4: Validation
            await self.send_status(4, "Validating & cleaning data...")
            await asyncio.sleep(15)
            # Use deterministic local validation to avoid LLM rate limits and format drift.
            validated_output = validate_and_clean_leads(contact_result, limit=self.criteria.num_leads)
            await asyncio.sleep(15)

            # STEP 5: Export
            await self.send_status(5, "Building CSV export...")
            await asyncio.sleep(15)
            # Attempt to parse the JSON output from validation
            try:
                # Cleaning the string if it contains markdown code blocks
                if isinstance(validated_output, list):
                    leads_data = validated_output
                else:
                    clean_json = str(validated_output).strip().replace('```json', '').replace('```', '')
                    leads_data = json.loads(clean_json)
            except:
                # Fallback if LLM didn't return perfect JSON
                leads_data = []

            df = pd.DataFrame(leads_data)
            expected_cols = ["Company Name", "Contact Name", "Title", "Email", "Phone", "Location", "Company Size", "Status"]
            
            # Ensure columns exist and are ordered
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = "N/A"
            df = df[expected_cols]

            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            
            # Stats for completion message
            total = len(df)
            verified = len(df[df['Status'] == 'Verified'])
            missing = len(df[df['Status'] == 'Missing Email'])
            
            await self.send_status(6, "Completed!", {
                "total_leads": total,
                "verified": verified,
                "missing_email": missing,
                "preview": df.head(1).to_dict(orient='records')
            })
            self.last_success = {
                "total_leads": total,
                "verified": verified,
                "missing_email": missing,
                "preview": df.head(10).to_dict(orient='records'),
            }
            await asyncio.sleep(15)

            return csv_buffer.getvalue()

        except litellm.RateLimitError as e:
            error_message = f"Groq token limit reached. Your Groq organization exceeded its tokens-per-day limit."
            print(f"Pipeline Error: {error_message}")
            await self.send_status(
                0,
                error_message,
                {"details": str(e)},
                status="error",
                code="GROQ_RATE_LIMIT",
            )
            return None
        except litellm.AuthenticationError as e:
            error_message = f"API Authentication Error: {e}. Please check your API keys."
            print(f"Pipeline Error: {error_message}")
            await self.send_status(
                0,
                "Authentication failed. One of your API keys is missing/invalid.",
                {"details": str(e)},
                status="error",
                code="AUTH_ERROR",
            )
            return None
        except litellm.BadRequestError as e:
            error_message = f"API Request Error: {e}. Please check your prompt or model configuration."
            print(f"Pipeline Error: {error_message}")
            await self.send_status(
                0,
                "Bad request to the LLM provider (model/prompt/config).",
                {"details": str(e)},
                status="error",
                code="BAD_REQUEST",
            )
            return None
        except Exception as e:
            error_message = f"An unexpected error occurred: {str(e)}"
            print(f"Pipeline Error: {error_message}")
            await self.send_status(
                0,
                "Unexpected pipeline error.",
                {"details": error_message},
                status="error",
                code="UNEXPECTED_ERROR",
            )
            return None
