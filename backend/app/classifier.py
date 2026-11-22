"""SafeVision accident-type classifier (N2): loads the context-only multi-task DistilBERT saved by Notebook 3.

Predicts the likely accident type (OIICS event group), injured body-part group and severity for a
situation description, following Wang et al. 2025 [6] (OIICS groups, DistilBERT) and Cao et al. 2026 [7].
"""
import json, re
from pathlib import Path


class AccidentClassifier:
    """Multi-task text classifier: shared encoder + one linear head per output."""

    def __init__(self, model_dir, device="cpu"):
        import torch, torch.nn as nn
        from transformers import AutoModel, AutoTokenizer
        d = Path(model_dir)
        meta = json.load(open(d / "labels.json"))
        self.targets, self.max_len, self.device = meta["targets"], meta["max_len"], device
        self.out_re = re.compile(rf"\b({meta['outcome_words']})\b", re.I)
        self.mech_re = re.compile(rf"\b({meta['mechanism_words']})\b", re.I)
        self.tok = AutoTokenizer.from_pretrained(d / "encoder")
        self.encoder = AutoModel.from_pretrained(d / "encoder").to(device).eval()
        hidden = self.encoder.config.hidden_size
        self.heads = nn.ModuleDict({t: nn.Linear(hidden, len(ls)) for t, ls in self.targets.items()})
        self.heads.load_state_dict(torch.load(d / "heads.pt", map_location=device, weights_only=True))
        self.heads.to(device).eval()
        self._torch = torch

    def context_only(self, text):
        """Same masking as in training: remove outcome and mechanism words."""
        t = self.mech_re.sub(" ", self.out_re.sub(" ", text))
        return re.sub(r"\s+", " ", t).strip()

    def predict(self, text, top=3):
        """Top classes with probabilities for each output, e.g. {'event_group': [('Fall, slip or trip', 0.41), ...]}."""
        torch = self._torch
        enc = self.tok([self.context_only(text)], truncation=True, max_length=self.max_len, return_tensors="pt").to(self.device)
        with torch.no_grad():
            h = self.encoder(**{k: v for k, v in enc.items() if k in ("input_ids", "attention_mask")}).last_hidden_state[:, 0]
            out = {}
            for t, head in self.heads.items():
                p = head(h).softmax(-1)[0].cpu().numpy()
                order = p.argsort()[::-1][:top]
                out[t] = [(self.targets[t][i], round(float(p[i]), 3)) for i in order]
        return out

    def proba(self, texts, task="event_group", mask=False, batch=64):
        """Class probabilities (n_texts x n_classes) for one output. Used by the explainers (SHAP, LIME, IG).

        mask=False: the texts are used as given (the explainers already work on the context-only text)."""
        import numpy as np
        torch = self._torch
        texts = [self.context_only(t) if mask else t for t in texts]
        out = []
        for i in range(0, len(texts), batch):
            chunk = [t if t.strip() else "[UNK]" for t in texts[i:i + batch]]     # an empty text still gets a score
            enc = self.tok(chunk, truncation=True, max_length=self.max_len, padding=True, return_tensors="pt").to(self.device)
            with torch.no_grad():
                h = self.encoder(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"]).last_hidden_state[:, 0]
                out.append(self.heads[task](h).softmax(-1).cpu().numpy())
        return np.concatenate(out) if out else np.zeros((0, len(self.targets[task])))
