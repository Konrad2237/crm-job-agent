from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

# Model inicjalizujemy raz przy imporcie modułu, nie przy każdym wywołaniu.
# max_tokens=100 — zapytanie to 5-10 słów, 100 tokenów w zupełności wystarcza
# temperature=0.9 — wysoka losowość żeby kolejne zapytania były różne, nie warianty tego samego
_model = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    max_tokens=100,
    temperature=0.9,
)

SYSTEM_PROMPT = """Generujesz zapytania do wyszukiwarki, które trafiają bezpośrednio w strony firmowe polskich firm AI — nie w artykuły, rankingi ani portale.

Cel: znaleźć stronę główną lub stronę ofertową konkretnej polskiej firmy która wdraża lub sprzedaje rozwiązania AI.

Typy firm których szukasz:
- chatboty i voiceboty dla biznesu
- agenci AI i automatyzacje LLM
- RAG i systemy wyszukiwania w dokumentach
- konsulting i wdrożenia AI
- software house z ofertą AI
- własne produkty SaaS oparte o AI

Wymiary do rotowania (zmieniaj każde zapytanie):
- Branże: fintech, medtech, legaltech, HR, e-commerce, produkcja, logistyka, edukacja, marketing, nieruchomości, ubezpieczenia
- Typ: startup, software house, agencja, product company, consulting

Zasady budowania zapytań:
- Zapytanie musi prowadzić do strony FIRMY, nie artykułu — dodaj słowa obecne na stronach firmowych: "oferta", "wdrożenia", "dla firm", "kontakt", "usługi"
- Firma musi być POLSKA — dodaj "Polska", "polska firma" lub użyj domeny .pl w zapytaniu
- Każde zapytanie inne niż poprzednie — inna branża, inny typ usługi
- Zwróć TYLKO zapytanie, bez cudzysłowów i wyjaśnień

Przykłady (struktura: usługa AI + branża + sygnał firmowy + Polska):
- agenci AI automatyzacja logistyki oferta polska firma
- wdrożenia RAG dokumenty prawne system dla kancelarii Polska
- voicebot obsługa klienta call center platforma dla firm site:.pl
- AI analityka predykcyjna fintech startup Polska usługi
- chatbot e-commerce personalizacja rekomendacje wdrożenia Polska
- NLP przetwarzanie dokumentów medycznych polska firma kontakt
- automatyzacja procesów HR rekrutacja AI rozwiązania dla firm
- LLM integracje ERP produkcja polska firma oferta wdrożenia\""""


async def generate_query(previous_queries: list[str], recent_found: list[str] | None = None) -> str:
    if previous_queries:
        previous_section = "Poprzednie zapytania (nie powtarzaj tych fraz):\n" + "\n".join(
            f"- {q}" for q in previous_queries
        )
    else:
        previous_section = "To jest pierwsze zapytanie w tej sesji."

    if recent_found:
        found_section = (
            "\nOstatnie znalezione firmy — szukaj INNEJ kategorii, nie tych samych:\n"
            + "\n".join(f"- {c}" for c in recent_found)
        )
    else:
        found_section = ""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"{previous_section}{found_section}\n\nGeneruj nowe zapytanie:"),
    ]

    response = await _model.ainvoke(messages)
    return response.content.strip()
