import os
from crewai import Agent
from langchain_groq import ChatGroq
from tools.search_tools import duckduckgo_company_search, serper_fallback_search
from tools.scraping_tools import website_enrichment_scraper, contact_page_scraper
from tools.contact_tools import hunter_find_email, extract_domain
from dotenv import load_dotenv

load_dotenv()

class LeadGenAgents:
    def __init__(self):
        self.llm = ChatGroq(
            model="llama3-70b-8192",
            temperature=0.1,
            api_key=os.getenv("GROQ_API_KEY")
        )

    def search_agent(self):
        return Agent(
            role="Company Search Specialist",
            goal="Find companies matching industry, location, size, and keywords. Return company names and website URLs.",
            backstory="Expert B2B researcher. Uses DuckDuckGo first, falls back to Serper if results are insufficient. Never fabricates data.",
            tools=[duckduckgo_company_search, serper_fallback_search],
            verbose=True,
            allow_delegation=False,
            max_iter=5,
            llm=self.llm
        )

    def enrichment_agent(self):
        return Agent(
            role="Company Enrichment Specialist",
            goal="Visit each company website and extract phone, location, company size, and description.",
            backstory="Expert web scraper. Uses BeautifulSoup for static pages. Returns N/A if not found.",
            tools=[website_enrichment_scraper],
            verbose=True,
            allow_delegation=False,
            max_iter=5,
            llm=self.llm
        )

    def contact_agent(self):
        return Agent(
            role="Contact Discovery Specialist",
            goal="Find decision-makers matching the target role at each company. Extract name, title, and personal email.",
            backstory="Expert at finding the right person at a company. Uses Hunter.io first, falls back to contact page scraping. Prefers personal emails over generic ones. Never fabricates.",
            tools=[hunter_find_email, extract_domain, contact_page_scraper],
            verbose=True,
            allow_delegation=False,
            max_iter=5,
            llm=self.llm
        )

    def validator_agent(self):
        return Agent(
            role="Data Validation Specialist",
            goal="Clean, validate, deduplicate all data. Assign status (Verified, New, Missing Email) to each lead.",
            backstory="Data quality expert. Validates emails, removes duplicates, fills missing fields with N/A, assigns correct status.",
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
