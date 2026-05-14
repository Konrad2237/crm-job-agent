import random

# Krótkie zapytania z "firma" lub "startup" wymuszają wyniki firmowe zamiast artykułów.
# Każde zapytanie = jedna konkretna nisza, nie kombinacja wielu słów kluczowych.
_QUERIES = [
    # Agenci i automatyzacja
    "polska firma agenci AI automatyzacja procesów wdrożenia",
    "startup AI automatyzacja workflow Polska oferta",
    "polska firma RPA automatyzacja robotyczna wdrożenia B2B",
    "chatbot voicebot firma Polska obsługa klienta wdrożenia",

    # ML i analityka
    "polska firma machine learning predykcja analityka wdrożenia",
    "startup ML forecasting Polska platforma SaaS",
    "polska firma computer vision inspekcja jakości wdrożenia",
    "firma AI anomalie wykrywanie fraud detection Polska",

    # NLP i dokumenty
    "polska firma przetwarzanie dokumentów OCR AI wdrożenia",
    "startup NLP analiza tekstu Polska platforma",
    "firma AI analiza umów dokumentów Polska wdrożenia",
    "polska firma RAG baza wiedzy LLM wdrożenia",

    # Branże
    "polska firma AI fintech credit scoring wdrożenia",
    "startup AI rekrutacja HR Polska platforma",
    "polska firma AI diagnostyka medyczna wdrożenia",
    "firma AI e-commerce rekomendacje personalizacja Polska",
    "polska firma AI produkcja przemysł wdrożenia",
    "startup AI logistyka supply chain Polska",
    "firma AI nieruchomości wycena Polska platforma",
    "polska firma AI contact center obsługa klienta",
    "startup AI marketing personalizacja Polska SaaS",
    "polska firma AI energetyka smart grid wdrożenia",
    "firma AI edtech szkolenia korporacyjne Polska",
    "polska firma AI bezpieczeństwo cybersecurity wdrożenia",
]


def generate_query() -> str:
    return random.choice(_QUERIES)
