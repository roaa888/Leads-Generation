from enum import Enum
from pydantic import BaseModel
from typing import Optional

class LeadStatus(str, Enum):
    VERIFIED = "Verified"
    NEW = "New"
    MISSING_EMAIL = "Missing Email"

class SearchCriteria(BaseModel):
    industry: str
    location: str
    lead_type: str
    target_role: str
    company_size: str
    keywords: Optional[str] = ""
    num_leads: int

class Lead(BaseModel):
    company_name: str = "N/A"
    contact_name: str = "N/A"
    title: str = "N/A"
    email: str = "N/A"
    phone: str = "N/A"
    location: str = "N/A"
    company_size: str = "N/A"
    website: str = "N/A"
    status: LeadStatus = LeadStatus.MISSING_EMAIL
