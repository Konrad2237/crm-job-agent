from urllib.parse import urlparse
from fastapi import HTTPException
from supabase import create_async_client, AsyncClient
from datetime import datetime, timezone, timedelta
import os

_supabase: AsyncClient | None = None


def normalize_domain(url: str) -> str:
    # "https://www.firma.pl/o-nas" → "firma.pl"
    # Bez tego "www.firma.pl" i "firma.pl" to dwa różne rekordy w dedup.
    return urlparse(url).netloc.lower().removeprefix("www.")


async def _get_client() -> AsyncClient:
    # Lazy init — tworzymy klienta przy pierwszym użyciu, nie przy starcie serwera.
    # Dzięki temu serwer startuje nawet gdy Supabase jest chwilowo niedostępny.
    global _supabase
    if _supabase is None:
        _supabase = await create_async_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
    return _supabase


async def safe_db_call(coro):
    # Każde wywołanie Supabase idzie przez ten wrapper.
    # Bez tego każdy błąd bazy (timeout, sieć) rzuca traceback jako HTTP 500.
    # Z tym — użytkownik dostaje czytelny komunikat 503.
    try:
        return await coro
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DB ERROR] {type(e).__name__}: {e}")
        raise HTTPException(503, "Problem z bazą danych. Spróbuj ponownie.")


async def is_domain_seen(domain: str) -> bool:
    client = await _get_client()
    result = await safe_db_call(
        client.table("companies").select("id").eq("domain", domain).limit(1).execute()
    )
    return len(result.data) > 0


async def save_company(name: str, url: str, domain: str, what_they_do: str) -> dict:
    client = await _get_client()
    result = await safe_db_call(
        client.table("companies")
        .upsert(
            {"name": name, "url": url, "domain": domain, "what_they_do": what_they_do},
            on_conflict="domain",
            ignore_duplicates=True,
        )
        .execute()
    )
    # upsert z ignore_duplicates=True zwraca [] przy konflikcie — pobieramy istniejący rekord
    if not result.data:
        existing = await safe_db_call(
            client.table("companies").select("*").eq("domain", domain).single().execute()
        )
        return existing.data
    return result.data[0]


async def get_recent_presented() -> dict | None:
    # Szuka firmy którą agent już pokazał ale użytkownik jeszcze nie zdecydował.
    # Okno 24h — po tym czasie firma przechodzi do "skipped" (patrz cleanup_stale_presented).
    client = await _get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    result = await safe_db_call(
        client.table("companies")
        .select("*")
        .eq("status", "presented")
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


async def cleanup_stale_presented() -> None:
    # Firmy w statusie "presented" starsze niż 24h → "skipped".
    # Scenariusz: użytkownik zamknął przeglądarkę przed decyzją.
    # Bez tego dedup traktuje je jako "widziane" i nigdy nie wracają.
    client = await _get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    await safe_db_call(
        client.table("companies")
        .update({"status": "skipped"})
        .eq("status", "presented")
        .lt("created_at", cutoff)
        .execute()
    )


async def update_company_status(company_id: str, status: str, extra: dict = {}) -> dict:
    client = await _get_client()
    payload = {"status": status, **extra}
    result = await safe_db_call(
        client.table("companies").update(payload).eq("id", company_id).execute()
    )
    return result.data[0]


async def save_manual_company(name: str, url: str, domain: str, data: dict) -> dict:
    client = await _get_client()
    now = datetime.now(timezone.utc).isoformat()
    result = await safe_db_call(
        client.table("companies")
        .insert({
            "name": name,
            "url": url,
            "domain": domain,
            "source": "manual",
            "status": "applied",
            "applied_at": now,
            **data,
        })
        .execute()
    )
    return result.data[0]


async def patch_company_fields(company_id: str, payload: dict) -> dict:
    client = await _get_client()
    result = await safe_db_call(
        client.table("companies").update(payload).eq("id", company_id).execute()
    )
    return result.data[0]


async def get_companies(status: str | None, limit: int, offset: int) -> list[dict]:
    client = await _get_client()
    query = client.table("companies").select("*").order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    result = await safe_db_call(query.range(offset, offset + limit - 1).execute())
    return result.data
