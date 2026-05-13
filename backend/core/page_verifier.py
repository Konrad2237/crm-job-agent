from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel


class PageVerification(BaseModel):
    is_polish: bool
    is_ai_company: bool


_model = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    max_tokens=50,
    temperature=0.0,
).with_structured_output(PageVerification)

SYSTEM_PROMPT = """Oceniasz fragment strony internetowej pod kątem dwóch pytań.

is_polish: Czy to firma działająca na polskim rynku? Oceń z kontekstu — język, lokalizacja, do kogo adresuje ofertę. Oddział zagranicznej korporacji w Polsce to NIE.

is_ai_company: Czy ta firma aktywnie tworzy lub wdraża rozwiązania AI dla swoich klientów? Tak rozumiane jako: buduje produkty AI, wdraża je u klientów, doradza w AI — czyli AI jest częścią jej oferty handlowej. NIE jeśli to artykuł, katalog firm, portal, lub firma która tylko wewnętrznie korzysta z AI.

Gdy kontekst jest niejednoznaczny — zwróć False."""


async def verify_page(content: str) -> PageVerification:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Treść strony:\n\n{content}"),
    ]
    return await _model.ainvoke(messages)
