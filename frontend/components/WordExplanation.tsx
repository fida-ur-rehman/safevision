// Word-level explanation: each word is shaded by how much it pushed the model towards (green) or away from (red) its prediction.
import type { Explanation } from "@/lib/api";

export default function WordExplanation({ e, hidden }: { e: Explanation; hidden: string[] }) {
  const max = Math.max(1e-9, ...e.scores.map(Math.abs));
  return (
    <div>
      <p className="words">
        {e.words.map((w, i) => {
          const s = e.scores[i] ?? 0; const a = Math.min(1, Math.abs(s) / max) * 0.6;
          const bg = s > 0 ? `rgba(19,128,74,${a})` : `rgba(200,16,46,${a})`;
          return <span key={i}><span className="w" style={{ background: a > 0.03 ? bg : undefined }} title={`${w}: ${s.toFixed(3)}`}>{w}</span> </span>;
        })}
      </p>
      <div className="legend-scale">
        <span>Pushes away</span><span className="grad" aria-hidden /><span>Pushes towards &ldquo;{e.label}&rdquo;</span>
        <span>Method: {e.method.toUpperCase()}, {e.ms >= 1000 ? `${(e.ms / 1000).toFixed(1)} s` : `${Math.round(e.ms)} ms`}</span>
      </div>
      {hidden.length > 0 && (
        <div className="hidden-words">
          <span className="muted">Hidden from the model on purpose (outcome and how-it-happened words):</span>
          {hidden.map((w) => <s key={w}>{w}</s>)}
        </div>
      )}
    </div>
  );
}
