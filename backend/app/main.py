import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.adapters.hubspot import HubSpotAdapter
from app.adapters.mock_drive import MockDriveAdapter
from app.core.mapping import answer_question

app = FastAPI(title="Scope")

allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

ADAPTERS = {
    "hubspot": HubSpotAdapter,
    "mock_drive": MockDriveAdapter,
}


class AskRequest(BaseModel):
    question: str
    object_type: str = "deals"
    source: str = "hubspot"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/discover/{object_type}")
async def discover(object_type: str, sample_size: int = 10, source: str = "hubspot"):
    if source not in ADAPTERS:
        raise HTTPException(400, f"Unknown source '{source}'")
    adapter = ADAPTERS[source]()
    return await adapter.discover_schema(object_type, sample_size=sample_size)


@app.post("/ask")
async def ask(req: AskRequest):
    if req.source not in ADAPTERS:
        raise HTTPException(400, f"Unknown source '{req.source}'")
    adapter = ADAPTERS[req.source]()
    return await answer_question(adapter, req.object_type, req.question)
