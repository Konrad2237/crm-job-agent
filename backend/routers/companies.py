from fastapi import APIRouter, HTTPException
from typing import Optional

from db.client import get_companies, patch_company_fields, is_domain_seen, save_manual_company, normalize_domain
from models.schemas import PatchCompanyRequest, ManualCompanyRequest

router = APIRouter()


@router.get("/companies")
async def list_companies(page: int = 1, limit: int = 20, status: Optional[str] = None):
    # Zawsze paginacja — nigdy wszystkich rekordów naraz.
    offset = (page - 1) * limit
    return await get_companies(status=status, limit=limit, offset=offset)


@router.post("/companies/manual")
async def add_manual(data: ManualCompanyRequest):
    domain = normalize_domain(data.url)
    if await is_domain_seen(domain):
        raise HTTPException(409, "Firma z tą domeną już jest w bazie.")
    payload = data.model_dump(exclude={"name", "url"}, exclude_none=True)
    return await save_manual_company(data.name, data.url, domain, payload)


@router.patch("/companies/{company_id}")
async def patch_company(company_id: str, data: PatchCompanyRequest):
    payload = data.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(400, "Brak pól do aktualizacji.")
    return await patch_company_fields(company_id, payload)
