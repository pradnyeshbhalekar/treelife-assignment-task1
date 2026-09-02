from typing import Any

import httpx

from app.adapters.base import FieldInfo, ObjectSchema, ToolAdapter
from app.core.config import settings

BASE_URL = "https://api.hubapi.com"


class HubSpotAdapter(ToolAdapter):
    def __init__(self, access_token: str | None = None):
        self._token = access_token or settings.hubspot_access_token

    @property
    def tool_name(self) -> str:
        return "hubspot"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def list_object_types(self) -> list[str]:
        return ["deals", "contacts", "companies"]

    async def discover_schema(self, object_type: str, sample_size: int = 25) -> ObjectSchema:
        async with httpx.AsyncClient() as client:
            props_resp = await client.get(
                f"{BASE_URL}/crm/v3/properties/{object_type}",
                headers=self._headers(),
            )
            props_resp.raise_for_status()
            raw_props = props_resp.json().get("results", [])

            fields = [
                FieldInfo(
                    name=p["name"],
                    label=p.get("label", p["name"]),
                    field_type=p.get("fieldType"),
                    group=p.get("groupName"),
                    options=[o["value"] for o in p.get("options", [])] or None,
                )
                for p in raw_props
            ]

            prop_names = [f["name"] for f in fields]
            records_resp = await client.get(
                f"{BASE_URL}/crm/v3/objects/{object_type}",
                headers=self._headers(),
                params={"limit": sample_size, "properties": ",".join(prop_names)},
            )
            records_resp.raise_for_status()
            sample_records = [
                r.get("properties", {}) for r in records_resp.json().get("results", [])
            ]

        return ObjectSchema(
            object_type=object_type,
            fields=fields,
            sample_records=sample_records,
        )

    async def get_pipeline_stages(self, object_type: str) -> dict[str, dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/crm/v3/pipelines/{object_type}", headers=self._headers()
            )
            resp.raise_for_status()
            stages: dict[str, dict] = {}
            for pipeline in resp.json().get("results", []):
                for stage in pipeline.get("stages", []):
                    stages[stage["id"]] = {
                        "label": stage.get("label"),
                        "is_closed": stage.get("metadata", {}).get("isClosed") == "true",
                    }
            return stages

    async def get_owners(self) -> dict[str, str]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/crm/v3/owners", headers=self._headers())
            resp.raise_for_status()
            return {
                o["id"]: f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
                for o in resp.json().get("results", [])
            }

    async def query_records(
        self, object_type: str, properties: list[str], limit: int = 200
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        after: str | None = None

        async with httpx.AsyncClient() as client:
            while len(results) < limit:
                page_size = min(100, limit - len(results))
                params = {"limit": page_size, "properties": ",".join(properties)}
                if after:
                    params["after"] = after

                resp = await client.get(
                    f"{BASE_URL}/crm/v3/objects/{object_type}",
                    headers=self._headers(),
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()

                for r in data.get("results", []):
                    results.append({"id": r["id"], **r.get("properties", {})})

                after = data.get("paging", {}).get("next", {}).get("after")
                if not after:
                    break

        return results
