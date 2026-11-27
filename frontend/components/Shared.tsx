// Pieces shared by the Inspect, Incident analysis and Rules pages.
import type { ReactNode } from "react";
import type { Check, CheckSummary, Risk, Rule, Similar, Status } from "@/lib/api";

// A titled block of the result. `source` names the model or data behind the block, so every number can be traced.
export function Section({ title, aside, source, children }: { title: string; aside?: ReactNode; source?: string; children: ReactNode }) {
  return (
    <section className="block">
      <div className="block-head"><h2>{title}</h2>{aside}</div>
      {children}
      {source && <p className="source">{source}</p>}
    </section>
  );
}

const STATUS_TEXT: Record<Status, string> = { yes: "worn", no: "missing", unsure: "unclear", "n/a": "not visible" };

// One cell of the PPE checklist
export function StatusMark({ status, conf }: { status: Status; conf?: number }) {
  const sym = { yes: "✓", no: "✕", unsure: "?", "n/a": "" }[status];
  const tip = STATUS_TEXT[status] + (conf != null && status !== "n/a" ? ` (confidence ${Math.round(conf * 100)}%)` : "");
  return <span className={`mark mark-${status === "n/a" ? "na" : status}`} title={tip}><span aria-hidden>{sym}</span><span className="visually-hidden">{tip}</span></span>;
}

const MARK: Record<Check["label"], string> = { supported: "m-ok", unsupported: "m-warn", contradicted: "m-bad", "invented citation": "m-bad" };
const RANK: Record<string, number> = { "m-ok": 1, "m-warn": 2, "m-bad": 3 };

// Report text with headings and bullets. Each checked sentence is underlined in the colour of its fact-check result,
// and the left margin repeats the worst result of the line so problems are easy to find.
export function CheckedText({ text, checks }: { text: string; checks: Check[] }) {
  return (
    <div className="report">
      {text.split("\n").map((line, i) => {
        const t = line.trim();
        if (!t) return null;
        if (/^\**#*\s*[A-Z][A-Za-z /&-]{2,40}:\**\s*$/.test(t)) return <h3 key={i}>{t.replace(/[*#:]/g, "").trim()}</h3>;
        let worst = "";
        let parts: ReactNode[] = [t.replace(/^\s*[-*•]\s*/, "")];
        checks.forEach((c, j) => {
          parts = parts.flatMap((p): ReactNode[] => {
            if (typeof p !== "string" || !p.includes(c.sentence)) return [p];
            const cls = MARK[c.label];
            if ((RANK[cls] ?? 0) > (RANK[worst] ?? 0)) worst = cls;
            const [a, ...rest] = p.split(c.sentence);
            const tip = `${c.label}, entailment ${c.entail.toFixed(2)}${c.best_evidence ? `\nBest evidence: ${c.best_evidence}` : ""}`;
            return [a, <mark key={`${i}-${j}`} className={cls} title={tip}>{c.sentence}</mark>, rest.join(c.sentence)];
          });
        });
        return <p key={i} className={`${/^\s*[-*•]/.test(t) ? "bullet" : ""} ${worst ? `g-${worst}` : ""}`}>{parts}</p>;
      })}
    </div>
  );
}

export function CheckScore({ s }: { s: CheckSummary | null }) {
  if (!s) return null;
  return (
    <span className="score">
      <span className="s-ok">{s.supported_pct.toFixed(0)}% supported</span>
      {s.unsupported_pct > 0 && <span className="s-warn">{s.unsupported_pct.toFixed(0)}% unverified</span>}
      {s.contradicted_pct > 0 && <span className="s-bad">{s.contradicted_pct.toFixed(0)}% contradicted</span>}
      {s.invented_citations > 0 && <span className="s-bad">{s.invented_citations} unknown rule cited</span>}
    </span>
  );
}

export function CheckLegend() {
  return (
    <p className="legend">
      <span className="lg lg-ok" /> supported by a finding or a retrieved rule
      <span className="lg lg-warn" /> not verified
      <span className="lg lg-bad" /> contradicted, or cites a rule that was not retrieved.
      Corrective actions are advice and are not checked. Hover a sentence to see its evidence.
    </p>
  );
}

const TARGET: Record<string, string> = { event_group: "Accident type", body_group: "Body part at risk", severity: "Severity" };

export function RiskBars({ risk, only }: { risk: Risk; only?: string[] }) {
  return (
    <div className="risk">
      {Object.entries(risk).filter(([k]) => !only || only.includes(k)).map(([k, list]) => (
        <div key={k} className="risk-group">
          <h3>{TARGET[k] ?? k}</h3>
          {list.slice(0, 3).map(([name, p], j) => (
            <div key={name} className={`risk-row ${j === 0 ? "top" : ""}`}>
              <span className="risk-name">{name}</span>
              <span className="risk-track" aria-hidden><span style={{ width: `${Math.max(1.5, p * 100)}%` }} /></span>
              <span className="risk-pct">{Math.round(p * 100)}%</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

export function RuleList({ rules, openFirst = false }: { rules: Rule[]; openFirst?: boolean }) {
  if (!rules.length) return <p className="muted">No rule was retrieved.</p>;
  return (
    <div className="refs">
      {rules.map((r, i) => (
        <details key={`${r.section}-${i}`} open={openFirst && i === 0}>
          <summary><span className="ref-id">{r.section}</span><span>{r.heading.replace(r.section, "").trim() || r.source}</span></summary>
          <p>{r.text}</p>
          <p className="ref-src">{r.source}</p>
        </details>
      ))}
    </div>
  );
}

export function SimilarList({ items }: { items: Similar[] }) {
  if (!items.length) return <p className="muted">No similar accident found.</p>;
  return (
    <div className="refs">
      {items.map((a, i) => (
        <details key={i} open={i === 0}>
          <summary><span className="ref-id">{a.year}</span><span>{a.event_group}, {a.body_group.toLowerCase()}, {a.severity}</span></summary>
          <p>{a.narrative}</p>
          <p className="ref-src">Similarity {a.score.toFixed(2)}</p>
        </details>
      ))}
    </div>
  );
}

// Time of each pipeline step, as measured by the backend.
const STEP: Record<string, string> = {
  vision_ms: "Detection and matching", caption_ms: "Scene caption", classifier_ms: "Accident classifier", explain_ms: "Word explanation",
  similar_ms: "Similar accidents", rules_ms: "Rule search", report_ms: "Report and fact check",
};
const fmt = (v: number) => (v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v)} ms`);

export function Timeline({ t }: { t: Record<string, number> }) {
  const steps = Object.entries(t).filter(([k, v]) => k in STEP && v > 0);
  const total = steps.reduce((a, [, v]) => a + v, 0);
  const max = Math.max(1, ...steps.map(([, v]) => v));
  return (
    <table className="timing">
      <tbody>
        {steps.map(([k, v]) => (
          <tr key={k}>
            <th scope="row">{STEP[k]}</th>
            <td className="timing-bar"><span style={{ width: `${Math.max(0.6, (100 * v) / max)}%` }} /></td>
            <td>{fmt(v)}</td>
          </tr>
        ))}
        <tr className="total"><th scope="row">Total</th><td /><td>{fmt(total)}</td></tr>
      </tbody>
    </table>
  );
}
