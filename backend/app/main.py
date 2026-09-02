from fastapi import FastAPI
from pydantic import BaseModel

from app.adapters.hubspot import HubSpotAdapter
from app.core.mapping import answer_question

app = FastAPI(title="Scope")


class AskRequest(BaseModel):
    question: str
    object_type: str = "deals"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/discover/{object_type}")
async def discover(object_type: str, sample_size: int = 10):
    adapter = HubSpotAdapter()
    return await adapter.discover_schema(object_type, sample_size=sample_size)


@app.post("/ask")
async def ask(req: AskRequest):
    adapter = HubSpotAdapter()
    return await answer_question(adapter, req.object_type, req.question)
