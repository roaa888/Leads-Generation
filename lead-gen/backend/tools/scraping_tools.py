import re
import requests
from bs4 import BeautifulSoup
from crewai.tools import tool
from urllib.parse import urljoin

def extract_phones(text):
    phone_pattern = re.compile(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
    return phone_pattern.findall(text)

def extract_emails(soup):
    emails = set()
    # mailto links
    for a in soup.find_all('a', href=True):
        if a['href'].startswith('mailto:'):
            emails.add(a['href'].replace('mailto:', '').split('?')[0])
    
    # regex from text
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    emails.update(email_pattern.findall(soup.get_text()))
    return list(emails)

@tool("website_enrichment_scraper")
def website_enrichment_scraper(url: str):
    """Visit a company website and extract key details like description, phone, and emails."""
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code != 200:
            return f"Error: Status code {response.status_code}"
            
        soup = BeautifulSoup(response.content, 'lxml')
        
        title = soup.title.string.strip() if soup.title else "N/A"
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        desc = meta_desc['content'].strip() if meta_desc and meta_desc.get('content') else "N/A"
        
        phones = extract_phones(soup.get_text())
        emails = extract_emails(soup)
        
        return f"Title: {title}\nDescription: {desc}\nPhones: {phones}\nEmails: {emails}"
    except Exception as e:
        return f"Error scraping website: {str(e)}"

