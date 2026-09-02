# Scope

A semantic translation layer that sits between a plain-English question and a business tool's
real, messy data structure — built for the Treelife AI technical assessment (Task 1).

Ask something like *"How many open deals does Garima own?"* and Scope:

1. Discovers the connected tool's actual schema and real record data via its API (no hardcoded
   field maps).
2. Figures out, per question, which fields/values plausibly encode the concepts being asked
   about (owner, status, priority, or anything else) — including hand-typed fields, nicknames,
   and hidden signals like a deal named `"[DEAD LEAD] ..."` that's still technically "open".
3. Executes the resolved filters against the real data and returns a count, the matched
   records, and a plain-English explanation of its reasoning.
4. If nothing matches, explains *why* instead of returning a misleading `0`.

It ships with two adapters to prove the approach isn't hardcoded to one tool:
- **HubSpot** (real CRM, connects with your own private-app token)
- **A mock file-drive adapter** (in-memory demo data, no API needed) — proves the same
  reasoning code handles a completely different tool shape (folders/tags instead of a CRM
  pipeline).

## Architecture

```
frontend/   React + TypeScript UI (Vite)
backend/
  app/
    adapters/    One class per tool, implementing a common ToolAdapter interface
      base.py       Abstract interface: list_object_types, discover_schema, query_records
      hubspot.py    Real HubSpot CRM integration (REST API)
      mock_drive.py In-memory "file drive" demo adapter
    core/
      llm.py         Groq LLM client wrapper
      mapping.py     The semantic layer: schema discovery -> LLM concept-mapping -> execution
    main.py        FastAPI app (/ask, /discover/{object_type})
```

The mapping layer (`core/mapping.py`) never talks to HubSpot directly — it only calls the
`ToolAdapter` interface. Adding a new tool means writing a new adapter; the reasoning logic
doesn't change.

## Setup

### Prerequisites
- Python 3.10+
- Node 20+
- A free [HubSpot](https://app.hubspot.com) account with a private app (see below)
- A free [Groq](https://console.groq.com) API key

### 1. HubSpot private app

In HubSpot: **Settings → Integrations → Private Apps → Create a private app**. Add these scopes:
- `crm.objects.deals.read`, `crm.objects.deals.write`
- `crm.schemas.deals.read`, `crm.schemas.deals.write`
- `crm.objects.owners.read`
- `crm.objects.contacts.read`, `crm.objects.companies.read`

Copy the generated access token.

### 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:
```
HUBSPOT_ACCESS_TOKEN=your-hubspot-token
GROK_API_KEY=your-groq-api-key
```

Run it:
```bash
uvicorn app.main:app --port 8000 --reload
```

Interactive API docs: `http://localhost:8000/docs`

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Trying it

The mock file-drive adapter works with no setup (no external API needed) — select
"File Drive (demo)" in the UI, or:
```bash
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"question": "How many active files does Priya have?", "object_type": "files", "source": "mock_drive"}'
```

For HubSpot, your account needs some deal data with realistic messiness (hand-typed owner
fields, a deal whose name/description implies it's dead while its stage is still open, etc.)
to see the interesting behavior — an empty account will just return `0` results honestly.

Example questions:
- `How many open deals does <name> own?` — tests hand-typed owner fields + hidden lost-status
- `How many deals does <name> own?` — no status filter, includes everything regardless of state
- `How many open deals does <someone not in your data> own?` — tests the "why nothing matched"
  explanation instead of a misleading zero
- `How many deals are urgent?` — tests a concept encoded two different ways (a real priority
  field for some records, a name prefix for others)

## Known limitations

- The Groq free tier has an 8000 tokens/minute limit; rapid back-to-back questions may hit a
  `429` — wait a few seconds and retry.
- HubSpot's owner-ID resolution (`hubspot_owner_id`) only reflects real HubSpot user accounts on
  your workspace; a free/solo HubSpot account typically only has one such user, so most
  "who owns this" messiness in the demo data comes through the hand-typed `assigned_to` field
  instead — which is itself a faithful example of the "invented fields" problem the assessment
  describes.
