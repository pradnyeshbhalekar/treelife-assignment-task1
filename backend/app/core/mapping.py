from app.adapters.base import ToolAdapter
from app.core.llm import ask_json

INFORMATIVE_FIELD_TYPES = {"text", "textarea", "select", "radio", "checkbox", "booleancheckbox"}

# HubSpot (and similar CRMs) always include internal bookkeeping fields of these kinds -
# audit trails, record ids, timestamps - which are never where a client hides business meaning.
NOISE_NAME_MARKERS = (
    "_object_id",
    "_object_source",
    "lastmodifieddate",
    "createdate",
    "_is_in_first_deal_stage",
    "all_owner_ids",
    "notification_recipients",
    "notification_followers",
    "notification_unfollowers",
)

PLAN_SYSTEM_PROMPT = """You are a data analyst figuring out how a specific client's messy CRM \
is actually structured, so you can answer a plain-English question correctly.

Clients often don't use fields the "textbook" way: the real owner may be hand-typed into a \
custom text field instead of the built-in owner field, with nicknames/typos/casing variants. \
Status like "lost" may never be set formally and instead be hidden in a name, tag, or note, \
even while the record's official stage/status still says it's open. Priority may be encoded \
in a name prefix instead of a dedicated field.

You are given: field definitions, the pipeline stages (with which ones are formally "closed"), \
owner accounts, and every record's human-typed/text-like field values (numeric and computed \
fields are omitted - they hold no hidden meaning). Only use fields and values that actually \
appear in what you were given - never invent field names.

Respond with JSON of this exact shape:
{
  "owner_target": "<the person name the question asks about, or null if the question has no owner/person target>",
  "owner_rules": [
    {"field": "<field name>", "match_values": ["<value1>", "<value2>"], "why": "<short reason>"}
  ],
  "status_rules": {
    "has_status_filter": <true if the question asks about a status/lifecycle concept like "open"/"active"/"lost", false if it just asks about deals/records in general with no status concept>,
    "include_stage_field": "<field name or null>",
    "include_stage_values": ["<stage id>"],
    "exclude_if_field_contains": {"<field name>": ["<substring>"]},
    "why": "<short reason>"
  },
  "fields_needed": ["<every field name referenced above, plus a name/label field>"],
  "reasoning_summary": "<2-3 sentence explanation of how this client's data is structured>"
}

If the question has no owner/person target, set owner_target to null and return an empty \
owner_rules list. If the question DOES name a target person but you find no field/value in the \
data that plausibly refers to them (checking for nicknames, typos, initials, and partial \
matches), set owner_target to that name anyway and leave owner_rules empty - this correctly \
produces zero matches instead of matching everything.

If has_status_filter is false, leave include_stage_field null and exclude_if_field_contains \
empty regardless of what you notice in the data - an unfiltered count question must include \
every record, dead-looking or not. Only set has_status_filter true when the question itself \
names a status/lifecycle concept (e.g. "open", "active", "lost", "closed").

When has_status_filter is true: default include_stage_values to every stage id that is NOT \
formally closed (from the pipeline stages you were given). Then actively scan every record's \
text fields for words/patterns implying it's actually dead/lost/cold even though its stage says \
open (e.g. a name prefixed "[DEAD LEAD]", or a description containing "DEAD"). If found, add \
that exact substring to exclude_if_field_contains. Never rely only on the stage field without \
checking text fields for contradicting hidden signals first."""


def _informative_fields(schema: dict) -> list[dict]:
    return [
        {"name": f["name"], "label": f["label"]}
        for f in schema["fields"]
        if f.get("field_type") in INFORMATIVE_FIELD_TYPES
        and not any(marker in f["name"] for marker in NOISE_NAME_MARKERS)
    ]


def _compact_records(records: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if v not in (None, "")} for r in records]


async def build_plan(
    schema: dict, records: list[dict], stages: dict, owners: dict[str, str], question: str
) -> dict:
    fields = _informative_fields(schema)
    user_prompt = (
        f"Question: {question}\n\n"
        f"Object type: {schema['object_type']}\n\n"
        f"Text/select-type fields (name, label):\n{fields}\n\n"
        f"Pipeline stages (id -> label, is_closed):\n{stages}\n\n"
        f"All records, text-like fields only (empty fields omitted):\n{records}\n\n"
        f"Owner accounts (id -> name), only relevant if a field references these ids:\n{owners}"
    )
    return await ask_json(PLAN_SYSTEM_PROMPT, user_prompt)


def _matches_owner(record: dict, owner_target: str | None, owner_rules: list[dict]) -> bool:
    if owner_target is None:
        return True
    if not owner_rules:
        return False
    for rule in owner_rules:
        value = str(record.get(rule["field"], "") or "")
        if any(v.lower() == value.lower() for v in rule["match_values"]):
            return True
    return False


def _matches_status(record: dict, status_rules: dict) -> bool:
    if not status_rules.get("has_status_filter"):
        return True

    stage_field = status_rules.get("include_stage_field")
    stage_values = status_rules.get("include_stage_values") or []
    if stage_field and stage_values:
        if str(record.get(stage_field, "")) not in stage_values:
            return False

    for field, substrings in (status_rules.get("exclude_if_field_contains") or {}).items():
        text = str(record.get(field, "") or "").lower()
        if any(s.lower() in text for s in substrings):
            return False

    return True


async def answer_question(adapter: ToolAdapter, object_type: str, question: str) -> dict:
    schema = await adapter.discover_schema(object_type, sample_size=1)
    fields = _informative_fields(schema)
    field_names = [f["name"] for f in fields]

    scan_records = _compact_records(
        await adapter.query_records(object_type, field_names, limit=200)
    )

    stages: dict = {}
    get_stages = getattr(adapter, "get_pipeline_stages", None)
    if get_stages:
        stages = await get_stages(object_type)

    owners: dict[str, str] = {}
    get_owners = getattr(adapter, "get_owners", None)
    if get_owners:
        owners = await get_owners()

    plan = await build_plan(schema, scan_records, stages, owners, question)

    fields_needed = list(set(plan.get("fields_needed", []) + field_names))
    records = await adapter.query_records(object_type, fields_needed, limit=200)

    owner_target = plan.get("owner_target")
    owner_rules = plan.get("owner_rules", [])
    owner_matches = [r for r in records if _matches_owner(r, owner_target, owner_rules)]
    final_matches = [r for r in owner_matches if _matches_status(r, plan.get("status_rules", {}))]

    if not records:
        note = f"No {object_type} records exist at all in this workspace."
    elif owner_target and not owner_rules:
        note = (
            f"The question asks about '{owner_target}', but no field or value across the "
            f"{len(records)} {object_type} scanned plausibly refers to them - not as a formal "
            f"owner, nickname, or typo. This is not a data error, '{owner_target}' likely "
            f"isn't represented in this workspace at all."
        )
    elif not final_matches and owner_matches:
        note = (
            f"Found {len(owner_matches)} record(s) for this owner, but all were excluded by "
            f"the status rule: {plan.get('status_rules', {}).get('why', '')}"
        )
    else:
        note = ""

    return {
        "answer_count": len(final_matches),
        "matched_records": [r.get("dealname", r.get("id")) for r in final_matches],
        "plan": plan,
        "explanation": plan.get("reasoning_summary", ""),
        "zero_result_note": note,
    }
