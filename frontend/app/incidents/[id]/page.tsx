"use client";
// One saved inspection, opened from History.
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getIncident, imageUrl, type Result } from "@/lib/api";
import ResultView from "@/components/ResultView";

export default function SavedInspection() {
  const { id } = useParams<{ id: string }>();
  const [r, setR] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { getIncident(id).then(setR).catch((e) => setError(`Could not open this inspection: ${e.message ?? e}`)); }, [id]);
  return (
    <>
      <div className="intro">
        <p className="crumb no-print"><Link href="/history">History</Link></p>
        <h1>{r ? r.filename : "Inspection"}</h1>
        {r && <p>Inspected {new Date(r.created).toLocaleString()}</p>}
      </div>
      {error && <p className="error">{error}</p>}
      {r ? <ResultView r={r} imageSrc={imageUrl(r.id)} /> : !error && <p className="muted">Loading…</p>}
    </>
  );
}
