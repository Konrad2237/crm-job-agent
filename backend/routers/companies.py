from fastapi import APIRouter, HTTPException
from typing import Optional

from db.client import get_companies, get_stats, patch_company_fields, delete_company, is_domain_seen, save_manual_company, normalize_domain
from models.schemas import PatchCompanyRequest, ManualCompanyRequest

router = APIRouter()


@router.get("/companies/stats")
async def company_stats():
    return await get_stats()


@router.get("/companies")
async def list_companies(
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = "created_at",
    order: str = "desc",
):
    offset = (page - 1) * limit
    return await get_companies(status=status, limit=limit, offset=offset, search=search, sort=sort, order=order)


@router.post("/companies/manual")
async def add_manual(data: ManualCompanyRequest):
    domain = normalize_domain(data.url)
    if await is_domain_seen(domain):
        raise HTTPException(409, "Firma z tą domeną już jest w bazie.")
    payload = data.model_dump(exclude={"name", "url"}, exclude_none=True)
    return await save_manual_company(data.name, data.url, domain, payload)


@router.patch("/companies/{company_id}")
async def patch_company(company_id: str, data: PatchCompanyRequest):
    payload = data.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(400, "Brak pól do aktualizacji.")
    return await patch_company_fields(company_id, payload)


@router.delete("/companies/{company_id}", status_code=204)
async def remove_company(company_id: str):
    await delete_company(company_id)
