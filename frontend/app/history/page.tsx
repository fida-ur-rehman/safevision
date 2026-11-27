"use client";
// History: every inspected photo saved by the backend (SQLite), newest first.
import Link from "next/link";
import { useEffect, useState } from "react";
import { deleteIncident, imageUrl, listIncidents, type IncidentRow } from "@/lib/api";

export default function HistoryPage() {
  const [rows, setRows] = useState<IncidentRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "violations">("all");

  useEffect(() => { listIncidents().then(setRows).catch((e) => setError(`Could not load the history: ${e.message ?? e}`)); }, []);

  async function remove(id: string) {
    if (!confirm("Delete this inspection? This cannot be undone.")) return;
    await deleteIncident(id);
    setRows((r) => r?.filter((x) => x.id !== id) ?? null);
  }
  const shown = (rows ?? []).filter((r) => filter === "all" || r.violation);
  const nViol = (rows ?? []).filter((r) => r.violation).length;

  return (
    <>
      <div className="intro intro-row">
        <div><h1>History</h1><p>Every inspected photo, newest first, stored by the backend. Open one to see its full result.</p></div>
        <div className="seg" role="group" aria-label="Filter">
          <button aria-pressed={filter === "all"} onClick={() => setFilter("all")}>All ({rows?.length ?? 0})</button>
          <button aria-pressed={filter === "violations"} onClick={() => setFilter("violations")}>With violations ({nViol})</button>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      {rows && shown.length === 0 && <p className="muted">No inspections yet. <Link href="/">Inspect a photo</Link> to start one.</p>}
      {shown.length > 0 && (
        <table className="log">
          <thead><tr><th>Photo</th><th>Date</th><th>Workers</th><th>Result</th><th><span className="visually-hidden">Actions</span></th></tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id}>
                <td><Link href={`/incidents/${r.id}`}><img className="thumb" src={imageUrl(r.id)} alt={r.filename} loading="lazy" /></Link></td>
                <td><Link href={`/incidents/${r.id}`}>{new Date(r.created).toLocaleString()}</Link><div className="muted">{r.filename}</div></td>
                <td>{r.workers}</td>
                <td>{r.violation
                  ? <span className="tag tag-bad">{[r.no_helmet && `${r.no_helmet} no hard hat`, r.no_vest && `${r.no_vest} no vest`].filter(Boolean).join(", ") || "PPE missing"}</span>
                  : <span className="tag tag-ok">PPE in place</span>}</td>
                <td><button className="link-btn" onClick={() => remove(r.id)}>Delete</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
