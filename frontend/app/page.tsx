"use client";
// Inspect a photo: upload, run the full pipeline (FastAPI /analyze), show the result.
import { useCallback, useRef, useState } from "react";
import { analyze, imageUrl, type Result } from "@/lib/api";
import ResultView from "@/components/ResultView";
import { IconUpload } from "@/components/Icons";

const STEPS = ["Finding workers and PPE", "Matching PPE to each worker", "Predicting the likely accident",
               "Searching safety rules", "Writing the report", "Checking every sentence"];

export default function InspectPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);
  const [factCheck, setFactCheck] = useState(true);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const pick = useCallback((f: File | undefined) => {
    if (!f) return;
    if (!f.type.startsWith("image/")) { setError("That file is not a photo. Choose a JPG or PNG."); return; }
    setFile(f); setResult(null); setError(null); setPreview(URL.createObjectURL(f));
  }, []);

  async function run() {
    if (!file) return;
    setBusy(true); setError(null); setStep(0);
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 1500);   // feedback only; the API is one call
    try { setResult(await analyze(file, factCheck)); }
    catch (e) { setError(`Inspection failed: ${e instanceof Error ? e.message : String(e)}`); }
    finally { clearInterval(timer); setBusy(false); }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Inspect a site photo</h1>
          <p>SafeVision finds each worker, checks their hard hat, vest, gloves and safety glasses, and writes a report that cites the matching safety rules.</p>
        </div>
      </header>

      <section className="panel no-print">
        <div className="upload">
          <div className={`drop ${drag ? "drop-on" : ""}`} role="button" tabIndex={0}
               onClick={() => input.current?.click()} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
               onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
               onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}>
            {preview ? <img src={preview} alt="" /> : <IconUpload />}
            <div>
              <strong>{file ? file.name : "Drop a site photo here, or click to choose one"}</strong>
              <div className="small muted">{file ? "Click to choose a different photo" : "JPG or PNG, any size"}</div>
            </div>
            <input ref={input} type="file" accept="image/*" hidden onChange={(e) => pick(e.target.files?.[0])} />
          </div>
          <div className="upload-actions">
            <button className="btn" disabled={!file || busy} onClick={run}>{busy ? "Inspecting…" : "Inspect photo"}</button>
            <label className="check small"><input type="checkbox" checked={factCheck} onChange={(e) => setFactCheck(e.target.checked)} /> Fact-check the report</label>
          </div>
        </div>
        {busy && (
          <ol className="progress" aria-live="polite">
            {STEPS.map((s, i) => <li key={s} className={i < step ? "done" : i === step ? "now" : ""}>{s}</li>)}
          </ol>
        )}
        {error && <p className="error" style={{ marginTop: 14 }}>{error}</p>}
      </section>

      {result ? <ResultView r={result} imageSrc={imageUrl(result.id)} /> :
        !busy && <p className="empty" style={{ marginTop: 16 }}>Results appear here: the photo with each worker marked, their PPE status, the report and the rules that apply.</p>}
    </>
  );
}
