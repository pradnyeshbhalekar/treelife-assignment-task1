from fastapi import FastAPI

from app.adapters.hubspot import HubSpotAdapter

app = FastAPI(title="Scope")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/discover/{object_type}")
async def discover(object_type: str, sample_size: int = 10):
    adapter = HubSpotAdapter()
    return await adapter.discover_schema(object_type, sample_size=sample_size)
