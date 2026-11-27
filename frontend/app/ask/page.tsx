"use client";
// Rules assistant: hybrid search (keywords + meaning + re-ranker) over the safety rule books, plus a short answer
// written only from the retrieved rules and checked sentence by sentence.
import { useState } from "react";
import { ask, type Answer } from "@/lib/api";
import { RuleList, Section } from "@/components/Shared";

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
      <div className="intro">
        <h1>Rules</h1>
        <p>Ask a safety question in plain words. The rule books are searched by keywords and by meaning, and the short answer
          is written only from the rules found, with each sentence checked against them.</p>
      </div>
      <section className="intake intake-text">
        <form className="askbar" onSubmit={(e) => { e.preventDefault(); go(q); }}>
          <label htmlFor="q" className="visually-hidden">Question</label>
          <input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Is a hard hat required near a crane?" />
          <button className="btn" disabled={busy || !q.trim()}>{busy ? "Searching" : "Search rules"}</button>
        </form>
        <div className="examples"><span>Examples:</span>{EXAMPLES.map((x) => <button key={x} className="example" onClick={() => go(x)}>{x}</button>)}</div>
      </section>
      {error && <p className="error">{error}</p>}
      {a && (
        <div className="result">
          {a.answer && (
            <Section title="Answer" aside={a.checks.length > 0 ? <span className="score"><span className={backed === a.checks.length ? "s-ok" : "s-warn"}>{backed} of {a.checks.length} sentences supported by the rules</span></span> : undefined}>
              <p className="answer">{a.answer}</p>
            </Section>
          )}
          <Section title="Rules found" source="Hybrid search: BM25 keywords and embeddings, fused by reciprocal rank and re-ranked by a cross-encoder."><RuleList rules={a.rules} openFirst /></Section>
        </div>
      )}
    </>
  );
}
