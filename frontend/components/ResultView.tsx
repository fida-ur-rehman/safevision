"use client";
// One inspection result: verdict, photo with numbered workers (or the detector heat map), the per-worker PPE checklist,
// the checked report, predicted accident risk, rules and similar accidents, and the measured time of each step.
import { useState } from "react";
import { heatmapUrl, missingItems, PPE_ITEMS, PPE_LABEL, workerTone, type Result } from "@/lib/api";
import { PpeSign, IconPrint } from "./Icons";
import { CheckLegend, CheckScore, CheckedText, RiskBars, RuleList, Section, SimilarList, StatusMark, Timeline } from "./Shared";

const STROKE = { bad: "#c8102e", warn: "#d98c00", ok: "#13804a" } as const;

function verdict(r: Result) {
  if (!r.counts.workers) return { tone: "none", title: "No workers found", sub: "Nothing to check. Use a photo where the workers are clearly visible." };
  if (!r.violation) return { tone: "ok", title: "PPE in place", sub: `All checked items are worn by the ${r.counts.workers} worker${r.counts.workers > 1 ? "s" : ""} found.` };
  const missing = r.workers.filter((w) => missingItems(w).length).length;
  return { tone: "bad", title: "PPE missing", sub: `${missing} of ${r.counts.workers} workers are missing at least one item.` };
}

export default function ResultView({ r, imageSrc }: { r: Result; imageSrc: string }) {
  const [view, setView] = useState<"boxes" | "heat">("boxes");
  const [hover, setHover] = useState<number | null>(null);
  const [heatErr, setHeatErr] = useState(false);
  const v = verdict(r);
  const stroke = Math.max(2, Math.round(r.width / 320));
  const items = PPE_ITEMS.filter((k) => r.workers.some((w) => (w[k] ?? "n/a") !== "n/a"));

  return (
    <div className="result">
      <div className={`verdict verdict-${v.tone}`} aria-live="polite">
        <div>
          <h2>{v.title}</h2>
          <p>{v.sub}</p>
        </div>
        <button className="btn btn-line no-print" onClick={() => window.print()}><IconPrint /> Export PDF</button>
      </div>

      <div className="inspect">
        <figure className="photo">
          <div className="photo-bar no-print">
            <div className="seg" role="group" aria-label="Photo view">
              <button aria-pressed={view === "boxes"} onClick={() => setView("boxes")}>Workers</button>
              <button aria-pressed={view === "heat"} onClick={() => setView("heat")}>Detector heat map</button>
            </div>
            <span>{view === "boxes" ? "Point at a worker to find their row in the checklist." : "Warmer areas influenced the detector more (EigenCAM)."}</span>
          </div>
          {view === "boxes" ? (
            <svg viewBox={`0 0 ${r.width} ${r.height}`} role="img" aria-label="Photo with numbered worker boxes">
              <image href={imageSrc} width={r.width} height={r.height} />
              {r.workers.map((w, i) => {
                const [x1, y1, x2, y2] = w.box; const col = STROKE[workerTone(w)]; const s = stroke * 10;
                return (
                  <g key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                    <rect x={x1} y={y1} width={x2 - x1} height={y2 - y1} fill={hover === i ? `${col}33` : "none"} stroke={col} strokeWidth={hover === i ? stroke * 1.8 : stroke} />
                    <rect x={x1} y={Math.max(0, y1 - s)} width={s * 1.15} height={s} fill={col} />
                    <text x={x1 + s * 0.57} y={Math.max(0, y1 - s) + s * 0.76} fontSize={s * 0.74} fill="#fff" fontWeight={700} textAnchor="middle">{i + 1}</text>
                  </g>
                );
              })}
            </svg>
          ) : heatErr ? (
            <p className="photo-empty">The heat map could not be made. Check that the detector is loaded in the backend.</p>
          ) : (
            <img src={heatmapUrl(r.id)} alt="Detector attention heat map over the photo" onError={() => setHeatErr(true)} />
          )}
          {(r.caption || r.privacy?.faces_blurred) ? (
            <figcaption>
              {r.caption && <p><b>Scene caption (Florence-2, context only):</b> {r.caption}</p>}
              {r.privacy?.faces_blurred ? <p>{r.privacy.faces_blurred} face{r.privacy.faces_blurred > 1 ? "s" : ""} blurred in the saved copy. The checks ran on the original photo.</p> : null}
            </figcaption>
          ) : null}
        </figure>

        <section className="checklist" aria-label="PPE checklist per worker">
          <h2>Checklist</h2>
          {r.workers.length === 0 ? <p className="muted">No workers detected.</p> : (
            <table>
              <thead>
                <tr>
                  <th scope="col">Worker</th>
                  {items.map((k) => <th key={k} scope="col"><PpeSign item={k} /><span>{PPE_LABEL[k]}</span></th>)}
                </tr>
              </thead>
              <tbody>
                {r.workers.map((w, i) => (
                  <tr key={i} className={hover === i ? "on" : ""} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                    <th scope="row">
                      <span className={`wno wno-${workerTone(w)}`}>{i + 1}</span>
                      <small>{w.source === "head-only" ? "head only" : `person ${Math.round(w.person_conf * 100)}%`}</small>
                    </th>
                    {items.map((k) => <td key={k}><StatusMark status={w[k] ?? "n/a"} conf={w[`${k}_conf` as const]} /></td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="key">
            <StatusMark status="yes" /> worn <StatusMark status="no" /> missing <StatusMark status="unsure" /> unclear <StatusMark status="n/a" /> not visible.
            Hover a mark for the detector confidence.
          </p>
        </section>
      </div>

      <div className="split">
        <Section title="Incident report" aside={<CheckScore s={r.check_summary} />}
                 source="Written by the language model from the findings, the retrieved rules and the predicted risk only.">
          <CheckedText text={r.report} checks={r.checks} />
          <CheckLegend />
        </Section>
        <div>
          {r.risk && (
            <Section title="Likely accident if nothing changes" source="DistilBERT classifier fine-tuned on OSHA Severe Injury Reports.">
              <RiskBars risk={r.risk} />
            </Section>
          )}
          <Section title="Rules that apply" source="Hybrid search over OSHA 29 CFR 1926 and UAE construction safety documents.">
            <RuleList rules={r.rules} />
          </Section>
        </div>
      </div>

      {r.similar && r.similar.length > 0 && (
        <Section title="Similar real accidents" source="Nearest OSHA injury reports by meaning (sentence embeddings, FAISS index).">
          <SimilarList items={r.similar} />
        </Section>
      )}

      <Section title="Time per step" source="Measured by the backend for this photo.">
        <Timeline t={r.timings} />
      </Section>
    </div>
  );
}
