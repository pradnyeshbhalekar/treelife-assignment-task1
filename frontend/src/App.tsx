import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

const SOURCES = [
  { id: "hubspot", label: "HubSpot CRM", objectType: "deals" },
  { id: "mock_drive", label: "File Drive (demo)", objectType: "files" },
] as const;

const EXAMPLE_QUESTIONS: Record<string, string[]> = {
  hubspot: [
    "How many open deals does Garima own?",
    "How many deals does Ishan own?",
    "How many open deals does Zubin own?",
    "How many deals are urgent?",
  ],
  mock_drive: [
    "How many active files does Priya have?",
    "How many files does Rohan have?",
  ],
};

type IncludeRule = {
  field: string;
  match_type: "equals" | "contains";
  match_values: string[];
};
type Filter = {
  concept: string;
  target: string;
  include_if: IncludeRule[];
  exclude_if_contains: Record<string, string[]>;
  why: string;
};
type Plan = {
  filters: Filter[];
  reasoning_summary: string;
};
type AskResponse = {
  answer_count: number;
  answer_sentence: string;
  matched_records: string[];
  plan: Plan;
  explanation: string;
  zero_result_note: string;
};

function App() {
  const [source, setSource] = useState<(typeof SOURCES)[number]["id"]>("hubspot");
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleSourceChange(next: (typeof SOURCES)[number]["id"]) {
    setSource(next);
    setQuestion("");
    setResult(null);
    setError(null);
  }

  async function handleAsk(q?: string) {
    const finalQuestion = q ?? question;
    if (!finalQuestion.trim()) return;
    setQuestion(finalQuestion);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const activeSource = SOURCES.find((s) => s.id === source)!;
      const resp = await fetch(`${API_BASE}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: finalQuestion,
          source: activeSource.id,
          object_type: activeSource.objectType,
        }),
      });
      if (!resp.ok) throw new Error(`Server error: ${resp.status}`);
      setResult(await resp.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-svh justify-center bg-bg">
      <div className="w-full max-w-2xl px-6 py-20 text-left">
        <div className="mb-10 text-center">
          <h1 className="mb-2 bg-gradient-to-br from-heading to-accent bg-clip-text text-6xl font-bold leading-tight text-transparent">
            Scope
          </h1>
          <p className="mx-auto max-w-md text-lg leading-relaxed text-muted">
            Ask your CRM a plain-English question. Scope figures out how your data is actually
            structured, even when it's messy.
          </p>
        </div>

        <div className="mb-4 flex justify-center gap-1.5">
          {SOURCES.map((s) => (
            <button
              key={s.id}
              onClick={() => handleSourceChange(s.id)}
              disabled={loading}
              className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors disabled:opacity-60 ${
                source === s.id
                  ? "border-accent/50 bg-accent/15 text-heading"
                  : "border-border bg-transparent text-muted"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        {source === "mock_drive" && (
          <div className="mb-4 rounded-lg border border-border bg-surface/60 px-4 py-2.5 text-center text-sm text-muted">
            Using temporary, in-memory demo data — 6 files across "Active Deals" and "Dead
            Leads" folders, shared with Priya, Rohan, and Ishan. No external API involved.
          </div>
        )}

        <div className="rounded-2xl border border-border bg-surface p-5 shadow-lg shadow-black/20">
          <div className="flex gap-2.5">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAsk()}
              placeholder={`e.g. ${EXAMPLE_QUESTIONS[source][0]}`}
              disabled={loading}
              className="flex-1 rounded-lg border border-border bg-bg px-4 py-3.5 text-base text-heading placeholder:text-muted/70 focus:border-accent focus:outline-none disabled:opacity-60"
            />
            <button
              onClick={() => handleAsk()}
              disabled={loading || !question.trim()}
              className="min-w-[84px] rounded-lg bg-accent px-5 py-3.5 text-base font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              {loading ? (
                <span className="mx-auto block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              ) : (
                "Ask"
              )}
            </button>
          </div>

          <div className="mt-3.5 flex flex-wrap items-center gap-2">
            <span className="mr-0.5 text-sm text-muted">Try:</span>
            {EXAMPLE_QUESTIONS[source].map((q) => (
              <button
                key={q}
                onClick={() => handleAsk(q)}
                disabled={loading}
                className="rounded-full border border-border bg-bg px-3 py-1.5 text-sm text-muted transition-colors hover:border-accent hover:text-heading disabled:opacity-50"
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3.5 text-red-400">
            {error}
          </div>
        )}

        {result && (
          <div className="mt-6 animate-[fade-in_0.25s_ease] rounded-2xl border border-border bg-surface p-6">
            <div className="mb-3.5 text-lg font-semibold text-heading">
              {result.answer_sentence}
            </div>
            <div className="mb-4 flex items-baseline gap-2.5">
              <div className="text-4xl font-bold leading-none text-heading">
                {result.answer_count}
              </div>
              <div className="text-sm text-muted">
                {result.answer_count === 1 ? "matching record" : "matching records"}
              </div>
            </div>

            {result.matched_records.length > 0 && (
              <ul className="mb-5 flex flex-col gap-1.5">
                {result.matched_records.map((name, i) => (
                  <li
                    key={i}
                    className="rounded-lg border border-border bg-bg px-3 py-2 text-sm text-heading"
                  >
                    {name}
                  </li>
                ))}
              </ul>
            )}

            <div className="text-[15px] leading-relaxed text-muted">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-accent">
                Reasoning
              </span>
              {result.explanation}
            </div>

            {result.zero_result_note && (
              <div className="mt-4 rounded-lg border border-accent/50 bg-accent/15 px-4 py-3.5 text-sm leading-relaxed text-heading">
                <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-accent">
                  Why nothing matched
                </span>
                {result.zero_result_note}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
