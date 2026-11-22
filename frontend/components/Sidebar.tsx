"use client";
// Left navigation + live status of the FastAPI backend and its models.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { health, type Health } from "@/lib/api";
import { IconHistory, IconIncident, IconInspect, IconMark, IconRules } from "./Icons";

const NAV = [
  { href: "/", label: "Inspect a photo", icon: IconInspect },
  { href: "/incident", label: "Incident analysis", icon: IconIncident },
  { href: "/ask", label: "Rules assistant", icon: IconRules },
  { href: "/history", label: "History", icon: IconHistory },
];

// Friendly names for the backend components listed by /health
const COMPONENTS: Record<string, string> = {
  detector: "PPE detector", pose: "Pose model", classifier: "Accident classifier", explainer: "Word explanations",
  rules: "Rule search", similar_accidents: "Similar accidents", captioner: "Scene captions", fact_checker: "Fact checker", llm: "Report writer",
};

export default function Sidebar() {
  const path = usePathname();
  const [h, setH] = useState<Health | null>(null);
  const [down, setDown] = useState(false);
  useEffect(() => { health().then(setH).catch(() => setDown(true)); }, []);

  const comps = h ? Object.entries(h.components).filter(([k]) => k in COMPONENTS) : [];
  const ready = comps.filter(([, v]) => v === "ok").length;
  const tone = down ? "dot-bad" : !h ? "" : ready === comps.length ? "dot-ok" : "dot-warn";
  const active = (href: string) =>
    href === "/" ? path === "/" : href === "/history" ? path.startsWith("/history") || path.startsWith("/incidents/") : path === href;

  return (
    <aside className="side no-print">
      <Link href="/" className="brand"><span className="brand-mark"><IconMark /></span>SafeVision</Link>
      <nav className="nav" aria-label="Main">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}><Icon />{label}</Link>
        ))}
      </nav>
      <div className="side-foot">
        <details>
          <summary className="status-line">
            <span className={`dot ${tone}`} />
            {down ? "Backend offline" : !h ? "Connecting…" : `${ready} of ${comps.length} models ready`}
          </summary>
          {h && (
            <ul className="comp-list">
              {comps.map(([k, v]) => <li key={k}><span>{COMPONENTS[k]}</span><span>{v === "ok" ? "ready" : v.startsWith("missing") ? "not installed" : "error"}</span></li>)}
              <li><span>Runs on</span><span>{h.device.toUpperCase()}</span></li>
              <li><span>Report writer</span><span>{h.components.llm_backend ?? "template"}</span></li>
              {h.components.xai_method && <li><span>Explanation method</span><span>{h.components.xai_method.toUpperCase()}</span></li>}
            </ul>
          )}
          {down && <p className="small" style={{ marginTop: 8 }}>Start it with: uvicorn app.main:app --port 8000 (in the backend folder).</p>}
        </details>
        <p className="small" style={{ marginTop: 14 }}>MAAI project, UOWD. Always confirm findings with a qualified safety officer.</p>
      </div>
    </aside>
  );
}
