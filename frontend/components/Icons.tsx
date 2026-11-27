// Line icons and PPE pictograms on a 24 px grid, so the app needs no icon package.
import type { ReactElement } from "react";
import type { PpeItem } from "@/lib/api";

const base = { width: 16, height: 16, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.9,
               strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };

export const IconUpload = () => <svg {...base} width={22} height={22}><path d="M12 15V4M7.5 8.5 12 4l4.5 4.5M4 15v3.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V15" /></svg>;
export const IconPrint = () => <svg {...base}><path d="M7 9V3.5h10V9M7 17H4.5V10h15v7H17" /><path d="M7 14h10v6.5H7z" /></svg>;

// Brand mark: a hard hat
export const IconMark = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden>
    <rect width="24" height="24" rx="6" fill="#111" />
    <path d="M5.5 16h13M7 16a5 5 0 0 1 10 0M12 11V9.4" stroke="#ffd60a" strokeWidth="2" fill="none" strokeLinecap="round" />
  </svg>
);

const GLYPH: Record<PpeItem, ReactElement> = {
  helmet: <path d="M3.5 16.5h17M5.5 16.5a6.5 6.5 0 0 1 13 0M12 10V7.5" />,
  vest: <path d="M8.5 3.5 5 6v14h5l2-3.6 2 3.6h5V6l-3.5-2.5L12 8.5z" />,
  gloves: <path d="M7.5 20.5v-7L5.6 10a1.2 1.2 0 0 1 2-1.3l1.4 1.9V4.8a1.2 1.2 0 0 1 2.4 0V10m0-5.6a1.2 1.2 0 0 1 2.4 0V10m0-4.3a1.2 1.2 0 0 1 2.4 0v4.8m0-2.7a1.2 1.2 0 0 1 2.4 0V14a6 6 0 0 1-2.6 4.9v1.6" />,
  glasses: <path d="M2.5 10.5h19M4 10.5l.7 3.8a1.9 1.9 0 0 0 1.9 1.6h2.2a1.9 1.9 0 0 0 1.8-1.3l.6-1.8h1.6l.6 1.8a1.9 1.9 0 0 0 1.8 1.3h2.2a1.9 1.9 0 0 0 1.9-1.6l.7-3.8" />,
};

export function PpeIcon({ item }: { item: PpeItem }) {
  return <svg {...base} width={18} height={18}>{GLYPH[item]}</svg>;
}
