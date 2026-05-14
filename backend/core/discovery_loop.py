import asyncio
import os
import re
import httpx
from urllib.parse import urlparse
from fastapi import HTTPException
from serpapi import GoogleSearch
from bs4 import BeautifulSoup

from db.client import normalize_domain, get_seen_domains, save_company, save_skipped_domain, get_recent_presented, cleanup_stale_presented
from core.query_generator import generate_query
from core.page_verifier import verify_page

MAX_ATTEMPTS = 1
MAX_RESULTS = 5
MAX_CONTENT_CHARS = 2_000

_POLISH_CHARS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")

_BLOCKED_DOMAINS = frozenset({
    "facebook.com", "youtube.com", "linkedin.com", "twitter.com", "x.com",
    "instagram.com", "tiktok.com",
    "wikipedia.org", "wikipedia.pl",
    "pracuj.pl", "olx.pl", "indeed.com", "nofluffjobs.com", "justjoin.it",
    "github.com", "stackoverflow.com", "reddit.com",
    "allegro.pl", "ceneo.pl",
    "rp.pl", "pb.pl", "infor.pl", "android.com.pl",
    "benchmark.pl", "chip.pl", "pcworld.pl", "pcformat.pl",
    "wirtualnemedia.pl", "money.pl", "forbes.pl", "businessinsider.com.pl",
    "itwiz.pl", "telepolis.pl", "antyweb.pl", "spidersweb.pl",
    # Portale szkoleniowe — dają kursy, nie firmy AI
    "nobleprog.pl", "sages.pl", "dataworkshop.eu",
    # Portale HR/news — nie firmy AI
    "pulshr.pl", "marketingonline.pl",
    # Platformy akademickie
    "issuu.com", "researchgate.net", "academia.edu",
})


def _is_blocked(domain: str) -> bool:
    if ".gov.pl" in domain:
        return True
    if domain in _BLOCKED_DOMAINS:
        return True
    return any(domain.endswith(f".{blocked}") for blocked in _BLOCKED_DOMAINS)


_ARTICLE_PATH_PATTERNS = (
    "/blog/", "/news/", "/artykul", "/artykuł", "/ranking",
    "/top-", "/lista-", "/wpis/", "/post/", "/wiedza/", "/porady/",
)
_DATE_PATH_RE = re.compile(r"/20\d{2}/\d{1,2}/")
_TITLE_NUMBER_START_RE = re.compile(r"^\d+[\s\-]")

_ARTICLE_TITLE_PATTERNS = (
    "ranking", "top 10", "top 5", "top 15", "top 20",
    "lista firm", "zestawienie firm", "najlepsze firmy",
    "jak wybrać", "jak działa", "co to jest", "jak ",
    "poradnik", "przewodnik", "czym jest", "co to",
    " firm ai", "katalog ", "companies in", "top ai", "sposobów", "zaskakując",
    "zastosowanie w 202", "w 2025r", "w 2026r", "w 2024r",
    "wprowadzenie do", "przegląd ", "omówienie",
)
_ARTICLE_SNIPPET_SIGNALS = (
    "w tym artykule",
    "przeczytaj artykuł",
    "redakcja:",
)

# Frazy które jednoznacznie wskazują na firmę NIE-AI.
# Celowo wąska lista — tylko to co na pewno wyklucza, nie to co "powinno być".
_DEFINITELY_NOT_AI = (
    "agencja marketingowa",
    "agencja reklamowa",
    "agencja seo",
    "kancelaria prawna",
    "kancelaria adwokacka",
    "kancelaria radcy",
    "biuro rachunkowe",
    "usługi księgowe",
    "sklep internetowy",
    "hurtownia",
    "agencja nieruchomości",
    "salon fryzjerski",
    "gabinet stomatologiczny",
)


def _is_likely_polish(domain: str, text: str) -> bool:
    if domain.endswith(".pl"):
        return True
    return any(c in _POLISH_CHARS for c in text)


def _is_edu_domain(domain: str) -> bool:
    return ".edu.pl" in domain


