import asyncio
import io
import json
import ast
import pandas as pd
from bootstrap import configure_runtime
from excel_export import build_excel

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
from urllib.parse import urlparse

from tools.search_tools import run_company_search
from tools.scraping_tools import run_website_enrichment
from tools.contact_tools import hunter_domain_search, find_linkedin_profile, find_company_linkedin

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


def _lead_status(email: str, contact_name: str, title: str) -> str:
    if email != "N/A" and contact_name != "N/A" and title != "N/A":
        return "Verified"
    if email != "N/A":
        return "New"
    return "Missing Email"


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

        company      = _clean_str(item.get("Company Name") or item.get("company_name") or item.get("company"))
        website      = _clean_str(item.get("website") or item.get("Website"))
        contact      = _clean_str(item.get("Contact Name") or item.get("contact_name") or item.get("name"))
        title        = _clean_str(item.get("Title") or item.get("title") or item.get("position"))
        email        = _clean_str(item.get("Email") or item.get("email"))
        phone        = _clean_str(item.get("Phone") or item.get("phone"))
        location     = _clean_str(item.get("Location") or item.get("location"))
        company_size = _clean_str(item.get("Company Size") or item.get("company_size"))
        linkedin     = _clean_str(item.get("LinkedIn") or item.get("linkedin"))

        email_valid = email != "N/A" and is_email(email, check_dns=False)
        if not email_valid:
            email = "N/A"

        status = _lead_status(email, contact, title)

        dedupe_key = (company.lower(), email.lower())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        cleaned.append(
            {
                "Company Name": company,
                "Website":      website,
                "Contact Name": contact,
                "Title":        title,
                "Email":        email,
                "Phone":        phone,
                "Location":     location,
                "Company Size": company_size,
                "LinkedIn":     linkedin,
                "Status":       status,
            }
        )

        if len(cleaned) >= limit:
            break

    return cleaned


def _domain_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        host = host.strip().lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""



def _parse_enrichment(text: str) -> dict:
    """
    Parse the string returned by website_enrichment_scraper().
    It's intentionally forgiving.
    """
    out = {"title": "N/A", "description": "N/A", "phones": [], "emails": []}
    if not text:
        return out
    for line in str(text).splitlines():
        if line.lower().startswith("title:"):
            out["title"] = line.split(":", 1)[1].strip() or "N/A"
        elif line.lower().startswith("description:"):
            out["description"] = line.split(":", 1)[1].strip() or "N/A"
        elif line.lower().startswith("phones:"):
            raw = line.split(":", 1)[1].strip()
            try:
                out["phones"] = ast.literal_eval(raw)
            except Exception:
                out["phones"] = []
        elif line.lower().startswith("emails:"):
            raw = line.split(":", 1)[1].strip()
            try:
                out["emails"] = ast.literal_eval(raw)
            except Exception:
                out["emails"] = []
    return out


async def _deterministic_pipeline(criteria: SearchCriteria, *, websocket) -> list[dict] | None:
    """
    Non-LLM pipeline: uses tools + Hunter directly. This avoids LLM formatting issues and reduces Groq usage.
    Returns list of lead dicts in the final CSV schema.
    """
    async def send(step: int, label: str, data: dict | None = None):
        try:
            payload = {"step": step, "label": label}
            if data:
                payload.update(data)
            await websocket.send_json(payload)
        except Exception:
            pass

    await send(1, "Searching for companies...")
    industry  = (criteria.industry or "").strip().replace("/", " ").replace("\\", " ")
    location  = (criteria.location or "").strip()
    keywords  = (criteria.keywords or "").strip()

    # Queries ordered from most-specific to broadest.
    # Exclusions appended to push search engines toward company homepages.
    _excl = "-site:crunchbase.com -site:g2.com -site:clutch.co -site:f6s.com -blog -list -ranking"
    queries = [q.strip() for q in [
        f"{industry} company {location} official website {_excl}",
        f"{industry} software company {location} {_excl}",
        f"{keywords} company {location} {_excl}" if keywords else "",
        f"{industry} startup {location}",
        f"{industry} companies in {location}",
        f"top {industry} companies",
    ] if q.strip()]

    companies: list[dict] = []
    used_query = ""
    for q in queries:
        used_query = q
        try:
            # run_company_search uses time.sleep for DDG retries — run off the event loop
            raw = await asyncio.to_thread(run_company_search, q)
            companies = json.loads(raw) if raw else []
        except Exception:
            companies = []
        if companies:
            break

    if not companies:
        await send(
            0,
            "No companies found from search providers.",
            {"status": "error", "code": "SEARCH_EMPTY",
             "details": f"Queries tried: {queries}. Last used: {used_query}"},
        )
        return None

    await send(2, "Enriching company data...")

    async def _enrich_one(c: dict) -> dict | None:
        website      = _clean_str(c.get("website"))
        company_name = _clean_str(c.get("company_name"))
        if website == "N/A":
            return None
        enrich_text = await asyncio.to_thread(run_website_enrichment, website)
        parsed = _parse_enrichment(enrich_text)
        phone  = parsed["phones"][0] if parsed["phones"] else "N/A"
        return {
            "Company Name": company_name,
            "Website":      website,
            "Phone":        phone or "N/A",
            "Location":     _clean_str(criteria.location),
            "Company Size": _clean_str(criteria.company_size),
            "Description":  _clean_str(parsed.get("description")),
        }

    enriched = [r for r in await asyncio.gather(*[_enrich_one(c) for c in companies]) if r]

    if not enriched:
        await send(0, "Enrichment produced no usable companies.", {"status": "error", "code": "ENRICH_EMPTY"})
        return None

    await send(3, "Finding contacts & emails...")

    async def _contact_one(item: dict) -> dict:
        domain       = _domain_from_url(item.get("Website", ""))
        company_name = _clean_str(item.get("Company Name"))
        contacts     = await asyncio.to_thread(hunter_domain_search, domain, limit=3)
        best         = contacts[0] if contacts else {}

        email = _clean_str(best.get("email"))
        if email != "N/A" and not is_email(email, check_dns=False):
            email = "N/A"
        contact_name = _clean_str(best.get("contact_name"))
        title        = _clean_str(best.get("title"))

        # LinkedIn: use Hunter's field first; fall back to DDG search
        linkedin = (best.get("linkedin") or "").strip()
        if not linkedin and contact_name != "N/A":
            linkedin = await asyncio.to_thread(find_linkedin_profile, contact_name, company_name)

        return {
            "Company Name": company_name,
            "Contact Name": contact_name,
            "Title":        title,
            "Email":        email,
            "Phone":        _clean_str(item.get("Phone")),
            "Location":     _clean_str(item.get("Location")),
            "Company Size": _clean_str(item.get("Company Size")),
            "LinkedIn":     linkedin or "N/A",
            "Status":       _lead_status(email, contact_name, title),
        }

    leads = await asyncio.gather(*[_contact_one(item) for item in enriched])
    leads = list(leads)[: criteria.num_leads]

    if not leads:
        await send(0, "No leads could be generated.", {"status": "error", "code": "LEADS_EMPTY"})
        return None

    await send(4, "Validating & cleaning data...")
    leads = validate_and_clean_leads(leads, limit=criteria.num_leads)

    await send(5, "Building Excel export...")
    return leads


