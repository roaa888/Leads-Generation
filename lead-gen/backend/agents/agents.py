import os
import requests # Added for hunter_find_email tool
from bootstrap import configure_runtime

configure_runtime()

from crewai import Agent
from crewai.tools import tool # Import tool from crewai.tools
from crewai import LLM
from tools.search_tools import duckduckgo_company_search
from tools.scraping_tools import website_enrichment_scraper
from dotenv import load_dotenv

load_dotenv()

class LeadGenAgents:
    def __init__(self):
        self.llm = LLM(
            model="groq/llama-3.1-8b-instant",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.1,
        )
        # self.llm = ChatGroq(
        #     model="llama-3.3-70b-versatile",
        #     api_key=os.getenv("GROQ_API_KEY"),
        #temperature=0.1,
        #)

    def search_agent(self):
        return Agent(
            role="Company Search Specialist",
            goal="Find companies matching industry, location, size, and keywords. Return company names and website URLs.",
            backstory=(
                "Expert B2B researcher.\n"
                "- You MUST ONLY use the 'duckduckgo_company_search' tool.\n"
                "- Never fabricate data.\n"
                "- Output MUST be valid JSON only (no markdown, no commentary)."
            ),
            tools=[duckduckgo_company_search],
            verbose=True,
            allow_delegation=False,
            max_iter=5,
            llm=self.llm
        )

    def enrichment_agent(self):
        return Agent(
            role="Company Enrichment Specialist",
            goal="Visit each company website and extract phone, location, company size, and description.",
            backstory=(
                "Expert web scraper.\n"
                "- You MUST ONLY use the 'website_enrichment_scraper' tool.\n"
                "- If a field is missing, return \"N/A\".\n"
                "- Output MUST be valid JSON only (no markdown, no commentary)."
            ),
            tools=[website_enrichment_scraper],
            verbose=True,
            allow_delegation=False,
            max_iter=5,
            llm=self.llm
        )

    def contact_agent(self):
        # Define the Hunter.io tool function directly here
        @tool("hunter_find_email") # Use @tool decorator from crewai.tools (lowercase)
        def hunter_find_email_internal(domain: str):
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

        return Agent(
            role="Contact Discovery Specialist",
            goal="Find decision-makers at companies. Uses Hunter.io to find email addresses for a given company domain.",
            backstory=(
                "Expert at finding the right person at a company.\n"
                "- You MUST ONLY use the 'hunter_find_email' tool.\n"
                "- Output MUST be valid JSON only (no markdown, no commentary)."
            ),
            tools=[hunter_find_email_internal], # Use the internally defined tool
            verbose=True,
            allow_delegation=False,
            max_iter=5,
            llm=self.llm
        )

    def validator_agent(self):
        return Agent(
            role="Data Validation Specialist",
            goal="Clean, validate, deduplicate all data. Assign status (Verified, New, Missing Email) to each lead.",
            backstory=(
                "Data quality expert.\n"
                "- Remove duplicates.\n"
                "- Fill missing fields with \"N/A\".\n"
                "- Assign status (Verified, New, Missing Email).\n"
                "- Output MUST be valid JSON only (no markdown, no commentary)."
            ),
            tools=[],
            verbose=True,
            allow_delegation=False,
            max_iter=5,
            llm=self.llm
        )

    def export_agent(self):
        return Agent(
            role="Data Export Specialist",
            goal="Structure all data into a clean CSV format with 8 columns: Company Name, Contact Name, Title, Email, Phone, Location, Company Size, Status.",
            backstory="Expert at data formatting. Ensures every row has all 8 fields properly formatted.",
            tools=[],
            verbose=True,
            allow_delegation=False,
            max_iter=5,
            llm=self.llm
        )
