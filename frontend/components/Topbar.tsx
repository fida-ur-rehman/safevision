"use client";
// Top navigation and the live status of the FastAPI backend (read from /health, nothing is assumed).
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { health, type Health } from "@/lib/api";
import { IconMark } from "./Icons";

const NAV = [
  { href: "/", label: "Inspect" },
  { href: "/incident", label: "Incident analysis" },
  { href: "/ask", label: "Rules" },
  { href: "/history", label: "History" },
];

// Readable names for the components reported by /health
const COMPONENTS: Record<string, string> = {
  scene_check: "Scene check (CLIP)", detector: "PPE detector (YOLO11s)", pose: "Pose model", captioner: "Scene captions (Florence-2)",
  classifier: "Accident classifier (DistilBERT)", explainer: "Word explanations", similar_accidents: "Similar accidents (FAISS)",
  rules: "Rule search (BM25 + embeddings)", llm: "Report writer (LLM)", fact_checker: "Fact checker (DeBERTa NLI)",
};

export default function Topbar() {
  const path = usePathname();
  const [h, setH] = useState<Health | null>(null);
  const [down, setDown] = useState(false);
  useEffect(() => { health().then(setH).catch(() => setDown(true)); }, []);

  const comps = h ? Object.entries(h.components).filter(([k]) => k in COMPONENTS) : [];
  const ready = comps.filter(([, v]) => v === "ok").length;
  const tone = down ? "bad" : !h ? "idle" : ready === comps.length ? "ok" : "warn";
  const active = (href: string) =>
    href === "/" ? path === "/" : href === "/history" ? path.startsWith("/history") || path.startsWith("/incidents/") : path === href;

  return (
    <header className="topbar no-print">
      <div className="topbar-in">
        <Link href="/" className="brand"><IconMark /><span>SafeVision</span></Link>
        <nav aria-label="Main">
          {NAV.map(({ href, label }) => (
            <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}>{label}</Link>
          ))}
        </nav>
        <details className="sys">
          <summary>
            <span className={`led led-${tone}`} />
            {down ? "Backend offline" : !h ? "Connecting" : `${ready}/${comps.length} models on ${h.device.toUpperCase()}`}
          </summary>
          <div className="sys-pop">
            {h ? (
              <table>
                <tbody>
                  {comps.map(([k, v]) => (
                    <tr key={k}><td>{COMPONENTS[k]}</td><td className={v === "ok" ? "ok" : "bad"}>{v === "ok" ? "loaded" : v.startsWith("missing") ? "not installed" : "error"}</td></tr>
                  ))}
                  <tr><td>Report writer backend</td><td>{h.components.llm_backend ?? "template"}</td></tr>
                  {h.components.xai_method && <tr><td>Explanation method</td><td>{h.components.xai_method.toUpperCase()}</td></tr>}
                </tbody>
              </table>
            ) : (
              <p>Start the backend in the backend folder with <code>uvicorn app.main:app --port 8000</code>.</p>
            )}
          </div>
        </details>
      </div>
    </header>
  );
}
