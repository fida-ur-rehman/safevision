"""SafeVision rule search (N4): hybrid BM25 + dense retrieval with reciprocal rank fusion and a cross-encoder re-ranker.

Loads the index written by Notebook 4 (chunks.parquet, chunks.faiss, config.json).
The same code runs in Notebook 5 and in the web app backend, so the app behaves like the evaluated system.
Design follows Guo et al. 2025 (EC3, hybrid RAG) [10] and Zhang et al. 2025 (BifrostRAG) [9];
RRF from Cormack et al. 2009.
"""
import json, re
from pathlib import Path

import numpy as np
import pandas as pd

STOP = set("a an the of to in on for and or with without is are was were be by at from this that it as any all no not".split())


def tokenize(text):
    """Lower-case word tokens without stop words (used by BM25)."""
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


class RuleSearch:
    """Hybrid rule search over the regulation chunks built in Notebook 4."""

    def __init__(self, index_dir, device="cpu", use_reranker=True, emb_model=None, reranker=None):
        import faiss
        from rank_bm25 import BM25Okapi
        from sentence_transformers import SentenceTransformer, CrossEncoder
        d = Path(index_dir)
        self.cfg = json.load(open(d / "config.json"))
        self.chunks = pd.read_parquet(d / "chunks.parquet").reset_index(drop=True)
        self.faiss = faiss.read_index(str(d / "chunks.faiss"))
        self.bm25 = BM25Okapi([tokenize(t) for t in self.chunks.text])
        emb_name = emb_model or self.cfg["emb_model"]
        self.emb = SentenceTransformer(emb_name, device=device)
        # bge embedding models expect this instruction in front of short queries
        self.prefix = "Represent this sentence for searching relevant passages: " if "bge" in emb_name else ""
        # on a GPU the re-ranker is loaded in fp16 (half the memory, much faster; same ranking in practice)
        half = {"model_kwargs": {"torch_dtype": __import__("torch").float16}} if str(device).startswith("cuda") else {}
        self.reranker = CrossEncoder(reranker or self.cfg["reranker"], device=device, **half) if use_reranker else None
        self.rrf_k = self.cfg.get("rrf_k", 60)
        self.candidates = self.cfg.get("candidates", 20)

    def _bm25(self, q, k):
        return list(np.argsort(-self.bm25.get_scores(tokenize(q)))[:k])

    def _dense(self, q, k):
        v = self.emb.encode([self.prefix + q], normalize_embeddings=True).astype("float32")
        return [int(i) for i in self.faiss.search(v, k)[1][0] if i >= 0]

    def _hybrid(self, q, k):
        # Reciprocal rank fusion: score = sum over lists of 1 / (rrf_k + rank)
        scores = {}
        for ranked in (self._bm25(q, self.candidates), self._dense(q, self.candidates)):
            for rank, idx in enumerate(ranked):
                scores[idx] = scores.get(idx, 0.0) + 1.0 / (self.rrf_k + rank + 1)
        return sorted(scores, key=scores.get, reverse=True)[:k]

    def search_ids(self, query, k=3):
        """Row numbers of the best k chunks (hybrid, then re-ranked if a re-ranker is loaded)."""
        cand = self._hybrid(query, self.candidates)
        if self.reranker is not None and cand:
            s = self.reranker.predict([(query, self.chunks.text[i]) for i in cand])
            cand = [cand[i] for i in np.argsort(-np.asarray(s))]
        return cand[:k]

    def search(self, query, k=3, unique_sections=True):
        """Top rules as dicts: section, heading, source, text. One chunk per section by default."""
        out, seen = [], set()
        for i in self.search_ids(query, k=k * 3 if unique_sections else k):
            row = self.chunks.iloc[i]
            if unique_sections and row.section in seen:
                continue
            seen.add(row.section)
            out.append({"section": str(row.section), "heading": str(row.heading), "source": str(row.source), "text": str(row.text)})
            if len(out) == k:
                break
        return out
