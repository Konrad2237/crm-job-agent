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

SYSTEM_PROMPT = """Generujesz zapytania do wyszukiwarki internetowej, żeby znajdować polskie firmy zajmujące się sztuczną inteligencją.

Szukaj firm które oferują:
- chatboty i wirtualnych asystentów dla biznesu
- agentów AI i automatyzacje procesów
- rozwiązania oparte na dużych modelach językowych (LLM)
- systemy RAG (retrieval-augmented generation)
- generatywne AI w produktach B2B lub B2C
- konsulting i wdrożenia AI

Zasady:
- Firmy muszą być POLSKIE (siedziba w Polsce, strona po polsku, domena .pl)
- Zapytanie może być po polsku lub angielsku — wybierz co da lepsze wyniki
- Każde zapytanie INNE niż poprzednie — zmieniaj frazy, branże, słowa kluczowe
- Zwróć TYLKO treść zapytania, żadnych wyjaśnień ani cudzysłowów"""


async def generate_query(previous_queries: list[str]) -> str:
    if previous_queries:
        previous_section = "Poprzednie zapytania (nie powtarzaj tych fraz):\n" + "\n".join(
            f"- {q}" for q in previous_queries
        )
    else:
        previous_section = "To jest pierwsze zapytanie w tej sesji."

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"{previous_section}\n\nGeneruj nowe zapytanie:"),
    ]

    response = await _model.ainvoke(messages)
    return response.content.strip()
