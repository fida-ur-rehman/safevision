// Line icons and PPE pictograms drawn on a 24 px grid, so the app needs no icon package.
import type { ReactElement } from "react";
import type { PpeItem } from "@/lib/api";

const base = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8,
               strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };

export const IconUpload = () => <svg {...base} width={28} height={28}><path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" /></svg>;
export const IconPrint = () => <svg {...base}><path d="M7 9V3h10v6M7 17H4v-7h16v7h-3" /><path d="M7 14h10v7H7z" /></svg>;

// Brand mark: a hard hat inside the round "mandatory" sign used on construction sites
export const IconMark = () => (
  <svg width="30" height="30" viewBox="0 0 24 24" aria-hidden>
    <circle cx="12" cy="12" r="11" fill="#fff" />
    <circle cx="12" cy="12" r="9.4" fill="var(--sign)" />
    <path d="M6.2 15.2h11.6M7.4 15.2a4.6 4.6 0 0 1 9.2 0M12 9.8v-1.4" stroke="#fff" strokeWidth="1.7" fill="none" strokeLinecap="round" />
  </svg>
);

// PPE pictograms (white on the blue mandatory-sign disc)
const GLYPH: Record<PpeItem, ReactElement> = {
  helmet: <path d="M5.5 15.5h13M6.8 15.5a5.2 5.2 0 0 1 10.4 0M12 10.3V8.6" />,
  vest: <path d="M9 5l-3 2.2V19h4.2l1.8-3.2 1.8 3.2H18V7.2L15 5l-3 4.2z" />,
  gloves: <path d="M8 19v-6.5L6.6 9.8a1 1 0 0 1 1.7-1l1.2 1.6V5.6a1 1 0 0 1 2 0V10m0-4.9a1 1 0 0 1 2 0V10m0-3.8a1 1 0 0 1 2 0V10.5m0-2.4a1 1 0 0 1 2 0V14a5 5 0 0 1-2.2 4.1V19" />,
  glasses: <path d="M3.5 11h17M5 11l.6 3.2a1.6 1.6 0 0 0 1.6 1.3h1.9a1.6 1.6 0 0 0 1.5-1.1l.5-1.5h1.8l.5 1.5a1.6 1.6 0 0 0 1.5 1.1h1.9a1.6 1.6 0 0 0 1.6-1.3L19 11" />,
};

export function PpeSign({ item, size = 26 }: { item: PpeItem; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden className="ppe-sign">
      <circle cx="12" cy="12" r="11.5" fill="var(--sign)" />
      <g stroke="#fff" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round">{GLYPH[item]}</g>
    </svg>
  );
}
