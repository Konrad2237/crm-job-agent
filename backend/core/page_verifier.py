from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel


class PageVerification(BaseModel):
    is_polish: bool
    is_ai_company: bool
    is_company_page: bool  # False dla list rankingów, artykułów, katalogów firm
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

Kryterium 2 — is_ai_company: czy firma oferuje usługi lub produkty z obszaru AI?
- TAK: chatboty, wirtualni asystenci, agenci AI, automatyzacje LLM, RAG, generatywne AI, wdrożenia modeli językowych, firmy IT/tech które mają AI jako jeden z oferowanych obszarów usług lub produktów
- NIE: kursy i szkolenia z AI (edukacja, akademia, bootcamp), firma tylko wspomina AI jako buzzword bez konkretnej oferty, zwykłe oprogramowanie bez AI, consulting IT bez AI, e-commerce, marketing bez AI

Kryterium 3 — is_company_page: czy to strona jednej konkretnej firmy?
- TAK: strona główna lub podstrona firmy opisująca jej ofertę/usługi
- NIE: artykuł z listą firm ("top 10 chatbotów"), katalog firm, ranking, blog, news, portal porównawczy

what_they_do: tylko gdy WSZYSTKIE trzy kryteria TAK — jednozdaniowy opis np. "chatboty dla e-commerce, integracje GPT-4".
Gdy którekolwiek kryterium NIE — zwróć pusty string.

Klasyfikuj wyłącznie na podstawie treści którą dostajesz. Nie zgaduj."""


async def verify_page(content: str) -> PageVerification:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Treść strony:\n\n{content}"),
    ]
    return await _model.ainvoke(messages)
