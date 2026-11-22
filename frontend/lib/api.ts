// Typed client for the SafeVision FastAPI backend (Python). Next.js is only the web interface.

export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Status = "yes" | "no" | "unsure" | "n/a";
export const PPE_ITEMS = ["helmet", "vest", "gloves", "glasses"] as const;
export type PpeItem = (typeof PPE_ITEMS)[number];
export const PPE_LABEL: Record<PpeItem, string> = { helmet: "Hard hat", vest: "Hi-vis vest", gloves: "Gloves", glasses: "Safety glasses" };

export interface Worker {
  box: [number, number, number, number];
  source: "person" | "head-only";
  person_conf: number;
  helmet: Status; helmet_conf: number;
  vest: Status; vest_conf: number;
  gloves?: Status; gloves_conf?: number;
  glasses?: Status; glasses_conf?: number;
}

export interface Rule { section: string; heading: string; source: string; text: string }

export interface Check {
  sentence: string;
  label: "supported" | "unsupported" | "contradicted" | "invented citation";
  entail: number;
  contra: number;
  best_evidence: string;
  bad_citations: string[];
}

export interface CheckSummary {
  sentences: number; supported_pct: number; unsupported_pct: number; contradicted_pct: number;
  citations: number; invented_citations: number; citation_precision: number | null;
}

export interface Similar { narrative: string; event_group: string; body_group: string; severity: string; year: number; score: number }
export type Risk = Record<string, [string, number][]>;

export interface Counts {
  workers: number; no_helmet: number; helmet_unsure: number; helmet_ok: number; no_vest: number; vest_ok: number;
  no_gloves?: number; gloves_ok?: number; no_glasses?: number; glasses_ok?: number;
}

export interface Result {
  id: string;
  created: string;
  filename: string;
  width: number;
  height: number;
  workers: Worker[];
  counts: Counts;
  situation: string;
  caption?: string | null;
  facts: string[];
  risk: Risk | null;
  risk_sentences: string[];
  rules: Rule[];
  similar?: Similar[];
  report: string;
  checks: Check[];
  check_summary: CheckSummary | null;
  timings: Record<string, number>;
  violation: boolean;
  privacy?: { faces_blurred: number; blur_on: boolean };
}

export interface Explanation { words: string[]; scores: number[]; target: number; label: string; prob: number; method: string; ms: number }

export interface IncidentResult {
  text: string;
  context_text: string;
  hidden_words: string[];
  risk: Risk;
  risk_sentences: string[];
  explanation: Explanation | null;
  top_words: string[];
  similar: Similar[];
  rules: Rule[];
  report: string;
  checks: Check[];
  check_summary: CheckSummary | null;
  timings: Record<string, number>;
}

export interface IncidentRow { id: string; created: string; filename: string; violation: number; workers: number; no_helmet: number; no_vest: number }

export interface Answer { question: string; rules: Rule[]; answer: string | null; checks: Check[] }

export interface Health { status: string; device: string; components: Record<string, string> }

async function handle<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {}
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

const json = (body: unknown) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const analyze = (file: File, factCheck = true) => {
  const fd = new FormData();
  fd.append("file", file);
  return fetch(`${API}/analyze?fact_check=${factCheck}`, { method: "POST", body: fd }).then(handle<Result>);
};
export const analyzeIncident = (text: string, method?: string) =>
  fetch(`${API}/incident-analysis`, json({ text, method })).then(handle<IncidentResult>);
export const listIncidents = () => fetch(`${API}/incidents`).then(handle<IncidentRow[]>);
export const getIncident = (id: string) => fetch(`${API}/incidents/${id}`).then(handle<Result>);
export const deleteIncident = (id: string) => fetch(`${API}/incidents/${id}`, { method: "DELETE" }).then(handle<{ deleted: string }>);
export const imageUrl = (id: string) => `${API}/incidents/${id}/image`;
export const heatmapUrl = (id: string) => `${API}/incidents/${id}/heatmap`;
export const ask = (question: string) => fetch(`${API}/ask`, json({ question })).then(handle<Answer>);
export const health = () => fetch(`${API}/health`).then(handle<Health>);

// Worker-level helpers shared by several views
export function workerTone(w: Worker): "bad" | "warn" | "ok" {
  const s = PPE_ITEMS.map((k) => w[k] ?? "n/a");
  if (s.includes("no")) return "bad";
  if (s.includes("unsure")) return "warn";
  return "ok";
}
export const missingItems = (w: Worker) => PPE_ITEMS.filter((k) => w[k] === "no");
