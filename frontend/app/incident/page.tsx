"use client";
// Incident analysis: describe an incident or near miss in words; get the likely accident type, why the model thinks so,
// similar real accidents, the rules that apply and a fact-checked summary (FastAPI /incident-analysis).
import { useState } from "react";
import { analyzeIncident, type IncidentResult } from "@/lib/api";
import WordExplanation from "@/components/WordExplanation";
import { CHECK_NOTE, CheckScore, CheckedText, RiskBars, RuleList, SimilarList, Timeline } from "@/components/Shared";

const EXAMPLES: [string, string][] = [
  ["Ladder, nobody holding it", "Worker was standing on the top rung of a step ladder to install ceiling panels, with no one holding the ladder."],
  ["Grinder without gloves or goggles", "Labourer was cutting rebar with a portable grinder without gloves or eye protection near the formwork."],
  ["Reversing excavator, no vests", "Excavator was reversing on site while two workers without high-visibility vests walked behind it."],
  ["Roof edge, harness not attached", "Crew was working on a flat roof near an unprotected edge in strong wind, harnesses were not attached."],
];
const METHODS = [["lime", "LIME"], ["shap", "SHAP"], ["ig", "Integrated Gradients"]] as const;

export default function IncidentPage() {
  const [text, setText] = useState("");
  const [method, setMethod] = useState<string | undefined>(undefined);
  const [r, setR] = useState<IncidentResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(t = text, m = method) {
    if (t.trim().split(/\s+/).length < 3) { setError("Describe the incident in at least one full sentence."); return; }
    setBusy(true); setError(null);
    try { setR(await analyzeIncident(t, m)); }
    catch (e) { setError(`Analysis failed: ${e instanceof Error ? e.message : String(e)}`); }
    finally { setBusy(false); }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Incident analysis</h1>
          <p>Describe an incident, near miss or unsafe condition. SafeVision predicts the likely accident, shows which words drove that prediction, finds similar real accidents and the rules that apply.</p>
        </div>
      </header>

      <section className="panel incident-form">
        <label htmlFor="incident" className="visually-hidden">Incident description</label>
        <textarea id="incident" value={text} onChange={(e) => setText(e.target.value)} placeholder="What happened, where, and what equipment or PPE was involved?" />
        <div className="form-row">
          <div className="seg" role="group" aria-label="Explanation method">
            <button aria-pressed={!method} onClick={() => { setMethod(undefined); if (r) run(text, undefined); }} title="The method that scored best in experiment E10">Best (auto)</button>
            {METHODS.map(([k, l]) => <button key={k} aria-pressed={method === k} onClick={() => { setMethod(k); if (r) run(text, k); }}>{l}</button>)}
          </div>
          <button className="btn" disabled={busy || !text.trim()} onClick={() => run()}>{busy ? "Analysing…" : "Analyse incident"}</button>
        </div>
        <div className="examples">
          <span className="small muted">Try an example:</span>
          {EXAMPLES.map(([label, x]) => <button key={label} className="example" title={x} onClick={() => { setText(x); run(x); }}>{label}</button>)}
        </div>
        {error && <p className="error" style={{ marginTop: 14 }}>{error}</p>}
      </section>

      {!r && !busy && <p className="empty" style={{ marginTop: 16 }}>Pick an example or write your own description to see the analysis.</p>}

      {r && (
        <>
          <div className="cols-2" style={{ marginTop: 16 }}>
            <section className="panel">
              <h2>Likely accident</h2>
              <RiskBars risk={r.risk} />
            </section>
            <section className="panel">
              <h2>Why the model thinks so</h2>
              {r.explanation ? <WordExplanation e={r.explanation} hidden={r.hidden_words} /> : <p className="muted">Word explanations are not available (explainer not loaded).</p>}
              {r.top_words.length > 0 && <p className="small" style={{ marginTop: 12 }}>Strongest evidence: <b>{r.top_words.join(", ")}</b></p>}
            </section>
          </div>
          <section className="panel" style={{ marginTop: 16 }}>
            <div className="panel-head"><h2>Analysis summary</h2><CheckScore s={r.check_summary} /></div>
            <CheckedText text={r.report} checks={r.checks} />
            <p className="small muted" style={{ marginTop: 12 }}>{CHECK_NOTE}</p>
          </section>
          <div className="cols-2" style={{ marginTop: 16 }}>
            <section className="panel"><h2>Similar real accidents</h2><SimilarList items={r.similar} /></section>
            <section className="panel"><h2>Rules that apply</h2><RuleList rules={r.rules} /></section>
          </div>
          <section className="panel" style={{ marginTop: 16 }}><h2>How long each step took</h2><Timeline t={r.timings} /></section>
        </>
      )}
    </>
  );
}
