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

SYSTEM_PROMPT = """Klasyfikujesz fragmenty stron internetowych. Odpowiedz tylko polami JSON.

is_polish: TAK jeśli polska firma (treść po polsku LUB domena .pl). Oddziały zagranicznych korporacji = NIE.

is_ai_company: TAK jeśli firma ŚWIADCZY usługi AI lub buduje produkty AI dla klientów (chatboty, agenci, RAG, automatyzacje LLM, wdrożenia AI, własny SaaS AI, software house z ofertą AI).
NIE jeśli: artykuł / ranking / katalog firm / firma tylko używa AI wewnętrznie / jedno narzędzie SaaS dla wąskiej niszy bez opisanego zespołu."""


async def verify_page(content: str) -> PageVerification:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Treść strony:\n\n{content}"),
    ]
    return await _model.ainvoke(messages)
