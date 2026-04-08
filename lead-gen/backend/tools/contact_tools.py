import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()


def hunter_domain_search(domain: str, *, limit: int = 3) -> list[dict]:
    """
    Query Hunter.io domain-search API.
    Returns contacts with: contact_name, title, email, confidence, linkedin.
    """
    api_key = os.getenv("HUNTER_API_KEY")
    if not api_key or not domain:
        return []
    try:
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": api_key, "limit": limit},
            timeout=20,
        )
        if resp.status_code != 200:
            return []
        data   = resp.json().get("data", {})
        emails = data.get("emails") or []
        return [
            {
                "contact_name": " ".join(
                    p for p in [e.get("first_name"), e.get("last_name")] if p
                ).strip() or "N/A",
                "title":      (e.get("position") or "N/A").strip() or "N/A",
                "email":      (e.get("value")    or "N/A").strip() or "N/A",
                "confidence": e.get("confidence", 0),
                "linkedin":   (e.get("linkedin")  or "").strip(),
            }
            for e in emails
        ]
    except Exception:
        return []


def find_linkedin_profile(contact_name: str, company_name: str) -> str:
    """
    Search DuckDuckGo for a person's LinkedIn profile URL.
    Returns the URL string or '' if not found.
    Only called when Hunter didn't supply a linkedin field.
    """
    if not contact_name or contact_name == "N/A":
        return ""
    try:
        from ddgs import DDGS
        query = f'"{contact_name}" "{company_name}" site:linkedin.com/in'
        for attempt in range(2):
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=3))
                for r in results:
                    href = (r.get("href") or "").strip()
                    if "linkedin.com/in/" in href:
                        return href.split("?")[0]  # strip tracking params
                break
            except Exception:
                pass
            time.sleep(3)
    except Exception:
        pass
    return ""


def find_company_linkedin(company_name: str) -> str:
    """
    Search for the company's LinkedIn page URL.
    Returns the URL string or ''.
    """
    if not company_name or company_name == "N/A":
        return ""
    try:
        from ddgs import DDGS
        query = f'"{company_name}" site:linkedin.com/company'
        for attempt in range(2):
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=3))
                for r in results:
                    href = (r.get("href") or "").strip()
                    if "linkedin.com/company/" in href:
                        return href.split("?")[0]
                break
            except Exception:
                pass
            time.sleep(3)
    except Exception:
        pass
    return ""
