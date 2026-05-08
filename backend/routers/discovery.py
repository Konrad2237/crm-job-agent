from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

from core.discovery_loop import find_company
from db.client import update_company_status
from models.schemas import CompanyOut, ApplyRequest

router = APIRouter()


@router.post("/find")
async def find():
    # Odpala discovery loop — może zająć do 25 sekund.
    # Zwraca firmę lub 404 gdy po 3 próbach nic nie znaleziono.
    company = await find_company()
    if company is None:
        raise HTTPException(
            status_code=404,
            detail={"found": False, "message": "Nie znaleziono nowych firm. Spróbuj za chwilę."},
        )
    return company


@router.post("/companies/{company_id}/skip")
async def skip(company_id: str):
    return await update_company_status(company_id, "skipped")


@router.post("/companies/{company_id}/apply")
async def apply(company_id: str, data: ApplyRequest):
    extra = data.model_dump(exclude_none=True)
    extra["applied_at"] = datetime.now(timezone.utc).isoformat()
    return await update_company_status(company_id, "applied", extra=extra)
