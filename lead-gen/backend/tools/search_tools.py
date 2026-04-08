import json
import time
from urllib.parse import urlparse

from ddgs import DDGS
from crewai.tools import tool
from dotenv import load_dotenv
import os
import requests

load_dotenv()

# Domains that are directories, aggregators, articles, or social sites — never real company homepages.
JUNK_DOMAINS = [
    # Social / video
    "youtube.com", "tiktok.com", "facebook.com", "twitter.com", "x.com",
    "instagram.com", "reddit.com", "soundcloud.com", "pinterest.com",
    # Encyclopedias / Q&A
    "wikipedia.org", "quora.com", "stackexchange.com", "stackoverflow.com",
    # Marketplaces / mega-retailers
    "amazon.com", "ebay.com", "alibaba.com", "aliexpress.com",
    # Publishing / blogging
    "medium.com", "substack.com", "wordpress.com", "blogspot.com", "wix.com",
    # LinkedIn (posts / search pages, not company pages)
    "linkedin.com/posts", "linkedin.com/pulse", "linkedin.com/search",
    # Company / startup DIRECTORY & aggregator sites
    "crunchbase.com", "f6s.com", "angellist.com", "wellfound.com",
    "g2.com", "capterra.com", "getapp.com", "softwareadvice.com",
    "trustpilot.com", "trustradius.com", "producthunt.com",
    "clutch.co", "goodfirms.co", "designrush.com", "themanifest.com",
    "10seos.com", "topdevelopers.co", "toptal.com",
    "saasbrowser.com", "saasdatabase.net", "saasworthy.com",
    "alternativeto.net", "slashdot.org",
    # Aggregator / listing / ranking articles
    "companiesmarketcap.com", "disfold.com", "zippia.com",
    "dnb.com", "zoominfo.com", "apollo.io", "lusha.com",
    # News / media
    "techcrunch.com", "forbes.com", "businessinsider.com", "venturebeat.com",
    "wired.com", "theverge.com", "cnet.com", "zdnet.com",
    "arabianbusiness.com", "zawya.com", "albawaba.com",
    # Job boards
    "glassdoor.com", "indeed.com", "linkedin.com/jobs", "bayt.com",
    # Generic blog/article patterns
    "blog.", "digitalmarketingmaterial.com", "suffescom.com",
]


# Path keywords that signal an article, list, or blog post — not a company homepage
_ARTICLE_KEYWORDS = (
    "best-", "top-", "list-of", "how-to", "why-", "what-is",
    "guide-to", "review", "comparison", "vs-", "alternative",
    "blog", "/news/", "/article", "/post/", "/resources/",
    "/insights/", "/press/", "/learn/", "roundup",
    "importance-of", "boosts-roi", "companies-in",
)


def _is_company_url(url: str) -> bool:
    """
    Returns True only if the URL looks like a real company homepage — not an
    article, blog post, aggregator listing, or directory page.
    """
    try:
        parsed = urlparse(url)
        path   = parsed.path.strip("/").lower()
        parts  = [p for p in path.split("/") if p]

        # Block known junk domains
        full = url.lower()
        if any(junk in full for junk in JUNK_DOMAINS):
            return False

        # Deep paths (3+ segments) are almost always listing/article pages
        if len(parts) >= 3:
            return False

        # Single-segment paths that look like article slugs
        if parts:
            slug = parts[-1]
            # Slug with many hyphens = article headline
            if slug.count("-") >= 5:
                return False
            # Contains article keyword patterns
            if any(kw in path for kw in _ARTICLE_KEYWORDS):
                return False

        return True
    except Exception:
        return False


def _extract_company_name(title: str, url: str) -> str:
    """
    Derive a clean company name from the page title.
    Strips common suffixes like '| Home', '- Official Site', etc.
    """
    name = (title or "").strip()
    for sep in [" | ", " - ", " – ", " · ", " — "]:
        if sep in name:
            name = name.split(sep)[0].strip()
    return name or urlparse(url).netloc.replace("www.", "") or "N/A"


def _serper_search(query: str, *, max_results: int = 15) -> list[dict]:
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
        out = []
        for r in (resp.json().get("organic") or []):
            link = (r.get("link") or "").strip()
            if not link or not _is_company_url(link):
                continue
            out.append({
                "company_name": _extract_company_name(r.get("title", ""), link),
                "website":      link,
                "snippet":      (r.get("snippet") or "").strip(),
            })
        # Also try knowledgeGraph / sitelinks if Serper returns them
        for entity in (resp.json().get("knowledgeGraph", {}).get("attributes", {}).values()):
            pass  # reserved for future enrichment
        return out
    except Exception:
        return []


def _serper_search_homepage(industry: str, location: str, *, max_results: int = 10) -> list[dict]:
    """
    More targeted Serper query that biases toward company homepages by
    explicitly excluding common aggregators using Google's minus-operator.
    """
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return []
    exclusions = "-site:crunchbase.com -site:g2.com -site:capterra.com -site:clutch.co -site:linkedin.com -site:glassdoor.com -site:f6s.com -site:saasbrowser.com"
    query = f'{industry} company {location} official site {exclusions}'
    return _serper_search(query, max_results=max_results)


def run_company_search(query: str) -> str:
    """
    Returns a JSON string of real company dicts — aggregator/directory URLs filtered out.
    Safe to call directly (non-tool) from the pipeline.
    """
    companies = []

    for attempt in range(3):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=20))
            if results:
                for r in results:
                    href  = (r.get("href")  or "").strip()
                    title = (r.get("title") or "").strip()
                    if not href or not _is_company_url(href):
                        continue
                    companies.append({
                        "company_name": _extract_company_name(title, href),
                        "website":      href,
                        "snippet":      (r.get("body") or "").strip(),
                    })
                break
        except Exception:
            pass
        time.sleep(5)

    # Fallback 1: Serper with same query
    if not companies:
        companies = _serper_search(query)

    # Fallback 2: Serper with homepage-targeted exclusion operators
    if not companies:
        # Derive industry/location hint from the query (best-effort)
        companies = _serper_search(query + " -blog -list -ranking -top10 -best")

    return json.dumps(companies[:12])


@tool("duckduckgo_company_search")
def duckduckgo_company_search(query: str):
    """Search for companies. Input must be a single string query."""
    return run_company_search(query)


@tool("brave_search")
def brave_search(query: str):
    """Compatibility alias — routes through the same DDG → Serper stack."""
    return run_company_search(query)
