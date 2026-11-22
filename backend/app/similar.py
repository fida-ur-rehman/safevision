"""SafeVision similar-accident search (N3): the k most similar real OSHA construction accidents for a situation.

Loads the index written by Notebook 3 (similar_accidents.faiss, similar_accidents_meta.parquet,
similar_accidents_config.json). Search runs on the context-only text (outcome words removed), the same
way it was evaluated in experiment E7.
"""
import json, re
from pathlib import Path


class SimilarAccidents:
    def __init__(self, models_dir, device="cpu", masker=None):
        import faiss
        import pandas as pd
        from sentence_transformers import SentenceTransformer
        d = Path(models_dir)
        cfg = json.load(open(d / "similar_accidents_config.json"))
        self.index = faiss.read_index(str(d / "similar_accidents.faiss"))
        self.meta = pd.read_parquet(d / "similar_accidents_meta.parquet").reset_index(drop=True)
        self.emb = SentenceTransformer(cfg["emb_model"], device=device)
        self.masker = masker          # function text -> context-only text (from AccidentClassifier), optional

    def search(self, situation, k=3):
        """Top-k similar accidents as dicts: narrative, event_group, body_group, severity, year, score."""
        q = self.masker(situation) if self.masker else situation
        v = self.emb.encode([q], normalize_embeddings=True).astype("float32")
        scores, ids = self.index.search(v, k)
        out = []
        for s, i in zip(scores[0], ids[0]):
            if i < 0:
                continue
            row = self.meta.iloc[int(i)]
            out.append({"narrative": re.sub(r"\s+", " ", str(row.narrative)).strip()[:600],
                        "event_group": str(row.event_group), "body_group": str(row.body_group),
                        "severity": str(row.severity), "year": int(row.year), "score": round(float(s), 3)})
        return out
