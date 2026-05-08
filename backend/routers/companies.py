from fastapi import APIRouter, HTTPException
from typing import Optional

from db.client import get_companies, patch_company_fields
from models.schemas import PatchCompanyRequest

router = APIRouter()


@router.get("/companies")
async def list_companies(page: int = 1, limit: int = 20, status: Optional[str] = None):
    # Zawsze paginacja — nigdy wszystkich rekordów naraz.
    # ?page=2&limit=20&status=applied → strona 2, tylko zaaplikowane
    offset = (page - 1) * limit
    return await get_companies(status=status, limit=limit, offset=offset)


@router.patch("/companies/{company_id}")
async def patch_company(company_id: str, data: PatchCompanyRequest):
    payload = data.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(400, "Brak pól do aktualizacji.")
    return await patch_company_fields(company_id, payload)
