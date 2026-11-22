"use client";
// One inspection result: verdict, photo (boxes or heat map), workers with PPE status, report, risk, rules, similar accidents.
import { useState } from "react";
import { heatmapUrl, missingItems, PPE_ITEMS, PPE_LABEL, workerTone, type Result } from "@/lib/api";
import { CHECK_NOTE, CheckScore, CheckedText, RiskBars, RuleList, SimilarList, StatusChip, Timeline } from "./Shared";

const STROKE = { bad: "#c42b1c", warn: "#d48a00", ok: "#17a35f" } as const;

function verdict(r: Result) {
  if (!r.counts.workers) return { title: "No workers found in this photo", sub: "Nothing to check. Try a photo where workers are clearly visible." };
  if (!r.violation) return { title: "All visible PPE is in place", sub: `${r.counts.workers} worker${r.counts.workers > 1 ? "s" : ""} checked.` };
  const missing = r.workers.filter((w) => missingItems(w).length).length;
  return { title: `${missing} of ${r.counts.workers} workers are missing PPE`, sub: "Details for each worker are listed next to the photo." };
}

export default function ResultView({ r, imageSrc }: { r: Result; imageSrc: string }) {
  const [view, setView] = useState<"boxes" | "heat">("boxes");
  const [hover, setHover] = useState<number | null>(null);
  const [heatErr, setHeatErr] = useState(false);
  const v = verdict(r);
  const stroke = Math.max(2, Math.round(r.width / 320));
  const checks8 = r.workers.some((w) => w.gloves && w.gloves !== "n/a");
  const c = r.counts;

  return (
    <div>
      <section className={`verdict ${r.violation ? "verdict-bad" : "verdict-ok"}`} aria-live="polite">
        <div><h2>{v.title}</h2><p>{v.sub}</p></div>
        <button className="btn btn-quiet no-print" onClick={() => window.print()}>Export as PDF</button>
      </section>

      <div className="inspect">
        <div>
          <div className="canvas-bar">
            <span className="small muted">{view === "boxes" ? "Hover a worker to see their PPE." : "Red = where the detector looked most (EigenCAM)."}</span>
            <div className="seg" role="group" aria-label="Photo view">
              <button aria-pressed={view === "boxes"} onClick={() => setView("boxes")}>Workers</button>
              <button aria-pressed={view === "heat"} onClick={() => setView("heat")}>Heat map</button>
            </div>
          </div>
          <div className="canvas-wrap">
            {view === "boxes" ? (
              <svg viewBox={`0 0 ${r.width} ${r.height}`} role="img" aria-label="Photo with numbered worker boxes">
                <image href={imageSrc} width={r.width} height={r.height} />
                {r.workers.map((w, i) => {
                  const [x1, y1, x2, y2] = w.box; const col = STROKE[workerTone(w)]; const s = stroke * 10;
                  return (
                    <g key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                      <rect x={x1} y={y1} width={x2 - x1} height={y2 - y1} fill={hover === i ? `${col}30` : "none"} stroke={col} strokeWidth={hover === i ? stroke * 1.8 : stroke} />
                      <rect x={x1} y={Math.max(0, y1 - s)} width={s * 1.15} height={s} fill={col} rx={stroke} />
                      <text x={x1 + s * 0.57} y={Math.max(0, y1 - s) + s * 0.74} fontSize={s * 0.72} fill="#fff" fontWeight={700} textAnchor="middle">{i + 1}</text>
                    </g>
                  );
                })}
              </svg>
            ) : heatErr ? (
              <p className="empty" style={{ margin: 16 }}>The heat map could not be made (is the detector loaded in the backend?).</p>
            ) : (
              <img src={heatmapUrl(r.id)} alt="Detector attention heat map over the photo" onError={() => setHeatErr(true)} />
            )}
          </div>
          {(r.caption || r.privacy?.faces_blurred) && (
            <p className="canvas-note">
              {r.caption && <><b>Scene description (AI):</b> {r.caption} </>}
              {r.privacy?.faces_blurred ? <span className="muted">{r.caption ? <br /> : null}{r.privacy.faces_blurred} face{r.privacy.faces_blurred > 1 ? "s" : ""} blurred to protect worker privacy. PPE checks used the original photo.</span> : null}
            </p>
          )}
        </div>

        <div className="panel">
          <div className="tally">
            <div><b>{c.workers}</b><span>workers</span></div>
            <div className={c.no_helmet ? "t-bad" : ""}><b>{c.no_helmet}</b><span>no hard hat</span></div>
            <div className={c.no_vest ? "t-bad" : ""}><b>{c.no_vest}</b><span>no vest</span></div>
            {checks8 && <div className={c.no_gloves ? "t-bad" : ""}><b>{c.no_gloves ?? 0}</b><span>bare hands</span></div>}
            {checks8 && <div className={c.no_glasses ? "t-bad" : ""}><b>{c.no_glasses ?? 0}</b><span>no glasses</span></div>}
          </div>
          <h2>Workers</h2>
          {r.workers.length === 0 ? <p className="muted">No workers detected.</p> : (
            <ul className="workers">
              {r.workers.map((w, i) => (
                <li key={i} className={hover === i ? "on" : ""} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                  <span className={`wnum wnum-${workerTone(w)}`}>{i + 1}</span>
                  <div>
                    <div className="wchips">
                      {PPE_ITEMS.filter((k) => (w[k] ?? "n/a") !== "n/a").map((k) => <StatusChip key={k} label={PPE_LABEL[k]} status={w[k] ?? "n/a"} />)}
                    </div>
                    <div className="wmeta">{w.source === "head-only" ? "Only the head is visible" : `Person found with ${Math.round(w.person_conf * 100)}% confidence`}</div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="cols-2" style={{ marginTop: 16 }}>
        <section className="panel">
          <div className="panel-head"><h2>Incident report</h2><CheckScore s={r.check_summary} /></div>
          <CheckedText text={r.report} checks={r.checks} />
          <p className="small muted" style={{ marginTop: 12 }}>{CHECK_NOTE}</p>
        </section>
        <div>
          {r.risk && (
            <section className="panel">
              <h2>Likely accident if nothing changes</h2>
              <p className="small muted">Predicted from real OSHA construction injury reports.</p>
              <RiskBars risk={r.risk} />
            </section>
          )}
          <section className="panel">
            <h2>Rules that apply</h2>
            <RuleList rules={r.rules} />
          </section>
        </div>
      </div>

      {r.similar && r.similar.length > 0 && (
        <section className="panel" style={{ marginTop: 16 }}>
          <h2>Similar real accidents</h2>
          <SimilarList items={r.similar} />
        </section>
      )}

      <section className="panel" style={{ marginTop: 16 }}>
        <h2>How long each step took</h2>
        <Timeline t={r.timings} />
      </section>
    </div>
  );
}
