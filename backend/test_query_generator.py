"""
Uruchom: python test_query_generator.py
Wymaga: ANTHROPIC_API_KEY w .env
"""
import asyncio
from dotenv import load_dotenv
load_dotenv()

from core.query_generator import generate_query


async def main():
    print("Test 1 — pierwsze zapytanie (brak poprzednich):")
    q1 = await generate_query([])
    print(f"  >> {q1}\n")

    print("Test 2 - drugie zapytanie (zna pierwsze):")
    q2 = await generate_query([q1])
    print(f"  >> {q2}\n")

    print("Test 3 - trzecie zapytanie (zna dwa poprzednie):")
    q3 = await generate_query([q1, q2])
    print(f"  >> {q3}\n")

    print("Wszystkie trzy zapytania różne?", len({q1, q2, q3}) == 3)


asyncio.run(main())
