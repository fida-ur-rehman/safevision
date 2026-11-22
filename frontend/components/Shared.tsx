// Pieces shared by the Inspect, Incident analysis and Rules pages.
import type { ReactNode } from "react";
import type { Check, CheckSummary, Risk, Rule, Similar, Status } from "@/lib/api";

export const STATUS_TEXT: Record<Status, string> = { yes: "worn", no: "missing", unsure: "unclear", "n/a": "not checked" };
export const STATUS_CLASS: Record<Status, string> = { yes: "chip-ok", no: "chip-bad", unsure: "chip-warn", "n/a": "chip-na" };

export function StatusChip({ label, status }: { label: string; status: Status }) {
  const sym = { yes: "✓", no: "✕", unsure: "?", "n/a": "–" }[status];
  return <span className={`chip ${STATUS_CLASS[status]}`} title={`${label}: ${STATUS_TEXT[status]}`}><span aria-hidden>{sym}</span>{label}<span className="visually-hidden"> {STATUS_TEXT[status]}</span></span>;
}

const MARK: Record<Check["label"], string> = { supported: "m-ok", unsupported: "m-warn", contradicted: "m-bad", "invented citation": "m-bad" };

// Report text: headings, bullets, and each checked sentence underlined in the colour of its fact-check result.
export function CheckedText({ text, checks }: { text: string; checks: Check[] }) {
  return (
    <div className="report">
      {text.split("\n").map((line, i) => {
        const t = line.trim();
        if (!t) return null;
        if (/^\**#*\s*[A-Z][A-Za-z /&-]{2,40}:\**\s*$/.test(t)) return <h4 key={i}>{t.replace(/[*#:]/g, "").trim()}</h4>;
        let parts: ReactNode[] = [t.replace(/^\s*[-*•]\s*/, "")];
        checks.forEach((c, j) => {
          parts = parts.flatMap((p): ReactNode[] => {
            if (typeof p !== "string" || !p.includes(c.sentence)) return [p];
            const [a, ...rest] = p.split(c.sentence);
            return [a, <mark key={`${i}-${j}`} className={MARK[c.label]} title={`${c.label} (entailment ${c.entail})`}>{c.sentence}</mark>, rest.join(c.sentence)];
          });
        });
        return <p key={i} className={/^\s*[-*•]/.test(t) ? "bullet" : ""}>{parts}</p>;
      })}
    </div>
  );
}

export function CheckScore({ s }: { s: CheckSummary | null }) {
  if (!s) return null;
  return (
    <span className="score-row">
      <span className="chip chip-ok">{s.supported_pct.toFixed(0)}% backed by evidence</span>
      {s.unsupported_pct > 0 && <span className="chip chip-warn">{s.unsupported_pct.toFixed(0)}% not verified</span>}
      {s.contradicted_pct > 0 && <span className="chip chip-bad">{s.contradicted_pct.toFixed(0)}% contradicted</span>}
      {s.invented_citations > 0 && <span className="chip chip-bad">{s.invented_citations} unknown rule cited</span>}
    </span>
  );
}

export const CHECK_NOTE = "Green underline: backed by the findings or a retrieved rule. Amber: could not be verified. Red: contradicts the evidence or cites a rule that was not retrieved. Corrective actions are advice and are not checked.";

const TARGET: Record<string, string> = { event_group: "Accident type", body_group: "Body part at risk", severity: "Severity" };

export function RiskBars({ risk, only }: { risk: Risk; only?: string[] }) {
  return (
    <div className="bars">
      {Object.entries(risk).filter(([k]) => !only || only.includes(k)).map(([k, list]) => (
        <div key={k} className="bar-group">
          <h3>{TARGET[k] ?? k}</h3>
          {list.slice(0, 3).map(([name, p]) => (
            <div key={name} className="bar">
              <span className="bar-label">{name}</span>
              <span className="bar-pct">{Math.round(p * 100)}%</span>
              <div className="bar-track" aria-hidden><div className="bar-fill" style={{ width: `${Math.max(2, p * 100)}%` }} /></div>
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
    <div className="items">
      {rules.map((r, i) => (
        <details key={`${r.section}-${i}`} open={openFirst && i === 0}>
          <summary><b>{r.section}</b><span>{r.heading.replace(r.section, "").trim() || r.source}</span></summary>
          <p>{r.text}</p>
          <p className="small muted">Source: {r.source}</p>
        </details>
      ))}
    </div>
  );
}

export function SimilarList({ items }: { items: Similar[] }) {
  if (!items.length) return <p className="muted">No similar accident found.</p>;
  return (
    <div className="items">
      {items.map((a, i) => (
        <details key={i} open={i === 0}>
          <summary><b>{a.year}</b><span>{a.event_group}, {a.body_group.toLowerCase()}, {a.severity}</span></summary>
          <p>{a.narrative}</p>
        </details>
      ))}
    </div>
  );
}

// Time per pipeline step as one horizontal bar (useful to explain the architecture in a demo).
const STEP: Record<string, [string, string]> = {
  vision_ms: ["Detection + matching", "#1b2420"], caption_ms: ["Scene caption", "#3d6b56"], classifier_ms: ["Accident classifier", "#5b8a72"],
  explain_ms: ["Word explanation", "#7a9e8a"], similar_ms: ["Similar accidents", "#8a9690"], rules_ms: ["Rule search", "#a9b4ae"], report_ms: ["Report + fact check", "#c9a227"],
};
export function Timeline({ t }: { t: Record<string, number> }) {
  const steps = Object.entries(t).filter(([k, v]) => k in STEP && v > 0);
  const total = steps.reduce((a, [, v]) => a + v, 0) || 1;
  return (
    <div>
      <div className="timeline" role="img" aria-label="Time per step">
        {steps.map(([k, v]) => <div key={k} style={{ width: `${(100 * v) / total}%`, background: STEP[k][1] }} title={`${STEP[k][0]}: ${Math.round(v)} ms`} />)}
      </div>
      <div className="timeline-legend">
        {steps.map(([k, v]) => <span key={k}><i style={{ background: STEP[k][1] }} />{STEP[k][0]} {v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v)} ms`}</span>)}
        <span><b>Total {(total / 1000).toFixed(1)} s</b></span>
      </div>
    </div>
  );
}
