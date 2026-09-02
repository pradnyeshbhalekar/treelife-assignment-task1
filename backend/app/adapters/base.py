from abc import ABC, abstractmethod
from typing import Any


class FieldInfo(dict):
    """{name, label, field_type, group, options}"""


class ObjectSchema(dict):
    """{object_type, fields: list[FieldInfo], sample_records: list[dict]}"""


class ToolAdapter(ABC):
    @property
    @abstractmethod
    def tool_name(self) -> str: ...

    @abstractmethod
    async def list_object_types(self) -> list[str]: ...

    @abstractmethod
    async def discover_schema(self, object_type: str, sample_size: int = 25) -> ObjectSchema: ...

    @abstractmethod
    async def query_records(
        self, object_type: str, properties: list[str], limit: int = 200
    ) -> list[dict[str, Any]]: ...
