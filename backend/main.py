from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(title="CRM Job Agent API")

# CORS — bez tego przeglądarka blokuje requesty z frontendu do backendu.
# To mechanizm bezpieczeństwa: strona na vercel.app nie może domyślnie
# gadać z serwerem na railway.app, chyba że serwer to wprost zezwoli.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_URL", "http://localhost:3000"),
        "http://localhost:3000",
    ],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "crm-job-agent"}