async def _kickoff_with_retry(crew: Crew, *, step_label: str, retries: int = 3) -> object:
    """
    Crew.kickoff() is synchronous and can fail transiently (TPM limits, network blips, empty LLM output).
    Retry a few times with backoff and treat empty output as an error.
    """
    delay_s = 2.0
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            result = await asyncio.to_thread(crew.kickoff)
            if result is None or str(result).strip() == "":
                raise ValueError("Invalid response from LLM call - None or empty.")
            return result
        except litellm.RateLimitError as e:
            last_exc = e
        except (litellm.InternalServerError, litellm.Timeout, litellm.APIConnectionError) as e:
            last_exc = e
        except Exception as e:
            last_exc = e

        if attempt < retries:
            await asyncio.sleep(delay_s)
            delay_s = min(delay_s * 2, 15)

    raise RuntimeError(f"{step_label} failed after retries: {last_exc}")


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
            # Prefer deterministic tool-driven pipeline to avoid LLM tool hallucinations / rate limits.
            deterministic = await _deterministic_pipeline(self.criteria, websocket=self.websocket)
            if deterministic is not None:
                leads_data = deterministic
                df = pd.DataFrame(leads_data)
                expected_cols = ["Company Name", "Contact Name", "Title", "Email", "Phone", "Location", "Company Size", "LinkedIn", "Status"]
                for col in expected_cols:
                    if col not in df.columns:
                        df[col] = "N/A"
                df = df[expected_cols]

                total    = len(df)
                verified = len(df[df["Status"] == "Verified"])
                missing  = len(df[df["Status"] == "Missing Email"])
                preview  = df.head(10).to_dict(orient="records")

                excel_bytes = build_excel(df.to_dict(orient="records"),
                                          self.criteria.model_dump())

                await self.send_status(6, "Completed!", {
                    "total_leads": total,
                    "verified": verified,
                    "missing_email": missing,
                    "preview": preview,
                })
                self.last_success = {
                    "total_leads": total,
                    "verified": verified,
                    "missing_email": missing,
                    "preview": preview,
                }
                return excel_bytes

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
                verbose=False,
                process=Process.sequential,
                llm=self.agents.llm
            )
            search_result = await _kickoff_with_retry(search_crew, step_label="Search")

            # STEP 2: Enrichment
            await self.send_status(2, "Enriching company data...")
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
                verbose=False,
                llm=self.agents.llm
            )
            enriched_result = await _kickoff_with_retry(enrichment_crew, step_label="Enrichment")

            # STEP 3: Contact Discovery
            await self.send_status(3, "Finding contacts & emails...")
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
                verbose=False,
                llm=self.agents.llm
            )
            contact_result = await _kickoff_with_retry(contact_crew, step_label="Contact discovery")

            # STEP 4: Validation
            await self.send_status(4, "Validating & cleaning data...")
            validated_output = validate_and_clean_leads(contact_result, limit=self.criteria.num_leads)

            # STEP 5: Export
            await self.send_status(5, "Building Excel export...")
            if isinstance(validated_output, list):
                leads_data = validated_output
            else:
                try:
                    leads_data = json.loads(
                        str(validated_output).strip().replace('```json', '').replace('```', '')
                    )
                except Exception:
                    leads_data = []

            df = pd.DataFrame(leads_data)
            expected_cols = ["Company Name", "Contact Name", "Title", "Email", "Phone", "Location", "Company Size", "LinkedIn", "Status"]
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = "N/A"
            df = df[expected_cols]

            total    = len(df)
            verified = len(df[df["Status"] == "Verified"])
            missing  = len(df[df["Status"] == "Missing Email"])
            preview  = df.head(10).to_dict(orient="records")

            excel_bytes = build_excel(df.to_dict(orient="records"),
                                      self.criteria.model_dump())

            await self.send_status(6, "Completed!", {
                "total_leads": total,
                "verified": verified,
                "missing_email": missing,
                "preview": preview,
            })
            self.last_success = {
                "total_leads": total,
                "verified": verified,
                "missing_email": missing,
                "preview": preview,
            }
            return excel_bytes

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
                {"details": error_message or "No additional details."},
                status="error",
                code="UNEXPECTED_ERROR",
            )
            return None
