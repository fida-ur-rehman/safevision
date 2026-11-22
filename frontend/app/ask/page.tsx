"use client";
// Rules assistant: hybrid search (keywords + meaning + re-ranker) over the safety rule books, plus a short answer
// written only from the retrieved rules and checked sentence by sentence.
import { useState } from "react";
import { ask, type Answer } from "@/lib/api";
import { RuleList } from "@/components/Shared";

const EXAMPLES = [
  "When is fall protection required?",
  "Does the employer have to provide hard hats?",
  "When must workers wear eye protection?",
  "Who must wear a high-visibility garment?",
];

export default function AskPage() {
  const [q, setQ] = useState("");
  const [a, setA] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function go(question: string) {
    if (!question.trim()) return;
    setQ(question); setBusy(true); setError(null);
    try { setA(await ask(question)); } catch (e) { setError(`Search failed: ${e instanceof Error ? e.message : String(e)}`); }
    finally { setBusy(false); }
  }
  const backed = a ? a.checks.filter((c) => c.label === "supported").length : 0;

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Rules assistant</h1>
          <p>Ask a safety question in plain words. The answer uses only the rules found, and cites them by section.</p>
        </div>
      </header>
      <section className="panel">
        <form className="askbar" onSubmit={(e) => { e.preventDefault(); go(q); }}>
          <label htmlFor="q" className="visually-hidden">Question</label>
          <input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Is a hard hat required near a crane?" />
          <button className="btn" disabled={busy || !q.trim()}>{busy ? "Searching…" : "Ask"}</button>
        </form>
        <div className="examples">{EXAMPLES.map((x) => <button key={x} className="example" onClick={() => go(x)}>{x}</button>)}</div>
        {error && <p className="error" style={{ marginTop: 14 }}>{error}</p>}
      </section>
      {a && (
        <>
          {a.answer && (
            <section className="panel" style={{ marginTop: 16 }}>
              <div className="panel-head"><h2>Answer</h2>
                {a.checks.length > 0 && <span className={`chip ${backed === a.checks.length ? "chip-ok" : "chip-warn"}`}>{backed} of {a.checks.length} sentences backed by the rules</span>}
              </div>
              <p className="answer">{a.answer}</p>
            </section>
          )}
          <section className="panel" style={{ marginTop: 16 }}><h2>Rules found</h2><RuleList rules={a.rules} openFirst /></section>
        </>
      )}
    </>
  );
}
