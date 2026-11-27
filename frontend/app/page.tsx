"use client";
// Inspect a photo: upload it, run the full pipeline with one call to FastAPI /analyze, show the result.
import { useCallback, useEffect, useRef, useState } from "react";
import { analyze, imageUrl, type Result, type SceneCheck } from "@/lib/api";
import ResultView from "@/components/ResultView";
import { IconUpload } from "@/components/Icons";

export default function InspectPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [factCheck, setFactCheck] = useState(true);
  const [drag, setDrag] = useState(false);
  const [notSite, setNotSite] = useState<SceneCheck | null>(null);   // the scene check said: not a work site
  const input = useRef<HTMLInputElement>(null);

  // Wall-clock time of the running request. The per-step times are shown from the server's own measurements afterwards.
  useEffect(() => {
    if (!busy) return;
    const t0 = performance.now();
    const id = setInterval(() => setElapsed((performance.now() - t0) / 1000), 100);
    return () => clearInterval(id);
  }, [busy]);

  const pick = useCallback((f: File | undefined) => {
    if (!f) return;
    if (!f.type.startsWith("image/")) { setError("That file is not a photo. Choose a JPG or PNG."); return; }
    setFile(f); setResult(null); setError(null); setNotSite(null); setPreview(URL.createObjectURL(f));
  }, []);

  async function run(force = false) {
    if (!file) return;
    setBusy(true); setError(null); setNotSite(null); setElapsed(0);
    try { setResult(await analyze(file, factCheck, force)); }
    catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      let scene: (SceneCheck & { code?: string }) | null = null;
      try { scene = JSON.parse(msg); } catch {}
      if (scene?.code === "not_a_site") setNotSite(scene);
      else setError(`Inspection failed: ${msg}`);
    }
    finally { setBusy(false); }
  }

  return (
    <>
      <div className="intro">
        <h1>Inspect a site photo</h1>
        <p>Finds every worker, checks their hard hat, vest, gloves and safety glasses, and writes a report that cites the rules and is fact-checked sentence by sentence.</p>
      </div>

      <section className={`drop ${drag ? "drop-on" : ""} ${preview ? "drop-has" : ""} no-print`}
               onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
               onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}>
        <button className="drop-pick" onClick={() => input.current?.click()} aria-label={file ? "Choose a different photo" : "Choose a photo"}>
          {preview ? <img src={preview} alt="" /> : <span className="drop-icon"><IconUpload /></span>}
          <span className="drop-text">
            <strong>{file ? file.name : "Drop a site photo, or click to browse"}</strong>
            <span>{file ? "Click to choose a different photo" : "JPG or PNG from a construction or industrial site"}</span>
          </span>
        </button>
        <input ref={input} type="file" accept="image/*" hidden onChange={(e) => pick(e.target.files?.[0])} />
        <div className="drop-actions">
          <label className="check"><input type="checkbox" checked={factCheck} onChange={(e) => setFactCheck(e.target.checked)} /> Fact-check report</label>
          <button className="btn" disabled={!file || busy} onClick={() => run()}>{busy ? `Inspecting ${elapsed.toFixed(1)}s` : "Inspect"}</button>
        </div>
      </section>

      {busy && (
        <p className="running" aria-live="polite">
          The backend is running the detector, worker matching, accident classifier, rule search{factCheck ? ", report writer and fact checker" : " and report writer"}.
          The time of each step is shown with the result.
        </p>
      )}
      {error && <p className="error">{error}</p>}
      {notSite && (
        <div className="notice" role="alert">
          <strong>This photo does not look like a work site.</strong>
          <p>The scene check matched it best to &ldquo;{notSite.best_match.replace(/^a (photo of )?/, "")}&rdquo; (work-site score {Math.round(notSite.site_score * 100)}%, threshold {Math.round(notSite.threshold * 100)}%). PPE rules apply to construction and industrial sites, so the check was not run.</p>
          <div className="row">
            <button className="btn" onClick={() => input.current?.click()}>Choose another photo</button>
            <button className="btn btn-ghost" onClick={() => run(true)}>Analyse anyway</button>
          </div>
        </div>
      )}

      {result?.scene && !result.scene.is_site && (
        <p className="notice">Analysed on request although the scene check did not recognise a work site (score {Math.round(result.scene.site_score * 100)}%). Treat the results with care.</p>
      )}
      {result && <ResultView r={result} imageSrc={imageUrl(result.id)} />}
    </>
  );
}
