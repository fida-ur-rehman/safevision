// Small line icons (24 px grid, 1.8 stroke) so the app needs no icon package.
const base = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8,
               strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };

export const IconInspect = () => <svg {...base}><path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" /><circle cx="12" cy="12" r="3.2" /></svg>;
export const IconIncident = () => <svg {...base}><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4M10 12h5M10 16h5" /></svg>;
export const IconRules = () => <svg {...base}><path d="M5 4h10a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z" /><path d="M5 17a3 3 0 0 1 3-3h10" /></svg>;
export const IconHistory = () => <svg {...base}><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5M12 7v5l3 2" /></svg>;
export const IconUpload = () => <svg {...base} width={26} height={26}><path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" /></svg>;
export const IconMark = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden><path d="M12 3 2.5 20h19z" fill="#1b2420" /><rect x="11" y="9" width="2" height="6" fill="#ffd60a" /><rect x="11" y="16.5" width="2" height="2" fill="#ffd60a" /></svg>
);
