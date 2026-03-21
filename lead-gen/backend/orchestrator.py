import io
import json
import pandas as pd
from crewai import Crew, Task, Process
from pyisemail import is_email
from agents.agents import LeadGenAgents
from models import SearchCriteria, LeadStatus

class LeadOrchestrator:
    def __init__(self, criteria: SearchCriteria, websocket):
        self.criteria = criteria
        self.websocket = websocket
        self.agents = LeadGenAgents()

    async def send_status(self, step, label, data=None):
        message = {"step": step, "label": label}
        if data:
            message.update(data)
        await self.websocket.send_json(message)

    async def run_pipeline(self):
        try:
            # STEP 1: Search
            await self.send_status(1, "Searching for companies...")
            search_task = Task(
                description=f"Find {self.criteria.num_leads * 2} companies in {self.criteria.industry} in {self.criteria.location}. "
                            f"Lead type: {self.criteria.lead_type}. Company size: {self.criteria.company_size}. "
                            f"Keywords: {self.criteria.keywords}. Return a JSON array of objects: [{{'company_name': '...', 'website': '...'}}]",
                expected_output="A JSON array of company names and websites.",
                agent=self.agents.search_agent()
            )
            search_crew = Crew(agents=[self.agents.search_agent()], tasks=[search_task], process=Process.sequential)
            search_result = search_crew.kickoff()

            # STEP 2: Enrichment
            await self.send_status(2, "Enriching company data...")
            enrichment_task = Task(
                description=f"Given this list of companies: {search_result}. "
                            f"For each company, scrape their website to find phone, location, size, and description. "
                            f"Return a JSON array: [{{'company_name': '...', 'website': '...', 'phone': '...', 'location': '...', 'company_size': '...', 'description': '...'}}]",
                expected_output="A JSON array of enriched company data.",
                agent=self.agents.enrichment_agent()
            )
            enrichment_crew = Crew(agents=[self.agents.enrichment_agent()], tasks=[enrichment_task], process=Process.sequential)
            enriched_result = enrichment_crew.kickoff()

            # STEP 3: Contact Discovery
            await self.send_status(3, "Finding contacts & emails...")
            contact_task = Task(
                description=f"Given these enriched companies: {enriched_result}. "
                            f"Find a contact matching the role '{self.criteria.target_role}' for each. "
                            f"Use Hunter.io and website scraping. Return a JSON array with all company and contact fields combined.",
                expected_output="A JSON array of companies with contact person details and emails.",
                agent=self.agents.contact_agent()
            )
            contact_crew = Crew(agents=[self.agents.contact_agent()], tasks=[contact_task], process=Process.sequential)
            contact_result = contact_crew.kickoff()

            # STEP 4: Validation
            await self.send_status(4, "Validating & cleaning data...")
            validation_task = Task(
                description=f"Clean and validate this data: {contact_result}. "
                            f"Remove duplicates, validate emails using LLM reasoning (and logic: Verified if email+name+title exists, New if only email, Missing Email otherwise). "
                            f"Keep exactly {self.criteria.num_leads} leads. Return a clean JSON array.",
                expected_output="A clean JSON array of validated leads.",
                agent=self.agents.validator_agent()
            )
            validation_crew = Crew(agents=[self.agents.validator_agent()], tasks=[validation_task], process=Process.sequential)
            validated_output = validation_crew.kickoff()

            # STEP 5: Export
            await self.send_status(5, "Building CSV export...")
            # Attempt to parse the JSON output from validation
            try:
                # Cleaning the string if it contains markdown code blocks
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

            return csv_buffer.getvalue()

        except Exception as e:
            print(f"Pipeline Error: {str(e)}")
            await self.send_status(0, f"An error occurred: {str(e)}")
            return None
