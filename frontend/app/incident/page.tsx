"use client";
// Incident analysis: describe an incident or near miss in words; get the likely accident type, why the model thinks so,
// similar real accidents, the rules that apply and a fact-checked summary (FastAPI /incident-analysis).
import { useState } from "react";
import { analyzeIncident, type IncidentResult } from "@/lib/api";
import WordExplanation from "@/components/WordExplanation";
import { CheckLegend, CheckScore, CheckedText, RiskBars, RuleList, Section, SimilarList, Timeline } from "@/components/Shared";

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
      <div className="intro">
        <h1>Incident analysis</h1>
        <p>Describe an incident, near miss or unsafe condition in your own words. The classifier predicts the likely accident,
          the explanation shows which words drove the prediction, and the matching rules and similar real accidents are listed.</p>
      </div>

      <section className="intake intake-text">
        <label htmlFor="incident" className="visually-hidden">Incident description</label>
        <textarea id="incident" value={text} onChange={(e) => setText(e.target.value)} placeholder="What happened, where, and what equipment or PPE was involved?" />
        <div className="row row-between">
          <div className="seg" role="group" aria-label="Explanation method">
            <button aria-pressed={!method} onClick={() => { setMethod(undefined); if (r) run(text, undefined); }} title="The method that was most faithful in experiment E10">Auto (best in E10)</button>
            {METHODS.map(([k, l]) => <button key={k} aria-pressed={method === k} onClick={() => { setMethod(k); if (r) run(text, k); }}>{l}</button>)}
          </div>
          <button className="btn" disabled={busy || !text.trim()} onClick={() => run()}>{busy ? "Analysing" : "Analyse incident"}</button>
        </div>
        <div className="examples">
          <span>Examples:</span>
          {EXAMPLES.map(([label, x]) => <button key={label} className="example" title={x} onClick={() => { setText(x); run(x); }}>{label}</button>)}
        </div>
      </section>
      {error && <p className="error">{error}</p>}

      {r && (
        <div className="result">
          <div className="split">
            <Section title="Likely accident" source="DistilBERT classifier fine-tuned on OSHA Severe Injury Reports (context-only text).">
              <RiskBars risk={r.risk} />
            </Section>
            <Section title="Why the model predicts this">
              {r.explanation ? <WordExplanation e={r.explanation} hidden={r.hidden_words} /> : <p className="muted">Word explanations are not available (explainer not loaded).</p>}
              {r.top_words.length > 0 && <p className="strong-words">Strongest evidence: <b>{r.top_words.join(", ")}</b></p>}
            </Section>
          </div>
          <Section title="Analysis summary" aside={<CheckScore s={r.check_summary} />}>
            <CheckedText text={r.report} checks={r.checks} />
            <CheckLegend />
          </Section>
          <div className="split">
            <Section title="Similar real accidents" source="Nearest OSHA injury reports by meaning."><SimilarList items={r.similar} /></Section>
            <Section title="Rules that apply"><RuleList rules={r.rules} /></Section>
          </div>
          <Section title="Time per step" source="Measured by the backend for this description."><Timeline t={r.timings} /></Section>
        </div>
      )}
    </>
  );
}
