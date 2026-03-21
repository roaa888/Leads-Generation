import os
import requests
from duckduckgo_search import DDGS
from crewai.tools import tool
from dotenv import load_dotenv

load_dotenv()

@tool("duckduckgo_company_search")
def duckduckgo_company_search(query: str):
    """Search for companies matching industry, location, and keywords using DuckDuckGo."""
    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=10)
        if not results:
            return "No results found."
        
        formatted_results = []
        for r in results:
            formatted_results.append(f"Company/Title: {r.get('title')}\nURL: {r.get('href')}\nSnippet: {r.get('body')}\n---")
        
        return "\n".join(formatted_results)

@tool("serper_fallback_search")
def serper_fallback_search(query: str):
    """Fallback search using Serper.dev if DuckDuckGo results are insufficient."""
    url = "https://google.serper.dev/search"
    api_key = os.getenv("SERPER_API_KEY")
    
    if not api_key:
        return "Serper API key not found in environment."
        
    payload = {"q": query}
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        return f"Error from Serper: {response.status_code}"
        
    results = response.json().get('organic', [])
    if not results:
        return "No results found on Serper."
        
    formatted_results = []
    for r in results:
        formatted_results.append(f"Title: {r.get('title')}\nLink: {r.get('link')}\nSnippet: {r.get('snippet')}\n---")
        
    return "\n".join(formatted_results)
