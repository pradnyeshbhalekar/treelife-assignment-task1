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

Clients often don't use fields the "textbook" way: an owner may be hand-typed into a custom \
text field instead of the built-in owner field, with nicknames/typos/casing variants. A status \
like "lost" may never be set formally and instead be hidden in a name, tag, or note, even while \
the record's official stage/status still says it's open. Priority, department, or any other \
concept may be encoded as a name prefix or tag instead of a dedicated field. The question can \
ask about ANY such concept - not just owner or status - so you must figure out, from scratch \
each time, which concepts this specific question raises and how this specific client encodes \
each one.

You are given: field definitions, the pipeline stages (with which ones are formally "closed"), \
owner accounts, and every record's human-typed/text-like field values (numeric and computed \
fields are omitted - they hold no hidden meaning). Only use fields and values that actually \
appear in what you were given - never invent field names.

Respond with JSON of this exact shape:
{
  "filters": [
    {
      "concept": "<short label for what this filter represents, e.g. 'owner', 'status', 'priority'>",
      "target": "<the specific value the question wants, e.g. 'Garima', 'open', 'urgent'>",
      "include_if": [
        {"field": "<field name>", "match_type": "equals" or "contains", "match_values": ["<value>"]}
      ],
      "exclude_if_contains": {"<field name>": ["<substring>"]},
      "why": "<short reason, and if include_if is empty, explain why nothing in the data plausibly matches the target>"
    }
  ],
  "fields_needed": ["<every field name referenced above, plus a name/label field>"],
  "reasoning_summary": "<2-3 sentence explanation of how this client's data is structured>"
}

Only include a filter object for a concept the question ACTUALLY asks about. Do not add a filter \
for a concept the question doesn't mention, even if you notice interesting data for it - an \
unfiltered question must include every record regardless of any status/priority/etc it has.

For each concept you DO include: find every field/value that could plausibly encode it, using \
match_type "equals" for exact field values (e.g. a select field, or a hand-typed name field) and \
"contains" for substrings inside longer text (e.g. "URGENT" inside a deal name, "DEAD" inside a \
description). Combine multiple ways the same concept could be expressed as separate include_if \
rules (they are OR'd together) - e.g. one client might record priority in a dedicated field for \
some records and as a name prefix for others; both should be separate rules in the same filter.

If a concept has a target (like a person's name) but you find no field/value in the data that \
plausibly refers to it (checking nicknames, typos, initials, partial matches), still add the \
filter with the target set, but leave include_if empty - this correctly produces zero results \
with a clear reason, instead of silently matching every record.

For a "status/lifecycle" concept specifically (open, active, lost, closed, etc): default \
include_if to the field/values that represent the pipeline stage, using every stage id that is \
NOT formally closed (from the pipeline stages you were given). Then actively scan every record's \
text fields for words/patterns implying it's actually dead/lost/cold even though its stage says \
open (e.g. a name prefixed "[DEAD LEAD]", or a description containing "DEAD"). If found, add \
that exact substring to exclude_if_contains. Never rely only on the stage field without checking \
text fields for contradicting hidden signals first."""


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


def _filter_matches(record: dict, filt: dict) -> bool:
    include_if = filt.get("include_if") or []
    if not include_if:
        return False

    matched = False
    for rule in include_if:
        value = str(record.get(rule["field"], "") or "")
        for mv in rule.get("match_values", []):
            if rule.get("match_type") == "contains":
                if mv.lower() in value.lower():
                    matched = True
            elif mv.lower() == value.lower():
                matched = True
            if matched:
                break
        if matched:
            break
    if not matched:
        return False

    for field, substrings in (filt.get("exclude_if_contains") or {}).items():
        text = str(record.get(field, "") or "").lower()
        if any(s.lower() in text for s in substrings):
            return False

    return True


def _record_matches_all(record: dict, filters: list[dict]) -> bool:
    return all(_filter_matches(record, f) for f in filters)


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
    filters = plan.get("filters", [])

    fields_needed = list(set(plan.get("fields_needed", []) + field_names))
    records = await adapter.query_records(object_type, fields_needed, limit=200)

    final_matches = [r for r in records if _record_matches_all(r, filters)]

    unresolved = [f for f in filters if not f.get("include_if")]

    if not records:
        note = f"No {object_type} records exist at all in this workspace."
    elif unresolved:
        parts = [f"'{f.get('target')}' ({f['concept']}): {f.get('why', '')}" for f in unresolved]
        note = "No matches, because: " + " | ".join(parts)
    elif not final_matches and filters:
        per_filter_counts = {
            f["concept"]: sum(1 for r in records if _filter_matches(r, f)) for f in filters
        }
        note = (
            "Each condition matched some records individually "
            f"({per_filter_counts}), but no record satisfied all of them together."
        )
    else:
        note = ""

    return {
        "answer_count": len(final_matches),
        "answer_sentence": _build_answer_sentence(object_type, len(final_matches), filters),
        "matched_records": [_display_name(r) for r in final_matches],
        "plan": plan,
        "explanation": plan.get("reasoning_summary", ""),
        "zero_result_note": note,
    }


NAME_FIELD_CANDIDATES = ("dealname", "filename", "name", "title", "subject")
OWNER_CONCEPT_MARKERS = ("owner", "assign", "person")


def _display_name(record: dict) -> str:
    for field in NAME_FIELD_CANDIDATES:
        if record.get(field):
            return record[field]
    return record.get("id", "unknown")


def _build_answer_sentence(object_type: str, count: int, filters: list[dict]) -> str:
    owner_filter = next(
        (
            f
            for f in filters
            if f.get("target") and any(m in f.get("concept", "").lower() for m in OWNER_CONCEPT_MARKERS)
        ),
        None,
    )
    other_filters = [f for f in filters if f is not owner_filter and f.get("target")]
    adjective = other_filters[0]["target"] if other_filters else None
    object_label = object_type[:-1] if count == 1 and object_type.endswith("s") else object_type
    noun = f"{adjective} {object_label}" if adjective else object_label

    if owner_filter:
        return f"{owner_filter['target']} has {count} {noun}."
    return f"There {'is' if count == 1 else 'are'} {count} {noun}."
