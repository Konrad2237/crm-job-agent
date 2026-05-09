from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path
import os

# .env leży w głównym folderze projektu (katalog wyżej niż backend/)
load_dotenv(Path(__file__).parent.parent / ".env")

app = FastAPI(title="CRM Job Agent API")

_origins = ["http://localhost:3000", "http://localhost:3001"]
if os.getenv("FRONTEND_URL"):
    _origins.append(os.getenv("FRONTEND_URL"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)

from routers import discovery, companies  # noqa: E402 — import po app żeby uniknąć circular imports
app.include_router(discovery.router)
app.include_router(companies.router)


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "crm-job-agent"}
