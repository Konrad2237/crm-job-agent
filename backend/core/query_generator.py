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
- agentów AI i automatyzacje procesów oparte na LLM
- rozwiązania RAG (retrieval-augmented generation)
- generatywne AI w produktach B2B lub B2C
- konsulting i wdrożenia AI
- firmy IT/tech z obszarem AI jako jedną z usług

Rotuj po tych wymiarach żeby eksplorować różne obszary:
- Branże: fintech, medtech, legaltech, HR tech, e-commerce, produkcja, logistyka, edukacja, marketing, nieruchomości
- Typ firmy: startup, software house, consulting AI, product company, agencja AI

Zasady:
- Firmy muszą być POLSKIE (siedziba w Polsce, strona po polsku, domena .pl)
- Każde zapytanie INNE niż poprzednie — zmieniaj kombinację branży, typu firmy i oferowanej usługi
- KAŻDE zapytanie musi zawierać przynajmniej jedno słowo ze zbioru: "oferta", "usługi", "wdrożenia", "rozwiązania", "dla firm", "platforma", "system" — dzięki temu wyszukiwarka znajdzie strony firmowe, nie artykuły
- Zwróć TYLKO treść zapytania, żadnych wyjaśnień ani cudzysłowów

Przykłady dobrych zapytań (wzoruj się na tej strukturze):
- "agenci AI automatyzacja procesów biznesowych polska firma oferta"
- "chatbot AI obsługa klienta wdrożenia dla e-commerce Polska"
- "platforma AI analityka medyczna Polska usługi"
- "RAG system wyszukiwania dokumentów prawnych polska firma"
- "voicebot AI call center wdrożenia dla firm"
- "AI software house NLP machine learning projekty polska"
- "automatyzacja HR rekrutacja AI rozwiązania dla firm Polska"
- "wdrożenia LLM dla branży finansowej polska firma konsulting\""""


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
