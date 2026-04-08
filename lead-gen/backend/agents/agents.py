import os
from bootstrap import configure_runtime

configure_runtime()

from crewai import Agent
from crewai.tools import tool
from crewai import LLM
from tools.search_tools import duckduckgo_company_search, brave_search
from tools.scraping_tools import website_enrichment_scraper
from tools.contact_tools import hunter_domain_search
from dotenv import load_dotenv

load_dotenv()

class LeadGenAgents:
    def __init__(self):
        self.llm = LLM(
            model="groq/llama-3.3-70b-versatile",
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.1,
            max_tokens=512,
        )

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
            tools=[duckduckgo_company_search, brave_search],
            verbose=False,
            allow_delegation=False,
            max_iter=2,
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
            verbose=False,
            allow_delegation=False,
            max_iter=2,
            llm=self.llm
        )

    def contact_agent(self):
        @tool("hunter_find_email")
        def hunter_find_email_internal(domain: str):
            """Finds emails for a given company domain. Input must be a single string (e.g., 'stripe.com')."""
            contacts = hunter_domain_search(domain, limit=5)
            if not contacts:
                return "No emails found on Hunter."
            return "\n".join(
                f"Name: {c['contact_name']} | Title: {c['title']} | Email: {c['email']} | Confidence: {c['confidence']}%"
                for c in contacts
            )

        return Agent(
            role="Contact Discovery Specialist",
            goal="Find decision-makers at companies. Uses Hunter.io to find email addresses for a given company domain.",
            backstory=(
                "Expert at finding the right person at a company.\n"
                "- You MUST ONLY use the 'hunter_find_email' tool.\n"
                "- Output MUST be valid JSON only (no markdown, no commentary)."
            ),
            tools=[hunter_find_email_internal],
            verbose=False,
            allow_delegation=False,
            max_iter=2,
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
            verbose=False,
            allow_delegation=False,
            max_iter=2,
            llm=self.llm
        )

    def export_agent(self):
        return Agent(
            role="Data Export Specialist",
            goal="Structure all data into a clean CSV format with 8 columns: Company Name, Contact Name, Title, Email, Phone, Location, Company Size, Status.",
            backstory="Expert at data formatting. Ensures every row has all 8 fields properly formatted.",
            tools=[],
            verbose=False,
            allow_delegation=False,
            max_iter=2,
            llm=self.llm
        )


def create_search_agent() -> Agent:
    return LeadGenAgents().search_agent()


def create_enrichment_agent() -> Agent:
    return LeadGenAgents().enrichment_agent()


def create_contact_agent() -> Agent:
    return LeadGenAgents().contact_agent()


def create_validator_agent() -> Agent:
    return LeadGenAgents().validator_agent()


def create_export_agent() -> Agent:
    return LeadGenAgents().export_agent()