def _is_likely_article(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if path.endswith(".pdf"):
        return True
    return any(pat in path for pat in _ARTICLE_PATH_PATTERNS) or bool(_DATE_PATH_RE.search(path))


def _is_likely_article_title(title: str) -> bool:
    if _TITLE_NUMBER_START_RE.match(title):
        return True
    lower = title.lower()
    return any(pat in lower for pat in _ARTICLE_TITLE_PATTERNS)


def _is_likely_article_snippet(snippet: str) -> bool:
    lower = snippet.lower()
    return any(sig in lower for sig in _ARTICLE_SNIPPET_SIGNALS)


def _is_definitely_not_ai(snippet: str, title: str) -> bool:
    combined = (snippet + " " + title).lower()
    return any(sig in combined for sig in _DEFINITELY_NOT_AI)


def _search_serpapi(query: str) -> list[dict]:
    params = {
        "engine": "google",
        "q": query,
        "gl": "pl",
        "hl": "pl",
        "num": MAX_RESULTS,
        "api_key": os.environ["SERPAPI_KEY"],
    }
    results = GoogleSearch(params).get_dict()
    return results.get("organic_results", [])


async def _fetch_page_content(url: str, snippet: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; CRMJobAgent/1.0)"}
            resp = await client.get(url, headers=headers)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
            if len(text) >= 300:
                return text[:MAX_CONTENT_CHARS]
    except Exception:
        pass
    return snippet[:MAX_CONTENT_CHARS] if snippet else ""


async def call_with_retry(fn, retries: int = 2, delay: float = 2.0):
    for attempt in range(retries + 1):
        try:
            return await fn()
        except Exception:
            if attempt == retries:
                raise
            await asyncio.sleep(delay)


def _name_from_title(title: str, domain: str) -> str:
    def _is_junk(text: str) -> bool:
        parts = [p.strip() for p in text.split(",")]
        return len(parts) >= 2 and all(p and p[0].isupper() for p in parts)

    def _looks_like_name(text: str) -> bool:
        # Odrzuca slogany i opisy: zaczyna się od czasownika lub przymiotnika opisowego
        junk_starts = ("jak ", "co ", "czy ", "dlaczego ", "kiedy ", "gdzie ",
                       "automatyzacja", "odzyskaj", "najlepsz", "kompleksow",
                       "profesjonaln", "innowacyjn", "skuteczn")
        lower = text.lower()
        return not any(lower.startswith(j) for j in junk_starts)

    # Próbuj ostatni człon po separatorze — standard PL: "Opis | Nazwa Firmy"
    for sep in (" | ", " – ", " - "):
        parts = title.split(sep)
        if len(parts) > 1:
            candidate = parts[-1].strip()
            if 2 < len(candidate) < 45 and not _is_junk(candidate) and _looks_like_name(candidate):
                return candidate

    # Fallback: pierwszy człon przed separatorem jeśli krótki (często nazwa firmy)
    for sep in (" | ", " – ", " - "):
        parts = title.split(sep)
        if len(parts) > 1:
            candidate = parts[0].strip()
            if 2 < len(candidate) < 35 and not _is_junk(candidate) and _looks_like_name(candidate):
                return candidate

    return domain


async def find_company() -> dict | None:
    try:
        async with asyncio.timeout(55):
            pending = await get_recent_presented()
            if pending:
                return pending

            await cleanup_stale_presented()

            for attempt in range(MAX_ATTEMPTS):
                query = generate_query()
                print(f"[QUERY #{attempt+1}] {query}")

                try:
                    raw_results = await asyncio.to_thread(_search_serpapi, query)
                except Exception as e:
                    print(f"[SERP:error] {e}")
                    continue

                candidates = []
                for result in raw_results:
                    url = result.get("link", "")
                    if not url:
                        continue
                    domain = normalize_domain(url)
                    if domain:
                        candidates.append((domain, url, result))

                seen = await get_seen_domains([d for d, _, _ in candidates])

                for domain, url, result in candidates:
                    if domain in seen:
                        print(f"[SKIP:seen]    {domain}")
                        continue

                    if _is_blocked(domain):
                        print(f"[SKIP:blocked] {domain}")
                        continue

                    if _is_edu_domain(domain):
                        print(f"[SKIP:edu]     {domain}")
                        continue

                    snippet = result.get("snippet", "")
                    title = result.get("title", "")

                    if not _is_likely_polish(domain, snippet):
                        print(f"[SKIP:not-pl]  {domain} | {title}")
                        continue
                    if _is_likely_article(url):
                        print(f"[SKIP:url-pat] {domain} | {title}")
                        continue
                    if _is_likely_article_title(title):
                        print(f"[SKIP:title]   {domain} | {title}")
                        continue
                    if _is_likely_article_snippet(snippet):
                        print(f"[SKIP:snippet] {domain} | {title}")
                        continue

                    if _is_definitely_not_ai(snippet, title):
                        print(f"[SKIP:not-ai]  {domain} | {title}")
                        continue

                    # Snippet Google jest wystarczający do klasyfikacji dla większości firm.
                    # Fetch strony tylko gdy snippet za krótki — oszczędza 4-8s per kandydat.
                    if len(snippet) >= 150:
                        content = snippet[:MAX_CONTENT_CHARS]
                    else:
                        content = await _fetch_page_content(f"https://{domain}", snippet)

                    if len(content) < 50:
                        print(f"[SKIP:no-content] {domain} | {title}")
                        continue

                    print(f"[HAIKU]        {domain} | {title}")
                    try:
                        verification = await call_with_retry(
                            lambda c=content, d=domain, t=title: verify_page(c, d, t), retries=1
                        )
                    except Exception:
                        await save_skipped_domain(title or domain, url, domain)
                        print(f"[SKIP:haiku-err] {domain}")
                        continue

                    if not verification.is_polish or not verification.is_ai_company:
                        print(f"[SKIP:haiku]   {domain} | pl={verification.is_polish} ai={verification.is_ai_company}")
                        continue

                    name = _name_from_title(title, domain)
                    homepage_url = f"https://{domain}"
                    print(f"[FOUND]        {domain} | {name}")
                    company = await save_company(name=name, url=homepage_url, domain=domain)
                    return company

            return None

    except (asyncio.TimeoutError, asyncio.CancelledError):
        raise HTTPException(503, "Wyszukiwanie trwa za długo. Spróbuj ponownie.")
