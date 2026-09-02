from typing import Any

from app.adapters.base import FieldInfo, ObjectSchema, ToolAdapter

# A stand-in for a file-drive tool (e.g. Google Drive). Demonstrates that the same
# semantic mapping layer works against a fundamentally different tool shape - no
# pipeline stages, no CRM owner objects - purely by discovering this tool's own
# fields and messy conventions, same as the HubSpot adapter does for a CRM.

FIELDS = [
    FieldInfo(name="filename", label="File name", field_type="text", group=None, options=None),
    FieldInfo(name="folder", label="Folder", field_type="text", group=None, options=None),
    FieldInfo(name="tags", label="Tags", field_type="text", group=None, options=None),
    FieldInfo(name="shared_with", label="Shared With", field_type="text", group=None, options=None),
    FieldInfo(name="notes", label="Notes", field_type="textarea", group=None, options=None),
]

FILES = [
    {"id": "1", "filename": "Q3 Contract - Acme.docx", "folder": "Active Deals", "tags": "", "shared_with": "priya", "notes": ""},
    {"id": "2", "filename": "Renewal draft - Beta Corp.docx", "folder": "Active Deals", "tags": "urgent", "shared_with": "Priya M.", "notes": ""},
    {"id": "3", "filename": "Old proposal - Gamma Inc.docx", "folder": "Dead Leads", "tags": "", "shared_with": "priya", "notes": "client went silent"},
    {"id": "4", "filename": "NDA - Delta LLC.pdf", "folder": "Active Deals", "tags": "", "shared_with": "rohan", "notes": ""},
    {"id": "5", "filename": "Cold outreach - Epsilon.docx", "folder": "Dead Leads", "tags": "", "shared_with": "Rohan K.", "notes": ""},
    {"id": "6", "filename": "Signed MSA - Zeta Co.pdf", "folder": "Active Deals", "tags": "priority-high", "shared_with": "ishan", "notes": ""},
]


class MockDriveAdapter(ToolAdapter):
    @property
    def tool_name(self) -> str:
        return "mock_drive"

    async def list_object_types(self) -> list[str]:
        return ["files"]

    async def discover_schema(self, object_type: str, sample_size: int = 25) -> ObjectSchema:
        return ObjectSchema(
            object_type=object_type,
            fields=FIELDS,
            sample_records=FILES[:sample_size],
        )

    async def query_records(
        self, object_type: str, properties: list[str], limit: int = 200
    ) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in f.items() if k in properties or k == "id"} for f in FILES[:limit]
        ]
