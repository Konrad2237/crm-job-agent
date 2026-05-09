from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CompanyOut(BaseModel):
    id: str
    name: str
    url: str
    domain: str
    what_they_do: Optional[str]
    source: str
    status: str
    position: Optional[str]
    salary_expectation: Optional[str]
    contact_email: Optional[str]
    notes: Optional[str]
    reply_received: Optional[str]
    reply_status: Optional[str]
    created_at: datetime
    applied_at: Optional[datetime]
    updated_at: datetime


class ApplyRequest(BaseModel):
    position: Optional[str] = None
    salary_expectation: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None


class ManualCompanyRequest(BaseModel):
    name: str
    url: str
    what_they_do: Optional[str] = None
    position: Optional[str] = None
    salary_expectation: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None


class PatchCompanyRequest(BaseModel):
    name: Optional[str] = None
    what_they_do: Optional[str] = None
    status: Optional[str] = None
    position: Optional[str] = None
    salary_expectation: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None
    reply_received: Optional[str] = None
    reply_status: Optional[str] = None
