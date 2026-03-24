import json

from duckduckgo_search import DDGS
from crewai.tools import tool
from dotenv import load_dotenv
import os
import requests

load_dotenv()

def _serper_search(query: str, *, max_results: int = 10) -> list[dict]:
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return []

    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": max_results},
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        payload = resp.json()
        organic = payload.get("organic") or []
        out: list[dict] = []
        for r in organic:
            link = (r.get("link") or "").strip()
            if not link:
                continue
            out.append(
                {
                    "company_name": (r.get("title") or "N/A").strip() or "N/A",
                    "website": link,
                    "snippet": (r.get("snippet") or "").strip(),
                }
            )
        return out
    except Exception:
        return []

@tool("duckduckgo_company_search")
def duckduckgo_company_search(query: str):
    """Search for companies. Input must be a single string query."""
    JUNK_DOMAINS = [
        "youtube.com", "tiktok.com", "facebook.com", "twitter.com",
        "instagram.com", "reddit.com", "soundcloud.com", "wikipedia.org",
        "forum.", "linkedin.com/posts", "news.", ".gov", "amazon.com",
        "medium.com", "quora.com", "stackoverflow.com"
    ]
    companies = []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(
                f'"{query}" company site:(.com OR .io OR .co)',
                max_results=15
            ))
            for r in results:
                title = (r.get("title") or "").strip()
                href = (r.get("href") or "").strip()
                if not href or not href.startswith("http"):
                    continue
                if any(junk in href.lower() for junk in JUNK_DOMAINS):
                    continue
                companies.append({
                    "company_name": title or "N/A",
                    "website": href,
                    "snippet": (r.get("body") or "").strip(),
                })
    except Exception:
        companies = []

    if not companies:
        companies = _serper_search(query, max_results=10)

    return json.dumps(companies[:5])