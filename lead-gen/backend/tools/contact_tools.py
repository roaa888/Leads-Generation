import os
import requests
from crewai.tools import tool
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

@tool("hunter_find_email")
def hunter_find_email(domain: str):
    """Find emails for a given domain using Hunter.io API."""
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

@tool("extract_domain")
def extract_domain(url: str):
    """Extract and clean the domain from a given website URL."""
    try:
        netloc = urlparse(url).netloc
        if not netloc:
            # Maybe it didn't have http/https
            netloc = urlparse(f"http://{url}").netloc
            
        domain = netloc.replace('www.', '')
        return domain
    except:
        return url
