"""SafeVision fact checker (N5b): checks every sentence of a generated report against the evidence with an NLI model.

A sentence is 'supported' if at least one evidence piece entails it, 'contradicted' if a finding contradicts it,
otherwise 'unsupported'. Rule citations (e.g. 1926.100) are also checked against the retrieved rules,
so invented section numbers are caught. Idea: grounding checks for RAG answers as discussed in [9], [10], [13].
"""
import re

CITE_RE = re.compile(r"\b(19\d\d\.\d+[a-z]?)\b")
HEADING_RE = re.compile(r"^\s*(?:#+\s*)?\**([A-Z][A-Za-z /&-]{2,40}):\**\s*(.*)$")


def split_sentences(report, skip_sections=("corrective actions",)):
    """Report text -> list of checkable sentences.

    Headings, bullet markers and very short lines are removed. Sentences under `skip_sections`
    are advice, not factual claims, so they are not checked.
    """
    out, section = [], ""
    for line in report.splitlines():
        line = line.strip()
        m = HEADING_RE.match(line)
        if m:                                                    # a heading, maybe followed by text on the same line
            section, line = m.group(1).strip().lower(), m.group(2).strip()
        if not line or section in skip_sections:
            continue
        line = re.sub(r"^([-*\u2022]|\d+[.)])\s*", "", line)      # drop bullet / numbering
        for s in re.split(r"(?<=[.!?])\s+", line):
            if len(s.split()) >= 4:
                out.append(s.strip())
    return out


def cited_sections(text):
    """All regulation section numbers cited in a text."""
    return sorted(set(CITE_RE.findall(text)))


class FactChecker:
    """NLI cross-encoder (default: cross-encoder/nli-deberta-v3-base) used as a sentence-level checker."""

    def __init__(self, model="cross-encoder/nli-deberta-v3-base", device="cpu", entail_min=0.5, contra_min=0.5):
        from sentence_transformers import CrossEncoder
        # fp16 on the GPU (loaded directly in fp16, so it never needs the full fp32 memory on the GPU)
        half = {"model_kwargs": {"torch_dtype": __import__("torch").float16}} if str(device).startswith("cuda") else {}
        self.nli = CrossEncoder(model, device=device, **half)
        names = {i: str(l).lower() for i, l in (self.nli.model.config.id2label or {}).items()}
        find = lambda key, default: next((i for i, n in names.items() if key in n), default)
        # documented label order of the cross-encoder NLI models: contradiction, entailment, neutral
        self.i_con, self.i_ent = find("contra", 0), find("entail", 1)
        self.entail_min, self.contra_min = entail_min, contra_min

    def _probs(self, pairs):
        import numpy as np
        logits = np.asarray(self.nli.predict(pairs, batch_size=32))
        if logits.ndim == 1:
            logits = logits[None, :]
        e = np.exp(logits - logits.max(axis=1, keepdims=True))
        return e / e.sum(axis=1, keepdims=True)

    def check(self, report, evidence, findings=None, allowed_sections=None):
        """Label every sentence of `report`.

        evidence: list of evidence texts (findings sentences, retrieved rule chunks, risk sentences).
        findings: subset of evidence that states hard facts from the photo (used for contradictions).
        allowed_sections: section numbers that were retrieved; other citations count as invented.
        """
        findings = findings or []
        allowed = set(allowed_sections or [])
        results = []
        sentences = split_sentences(report)
        n_f = [i for i, ev in enumerate(evidence) if ev in findings]
        # all (evidence, sentence) pairs in ONE batch: much faster than one model call per sentence
        all_p = self._probs([(ev, s) for s in sentences for ev in evidence]) if (sentences and evidence) else None
        for k, s in enumerate(sentences):
            p = all_p[k * len(evidence):(k + 1) * len(evidence)] if all_p is not None else None
            ent = float(p[:, self.i_ent].max()) if p is not None else 0.0
            best = evidence[int(p[:, self.i_ent].argmax())] if p is not None else ""
            con = float(p[n_f, self.i_con].max()) if (p is not None and n_f) else 0.0
            bad_cites = [c for c in cited_sections(s) if allowed and c not in allowed]
            if bad_cites:
                label = "invented citation"
            elif con >= self.contra_min and ent < self.entail_min:
                label = "contradicted"
            elif ent >= self.entail_min:
                label = "supported"
            else:
                label = "unsupported"
            results.append({"sentence": s, "label": label, "entail": round(ent, 3), "contra": round(con, 3),
                            "best_evidence": best[:200], "bad_citations": bad_cites})
        return results


def summarise(checks, report=""):
    """Share of supported / unsupported / contradicted sentences and citation precision for one report."""
    n = max(len(checks), 1)
    cites = cited_sections(report)
    bad = sorted({c for r in checks for c in r["bad_citations"]})
    return {"sentences": len(checks),
            "supported_pct": 100 * sum(r["label"] == "supported" for r in checks) / n,
            "unsupported_pct": 100 * sum(r["label"] == "unsupported" for r in checks) / n,
            "contradicted_pct": 100 * sum(r["label"] == "contradicted" for r in checks) / n,
            "citations": len(cites), "invented_citations": len(bad),
            "citation_precision": (len(cites) - len(bad)) / len(cites) if cites else float("nan")}
