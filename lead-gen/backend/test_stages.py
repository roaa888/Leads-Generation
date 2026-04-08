"""
Stage-by-stage pipeline tests.

Run: `python test_stages.py`

These tests are designed to be run manually in WSL with valid API keys.
"""

import asyncio
import json
import time

from crewai import Crew, Process, Task

from agents.agents import (
    create_contact_agent,
    create_enrichment_agent,
    create_search_agent,
    create_validator_agent,
)


def _print_stage(title: str) -> None:
    print("\n" + "=" * 18)
    print(title)
    print("=" * 18)


def stage_1_search() -> str:
    _print_stage("STAGE 1 — Search Agent")
    agent = create_search_agent()
    task = Task(
        description='Find 2 SaaS companies in United States. Return JSON: [{"company_name","website"}]',
        expected_output="JSON array with 2 companies",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
    result = crew.kickoff()
    print("RESULT:", result)
    return str(result)


def stage_2_enrich() -> str:
    _print_stage("STAGE 2 — Enrichment Agent")
    companies = '[{"company_name":"Stripe","website":"https://stripe.com"}]'
    agent = create_enrichment_agent()
    task = Task(
        description=f"Scrape these companies: {companies}. Extract phone, location, description. Return JSON array.",
        expected_output="JSON array with enriched company data",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
    result = crew.kickoff()
    print("RESULT:", result)
    return str(result)


def stage_3_contact() -> str:
    _print_stage("STAGE 3 — Contact Agent")
    companies = (
        '[{"company_name":"Stripe","website":"https://stripe.com","phone":"N/A","location":"N/A","company_size":"N/A","description":"Payment processing"}]'
    )
    agent = create_contact_agent()
    task = Task(
        description=f"Find CEO contact for these companies: {companies}. Use Hunter.io first. Return JSON array with contact_name, title, email added.",
        expected_output="JSON array with contact details",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
    result = crew.kickoff()
    print("RESULT:", result)
    return str(result)


def stage_4_validator() -> str:
    _print_stage("STAGE 4 — Validator Agent")
    messy_data = [
        {
            "company_name": "Stripe",
            "contact_name": "John Smith",
            "title": "CEO",
            "email": "john@stripe.com",
            "phone": "N/A",
            "location": "N/A",
            "company_size": "N/A",
            "website": "https://stripe.com",
        },
        {
            "company_name": "Stripe",
            "contact_name": "John Smith",
            "title": "CEO",
            "email": "john@stripe.com",
            "phone": "N/A",
            "location": "N/A",
            "company_size": "N/A",
            "website": "https://stripe.com",
        },
        {
            "company_name": "Bad Corp",
            "contact_name": "N/A",
            "title": "N/A",
            "email": "not-valid",
            "phone": "N/A",
            "location": "N/A",
            "company_size": "N/A",
            "website": "N/A",
        },
    ]
    agent = create_validator_agent()
    task = Task(
        description=f"Clean this data: {messy_data}. Remove duplicates. Validate emails. Assign status: Verified/New/Missing Email. Return clean JSON array.",
        expected_output="Clean JSON array with status field",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)
    result = crew.kickoff()
    print("RESULT:", result)
    return str(result)


def main() -> None:
    stage_1_search()
    time.sleep(15)
    stage_2_enrich()
    time.sleep(15)
    stage_3_contact()
    time.sleep(15)
    stage_4_validator()


if __name__ == "__main__":
    main()

