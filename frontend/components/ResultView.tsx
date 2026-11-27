"use client";
// One inspection result. The photo stays on the left; everything the pipeline produced is in tabs on the right:
// workers (PPE per worker), the checked report, predicted risk, rules, similar accidents and measured step times.
import { useState } from "react";
import { heatmapUrl, missingItems, PPE_ITEMS, PPE_LABEL, workerTone, type Result } from "@/lib/api";
import { IconPrint, PpeIcon } from "./Icons";
import { CheckLegend, CheckScore, CheckedText, RiskBars, RuleList, SimilarList, Source, Timeline } from "./Shared";

const STROKE = { bad: "#e5484d", warn: "#f5a524", ok: "#30a46c" } as const;
const STATE_TEXT = { yes: "worn", no: "missing", unsure: "unclear", "n/a": "not visible" } as const;

function headline(r: Result) {
  if (!r.counts.workers) return { tone: "none", title: "No workers found", sub: "Use a photo where the workers are clearly visible." };
  if (!r.violation) return { tone: "ok", title: "PPE in place", sub: `All checked items are worn by the ${r.counts.workers} worker${r.counts.workers > 1 ? "s" : ""} found.` };
  const missing = r.workers.filter((w) => missingItems(w).length).length;
  return { tone: "bad", title: `${missing} of ${r.counts.workers} workers missing PPE`, sub: "Select a worker to see their checks." };
}

type Tab = "workers" | "report" | "risk" | "rules" | "similar" | "timing";

