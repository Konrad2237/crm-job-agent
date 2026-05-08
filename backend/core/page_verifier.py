from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel


class PageVerification(BaseModel):
    is_polish: bool
    is_ai_company: bool
    what_they_do: str  # krótki opis jak "chatboty, agenci AI" — pusty string jeśli firma nie pasuje


# temperature=0.0 — klasyfikacja wymaga determinizmu, nie kreatywności
_model = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    max_tokens=150,
    temperature=0.0,
).with_structured_output(PageVerification)

SYSTEM_PROMPT = """Klasyfikujesz strony internetowe firm pod kątem dwóch kryteriów.

Kryterium 1 — is_polish: czy to polska firma?
- Strona głównie po polsku LUB siedziba w Polsce LUB domena .pl
- Oddziały zagranicznych korporacji w Polsce = NIE (szukamy polskich firm)

Kryterium 2 — is_ai_company: czy firma zajmuje się AI/sztuczną inteligencją?
- TAK: chatboty, wirtualni asystenci, agenci AI, automatyzacje oparte na LLM, RAG, generatywne AI, wdrożenia modeli językowych
- NIE: zwykłe oprogramowanie bez AI, consulting IT bez AI, e-commerce, marketing

what_they_do: tylko gdy OBA kryteria TAK — jednozdaniowy opis np. "chatboty dla e-commerce, integracje GPT-4".
Gdy któreś kryterium NIE — zwróć pusty string.

Klasyfikuj wyłącznie na podstawie treści którą dostajesz. Nie zgaduj."""


async def verify_page(content: str) -> PageVerification:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Treść strony:\n\n{content}"),
    ]
    return await _model.ainvoke(messages)
