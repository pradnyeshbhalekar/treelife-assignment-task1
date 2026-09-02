import { useState } from "react";
import "./App.css";

const API_BASE = "http://localhost:8000";

const EXAMPLE_QUESTIONS = [
  "How many open deals does Garima own?",
  "How many deals does Ishan own?",
  "How many open deals does Zubin own?",
];

type OwnerRule = { field: string; match_values: string[]; why: string };
type StatusRules = {
  include_stage_field: string | null;
  include_stage_values: string[];
  exclude_if_field_contains: Record<string, string[]>;
  why: string;
};
type Plan = {
  owner_target: string | null;
  owner_rules: OwnerRule[];
  status_rules: StatusRules;
  reasoning_summary: string;
};
type AskResponse = {
  answer_count: number;
  matched_records: string[];
  plan: Plan;
  explanation: string;
  zero_result_note: string;
};

function App() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAsk(q?: string) {
    const finalQuestion = q ?? question;
    if (!finalQuestion.trim()) return;
    setQuestion(finalQuestion);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const resp = await fetch(`${API_BASE}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: finalQuestion }),
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
    <div className="page">
      <div className="container">
        <div className="hero">
          <h1>Scope</h1>
          <p className="subtitle">
            Ask your CRM a plain-English question. Scope figures out how your data is actually
            structured, even when it's messy.
          </p>
        </div>

        <div className="ask-card">
          <div className="ask-row">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAsk()}
              placeholder="e.g. How many open deals does Garima own?"
              disabled={loading}
            />
            <button onClick={() => handleAsk()} disabled={loading || !question.trim()}>
              {loading ? <span className="spinner" /> : "Ask"}
            </button>
          </div>

          <div className="examples">
            <span className="examples-label">Try:</span>
            {EXAMPLE_QUESTIONS.map((q) => (
              <button key={q} className="example-chip" onClick={() => handleAsk(q)} disabled={loading}>
                {q}
              </button>
            ))}
          </div>
        </div>

        {error && <div className="error">{error}</div>}

        {result && (
          <div className="result">
            <div className="answer-row">
              <div className="answer-count">{result.answer_count}</div>
              <div className="answer-label">
                {result.answer_count === 1 ? "matching record" : "matching records"}
              </div>
            </div>

            {result.matched_records.length > 0 && (
              <ul className="matches">
                {result.matched_records.map((name, i) => (
                  <li key={i}>{name}</li>
                ))}
              </ul>
            )}

            <div className="explanation">
              <span className="explanation-label">Reasoning</span>
              {result.explanation}
            </div>

            {result.zero_result_note && (
              <div className="zero-note">
                <span className="zero-note-label">Why nothing matched</span>
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