export default function ResultView({ r, imageSrc }: { r: Result; imageSrc: string }) {
  const [view, setView] = useState<"boxes" | "heat">("boxes");
  const [hover, setHover] = useState<number | null>(null);
  const [heatErr, setHeatErr] = useState(false);
  const [tab, setTab] = useState<Tab>("workers");
  const h = headline(r);
  const stroke = Math.max(2, Math.round(r.width / 320));
  const items = PPE_ITEMS.filter((k) => r.workers.some((w) => (w[k] ?? "n/a") !== "n/a"));

  const tabs: [Tab, string, string | number | null][] = [
    ["workers", "Workers", r.workers.length],
    ["report", "Report", r.check_summary ? `${r.check_summary.supported_pct.toFixed(0)}%` : null],
    ...(r.risk ? [["risk", "Risk", null] as [Tab, string, null]] : []),
    ["rules", "Rules", r.rules.length],
    ...(r.similar?.length ? [["similar", "Similar", r.similar.length] as [Tab, string, number]] : []),
    ["timing", "Timing", null],
  ];

  return (
    <div className="result">
      <div className="headline">
        <div>
          <h2><span className={`dot dot-${h.tone}`} aria-hidden />{h.title}</h2>
          <p>{h.sub}</p>
        </div>
        <button className="btn btn-ghost no-print" onClick={() => window.print()}><IconPrint />Export PDF</button>
      </div>

      <div className="stage">
        <figure className="photo">
          <div className="photo-frame">
            {view === "boxes" ? (
              <svg viewBox={`0 0 ${r.width} ${r.height}`} role="img" aria-label="Photo with numbered worker boxes">
                <image href={imageSrc} width={r.width} height={r.height} />
                {r.workers.map((w, i) => {
                  const [x1, y1, x2, y2] = w.box; const col = STROKE[workerTone(w)]; const s = stroke * 10;
                  const on = hover === i;
                  return (
                    <g key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} onClick={() => setTab("workers")} style={{ cursor: "pointer" }}>
                      <rect x={x1} y={y1} width={x2 - x1} height={y2 - y1} rx={stroke * 2} fill={on ? `${col}2e` : "none"} stroke={col} strokeWidth={on ? stroke * 1.8 : stroke} />
                      <rect x={x1} y={Math.max(0, y1 - s * 1.1)} width={s * 1.2} height={s} rx={s * 0.3} fill={col} />
                      <text x={x1 + s * 0.6} y={Math.max(0, y1 - s * 1.1) + s * 0.74} fontSize={s * 0.7} fill="#fff" fontWeight={700} textAnchor="middle">{i + 1}</text>
                    </g>
                  );
                })}
              </svg>
            ) : heatErr ? (
              <p className="photo-empty">The heat map could not be made. Check that the detector is loaded in the backend.</p>
            ) : (
              <img src={heatmapUrl(r.id)} alt="Detector attention heat map over the photo" onError={() => setHeatErr(true)} />
            )}
            <div className="toggle no-print" role="group" aria-label="Photo view">
              <button aria-pressed={view === "boxes"} onClick={() => setView("boxes")}>Workers</button>
              <button aria-pressed={view === "heat"} onClick={() => setView("heat")}>Heat map</button>
            </div>
          </div>
          {(r.caption || r.privacy?.faces_blurred) ? (
            <figcaption>
              {r.caption && <p>&ldquo;{r.caption}&rdquo; <span>Florence-2 scene caption, used as context only</span></p>}
              {r.privacy?.faces_blurred ? <p><span>{r.privacy.faces_blurred} face{r.privacy.faces_blurred > 1 ? "s" : ""} blurred in the saved copy. The checks ran on the original photo.</span></p> : null}
            </figcaption>
          ) : null}
        </figure>

        <div className="pane">
          <div className="tabs no-print" role="tablist" aria-label="Result details">
            {tabs.map(([k, label, n]) => (
              <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>
                {label}{n != null && <span className="count">{n}</span>}
              </button>
            ))}
          </div>

          <div className="pane-body" role="tabpanel">
            {tab === "workers" && (
              r.workers.length === 0 ? <p className="muted">No workers detected.</p> : (
                <>
                  <ul className="people">
                    {r.workers.map((w, i) => {
                      const miss = missingItems(w);
                      const tone = workerTone(w);
                      return (
                        <li key={i} className={hover === i ? "on" : ""} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                          <span className={`num num-${tone}`}>{i + 1}</span>
                          <div className="person">
                            <strong>{miss.length ? `Missing ${miss.map((k) => PPE_LABEL[k].toLowerCase()).join(" and ")}` : tone === "warn" ? "Some items unclear" : "All checked items worn"}</strong>
                            <span>{w.source === "head-only" ? "Only the head is visible" : `Detected with ${Math.round(w.person_conf * 100)}% confidence`}</span>
                          </div>
                          <div className="kit">
                            {items.map((k) => {
                              const s = w[k] ?? "n/a"; const c = w[`${k}_conf` as const];
                              const tip = `${PPE_LABEL[k]}: ${STATE_TEXT[s]}${c != null && s !== "n/a" ? ` (${Math.round(c * 100)}%)` : ""}`;
                              return <span key={k} className={`kit-i kit-${s === "n/a" ? "na" : s}`} title={tip}><PpeIcon item={k} /><span className="visually-hidden">{tip}</span></span>;
                            })}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                  <p className="kit-key">
                    {items.map((k) => <span key={k}><PpeIcon item={k} />{PPE_LABEL[k]}</span>)}
                  </p>
                  <p className="kit-key">
                    <span><i className="sw sw-yes" />worn</span><span><i className="sw sw-no" />missing</span>
                    <span><i className="sw sw-unsure" />unclear</span><span><i className="sw sw-na" />not visible</span>
                  </p>
                </>
              )
            )}

            {tab === "report" && (
              <>
                <CheckScore s={r.check_summary} />
                <CheckedText text={r.report} checks={r.checks} />
                <CheckLegend />
                <Source>Written by the language model from the findings, the retrieved rules and the predicted risk only, then checked sentence by sentence by a DeBERTa NLI model.</Source>
              </>
            )}

            {tab === "risk" && r.risk && (
              <>
                <RiskBars risk={r.risk} />
                <Source>DistilBERT classifier fine-tuned on OSHA Severe Injury Reports, reading a description of the scene.</Source>
              </>
            )}

            {tab === "rules" && (
              <>
                <RuleList rules={r.rules} openFirst />
                <Source>Hybrid search over OSHA 29 CFR 1926 and UAE construction safety documents.</Source>
              </>
            )}

            {tab === "similar" && r.similar && (
              <>
                <SimilarList items={r.similar} />
                <Source>Nearest OSHA injury reports by meaning (sentence embeddings, FAISS index).</Source>
              </>
            )}

            {tab === "timing" && (
              <>
                <Timeline t={r.timings} />
                <Source>Measured by the backend for this photo.</Source>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Printed PDF: every section in order, since tabs do not print */}
      <div className="print-only">
        <h3>Report</h3><CheckedText text={r.report} checks={r.checks} />
        {r.risk && <><h3>Likely accident</h3><RiskBars risk={r.risk} /></>}
        <h3>Rules that apply</h3><RuleList rules={r.rules} />
      </div>
    </div>
  );
}
