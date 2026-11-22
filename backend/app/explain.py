"""SafeVision word explanations for the accident-type classifier (XAI, experiment E10).

Three methods give every word of the (context-only) text a score: how much it pushes the model towards the
predicted class.
  * SHAP  - Partition explainer with a text masker (Lundberg & Lee 2017; shap library).
  * LIME  - local linear model on randomly removed words (Ribeiro et al. 2016; lime library).
  * IG    - Integrated Gradients on the word embeddings (Sundararajan et al. 2017; Captum).
All three return the same format, so they can be compared with the same faithfulness tests (ERASER,
DeYoung et al. 2020): comprehensiveness (remove the top words: the score should drop a lot) and
sufficiency (keep only the top words: the score should stay high, so the drop should be small).
"""
import json, re, time
from pathlib import Path
import numpy as np

ALL_METHODS = ("shap", "lime", "ig")


def words_of(text):
    return text.split()


class WordExplainer:
    def __init__(self, classifier, shap_evals=500, lime_samples=500, ig_steps=50, seed=0):
        self.clf, self.seed = classifier, seed
        self.shap_evals, self.lime_samples, self.ig_steps = shap_evals, lime_samples, ig_steps
        self._shap, self._lime, self._ig = {}, None, None

    # ---------- shared helpers ----------
    def prob_fn(self, task, target):
        """f(list of texts) -> probability of class `target` (index) for each text."""
        return lambda texts: self.clf.proba(list(texts), task)[:, target]

    def predict_index(self, text, task):
        return int(self.clf.proba([text], task)[0].argmax())

    # ---------- SHAP ----------
    def shap_scores(self, text, task, target):
        import shap
        if task not in self._shap:
            # Hidden words are replaced by a marker that is then deleted, so SHAP, LIME and the faithfulness
            # tests all "remove" words the same way.
            masker = shap.maskers.Text(r"\s+", mask_token="XXDELXX", collapse_mask_token=True)
            drop = lambda t: re.sub(r"\s+", " ", t.replace("XXDELXX", " ")).strip()
            f = lambda texts: self.clf.proba([drop(t) for t in texts], task)
            self._shap[task] = shap.Explainer(f, masker, output_names=self.clf.targets[task], algorithm="partition")
        ex = self._shap[task]([text], max_evals=self.shap_evals, silent=True)
        toks, vals = ex.data[0], ex.values[0][:, target]
        scores = [float(v) for t, v in zip(toks, vals) if str(t).strip()]
        return self._fit(scores, len(words_of(text)))

    # ---------- LIME ----------
    def lime_scores(self, text, task, target):
        from lime.lime_text import LimeTextExplainer
        if self._lime is None:
            self._lime = LimeTextExplainer(split_expression=r"\s+", bow=False, mask_string="", random_state=self.seed)
        f = lambda texts: self.clf.proba(list(texts), task)
        n = len(words_of(text))
        ex = self._lime.explain_instance(text, f, labels=[target], num_features=max(n, 1), num_samples=self.lime_samples)
        scores = np.zeros(n)
        for pos, w in ex.as_map()[target]:
            if pos < n:
                scores[pos] = w
        return scores.tolist()

    # ---------- Integrated Gradients ----------
    def ig_scores(self, text, task, target):
        import torch
        from captum.attr import LayerIntegratedGradients
        clf, words = self.clf, words_of(text)
        enc = clf.tok(words, is_split_into_words=True, truncation=True, max_length=clf.max_len, return_tensors="pt")
        ids, att = enc["input_ids"].to(clf.device), enc["attention_mask"].to(clf.device)
        special = torch.tensor([i in clf.tok.all_special_ids for i in ids[0].tolist()], device=clf.device)
        base = torch.where(special, ids, torch.full_like(ids, clf.tok.pad_token_id))   # baseline: every word replaced by [PAD]

        def forward(input_ids, attention_mask):
            h = clf.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state[:, 0]
            return clf.heads[task](h).softmax(-1)[:, target]

        lig = LayerIntegratedGradients(forward, clf.encoder.embeddings)
        attr = lig.attribute(ids, baselines=base, additional_forward_args=(att,), n_steps=self.ig_steps,
                             internal_batch_size=self.ig_steps)
        sub = attr.sum(-1)[0].detach().cpu().numpy()          # one number per sub-word token
        scores = np.zeros(len(words))
        for tok_i, w in enumerate(enc.word_ids(0)):
            if w is not None:
                scores[w] += sub[tok_i]                      # sum the sub-words of each word
        return scores.tolist()

    # ---------- public API ----------
    def explain(self, text, task="event_group", method="shap", target=None):
        """Word scores for one text. Returns dict(words, scores, target, label, prob, method, ms)."""
        t0 = time.time()
        target = self.predict_index(text, task) if target is None else target
        fn = {"shap": self.shap_scores, "lime": self.lime_scores, "ig": self.ig_scores}[method]
        scores = fn(text, task, target) if words_of(text) else []
        p = float(self.clf.proba([text], task)[0, target])
        return dict(words=words_of(text), scores=[round(float(s), 5) for s in scores], target=target,
                    label=self.clf.targets[task][target], prob=round(p, 4), method=method,
                    ms=round(1000 * (time.time() - t0), 1))

    @staticmethod
    def _fit(scores, n):
        # Make the score list exactly n long (tokeniser edge cases).
        return (list(scores) + [0.0] * n)[:n]


# ---------- faithfulness (ERASER) ----------
def top_k_positions(scores, k):
    order = np.argsort(-np.asarray(scores, dtype=float))
    return set(order[:k].tolist())


def remove_words(words, positions):
    return " ".join(w for i, w in enumerate(words) if i not in positions)


def keep_words(words, positions):
    return " ".join(w for i, w in enumerate(words) if i in positions)


def faithfulness(prob_fn, words, scores, ks=(1, 3, 5)):
    """Comprehensiveness and sufficiency at each k. prob_fn(list of texts) -> target-class probabilities."""
    full = " ".join(words)
    texts = [full]
    for k in ks:
        pos = top_k_positions(scores, min(k, len(words)))
        texts += [remove_words(words, pos), keep_words(words, pos)]
    p = prob_fn(texts)
    out = {}
    for j, k in enumerate(ks):
        out[f"comp@{k}"] = float(p[0] - p[1 + 2 * j])
        out[f"suff@{k}"] = float(p[0] - p[2 + 2 * j])
    return out


def load_choice(models_dir):
    """Method picked by Notebook 6 (xai_choice.json), default SHAP."""
    f = Path(models_dir) / "xai_choice.json"
    return json.load(open(f)).get("best_method", "shap") if f.exists() else "shap"
