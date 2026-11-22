"""SafeVision pipeline used by the web app: photo -> workers -> findings -> risk + rules -> report -> fact check.

Every component is optional: if a model file is missing, that step is skipped and /health says so,
so the app still runs while some notebooks are unfinished.
"""
import json, os, time
from pathlib import Path

from .privacy import privacy_regions
from .matching import detections_from_result, poses_from_result, match_workers, zoom_detections, merge_detections
from .report import (findings_from_workers, rule_query, risk_sentences, build_messages, fix_messages, template_report, LLMClient,
                     incident_messages, incident_template)
from .factcheck import FactChecker, summarise

MODELS = Path(os.environ.get("SAFEVISION_MODELS", Path(__file__).resolve().parents[1] / "models"))


class Pipeline:
    def __init__(self):
        import torch
        self.device = os.environ.get("SAFEVISION_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
        self.status = {}
        self.imgsz, self.conf_yes, self.conf_no = 640, 0.40, 0.40
        self.method = os.environ.get("MATCH_METHOD", "box")
        if (MODELS / "run_config.json").exists():
            self.imgsz = json.load(open(MODELS / "run_config.json")).get("best_imgsz", self.imgsz)
        if (MODELS / "matching_thresholds.json").exists():
            self.conf_yes, self.conf_no = json.load(open(MODELS / "matching_thresholds.json"))[self.method]
        self.item_conf = {}
        # Zoom re-check (crop each worker and detect again): on by default for hard hat, vest and gloves.
        # Notebook 2x (experiment E3x) writes the measured choice into matching_thresholds_ppe8.json ("zoom_items").
        self.zoom_items = [x for x in os.environ.get("ZOOM_ITEMS", "helmet,vest,gloves").split(",") if x]
        if (MODELS / "matching_thresholds_ppe8.json").exists():     # gloves / glasses thresholds from Notebook 2x (E3x)
            ppe8 = json.load(open(MODELS / "matching_thresholds_ppe8.json"))
            self.item_conf = {k: tuple(v) for k, v in ppe8.items() if k in ("gloves", "glasses")}
            if "zoom_items" in ppe8 and "ZOOM_ITEMS" not in os.environ:
                self.zoom_items = list(ppe8["zoom_items"])
        self.detector = self._load("detector", lambda: __import__("ultralytics").YOLO(str(MODELS / "detector_best.pt")),
                                   MODELS / "detector_best.pt")
        self.pose = self._load("pose", lambda: __import__("ultralytics").YOLO("yolo11s-pose.pt")) if self.method == "pose" else None
        self.classifier = self._load("classifier", lambda: __import__("app.classifier", fromlist=["x"]).AccidentClassifier(
            MODELS / "accident_classifier", device=self.device), MODELS / "accident_classifier")
        self.rules = self._load("rules", lambda: self._gpu_or_cpu(lambda dev: __import__("app.rules", fromlist=["x"]).RuleSearch(
            MODELS / "rule_index", device=dev, use_reranker=os.environ.get("USE_RERANKER", "1") == "1")), MODELS / "rule_index")
        self.similar = self._load("similar_accidents", lambda: __import__("app.similar", fromlist=["x"]).SimilarAccidents(
            MODELS, device=self.device, masker=self.classifier.context_only if self.classifier else None),
            MODELS / "similar_accidents.faiss")
        self.explainer = self._load("explainer", lambda: __import__("app.explain", fromlist=["x"]).WordExplainer(
            self.classifier, shap_evals=int(os.environ.get("SHAP_EVALS", 300)), lime_samples=int(os.environ.get("LIME_SAMPLES", 300)))
            ) if self.classifier else None
        self.xai_method = __import__("app.explain", fromlist=["x"]).load_choice(MODELS)
        self.status["xai_method"] = self.xai_method
        self.captioner = self._load("captioner", lambda: __import__("app.caption", fromlist=["x"]).Captioner(
            MODELS / "florence2_captioner", device=self.device), MODELS / "florence2_captioner")
        self.checker = self._load("fact_checker", lambda: self._gpu_or_cpu(lambda dev: FactChecker(
            os.environ.get("NLI_MODEL", "cross-encoder/nli-deberta-v3-base"), device=dev)))
        backend = os.environ.get("LLM_BACKEND", "groq" if os.environ.get("GROQ_API_KEY") else "template")
        self.llm = None if backend == "template" else self._load("llm", lambda: LLMClient(backend, model=os.environ.get("LLM_MODEL")))
        self.status["llm_backend"] = backend if self.llm else "template"

    def warm_up(self):
        """Run every model once on dummy input so the first real request is fast (GPU kernels, caches).
        Each step is optional: a failure is recorded in status and never stops the server."""
        from PIL import Image
        img, took = Image.new("RGB", (640, 480), (128, 128, 128)), {}
        steps = [
            ("detector", lambda: self.detector.predict(img, imgsz=self.imgsz, conf=0.10, device=self.device, verbose=False)),
            ("captioner", lambda: self.captioner.caption(img)),
            ("classifier", lambda: self.classifier.predict("A worker stands on a ladder without a hard hat.")),
            ("similar_accidents", lambda: self.similar.search("worker on a ladder", k=1)),
            ("rules", lambda: self.rules.search("hard hat required", k=1)),
            ("fact_checker", lambda: self.checker.check("Workers must wear hard hats.", ["Employees shall wear protective helmets."])),
        ]
        for name, run in steps:
            if getattr(self, {"similar_accidents": "similar", "fact_checker": "checker"}.get(name, name), None) is None:
                continue
            t0 = time.time()
            try:
                run(); took[name] = round(time.time() - t0, 1)
            except Exception as e:
                took[name] = f"failed: {e}"[:120]
        self.status["warm_up_s"] = took
        return took

    def _gpu_or_cpu(self, make):
        """Build a component on the GPU; if the GPU is full (small cards), build it on the CPU instead of failing."""
        if self.device == "cpu":
            return make("cpu")
        try:
            return make(self.device)
        except Exception as e:                                   # CUDA out of memory and similar
            if "out of memory" not in str(e).lower():
                raise
            import torch
            torch.cuda.empty_cache()
            return make("cpu")

    def _load(self, name, fn, needs=None):
        # Load one component; record 'ok' or the reason it is missing.
        if needs is not None and not Path(needs).exists():
            self.status[name] = f"missing: {Path(needs).name}"
            return None
        try:
            obj = fn(); self.status[name] = "ok"; return obj
        except Exception as e:
            self.status[name] = f"error: {e}"[:200]
            return None

    def analyze(self, image, n_rules=3, fact_check=True):
        """Run the full pipeline on one PIL image and return a JSON-ready dict."""
        t, out = {}, {"width": image.size[0], "height": image.size[1]}
        t0 = time.time()
        if self.detector is None:
            raise RuntimeError("Detector not loaded: put detector_best.pt in backend/models")
        det = self.detector.predict(image, imgsz=self.imgsz, conf=0.10, device=self.device, verbose=False)[0]
        dets = detections_from_result(det)
        if self.zoom_items:                      # zoom re-check of every clearly detected worker
            persons = [b for b, c in dets["person"] if c >= 0.30]
            dets = merge_detections(dets, zoom_detections(self.detector, image, persons, items=self.zoom_items))
        out["privacy_regions"] = privacy_regions(dets)        # faces to blur in the saved copy (main.py)
        poses = poses_from_result(self.pose.predict(image, imgsz=self.imgsz, conf=0.25, device=self.device, verbose=False)[0]) if self.pose else None
        workers = match_workers(dets, image.size[1], pose_list=poses, method=self.method,
                                conf_yes=self.conf_yes, conf_no=self.conf_no, item_conf=self.item_conf)
        t["vision_ms"] = 1000 * (time.time() - t0)
        situation, facts, counts = findings_from_workers(workers)
        caption = None
        if self.captioner:                       # scene description (Florence-2, Notebook 7) -> richer situation text
            t0 = time.time()
            try:
                caption = self.captioner.caption(image)
                situation = f"{situation} {caption}"
            except Exception as e:
                self.status["captioner"] = f"error: {e}"[:200]
            t["caption_ms"] = 1000 * (time.time() - t0)

        t0 = time.time()
        pred = self.classifier.predict(situation) if (self.classifier and counts["workers"]) else None
        t["classifier_ms"] = 1000 * (time.time() - t0)
        risk = risk_sentences(pred)

        t0 = time.time()
        similar = self.similar.search(situation, k=3) if (self.similar and counts["workers"]) else []
        t["similar_ms"] = 1000 * (time.time() - t0)

        t0 = time.time()
        n_items = sum(bool(counts.get(k)) for k in ("no_helmet", "no_vest", "no_gloves", "no_glasses"))
        rules = self.rules.search(rule_query(counts), k=max(n_rules, n_items + 1)) if (self.rules and self._violation(counts)) else []
        t["rules_ms"] = 1000 * (time.time() - t0)

        t0 = time.time()
        evidence, allowed = facts + [r["text"] for r in rules] + risk, [r["section"] for r in rules]
        checks = []
        if self.llm:
            msgs = build_messages(facts, rules, risk)
            try:
                report = self.llm.chat(msgs)
                if fact_check and self.checker:
                    checks = self.checker.check(report, evidence, findings=facts, allowed_sections=allowed)
                    bad = [c["sentence"] for c in checks if c["label"] != "supported"]
                    if bad:                                  # one correction round, as variant V3 in Notebook 5
                        report = self.llm.chat(fix_messages(msgs, report, bad))
                        checks = self.checker.check(report, evidence, findings=facts, allowed_sections=allowed)
            except Exception as e:                           # LLM down -> template report, so the app still answers
                report = template_report(facts, rules, risk) + f"\n\n(Language model unavailable: {str(e)[:100]})"
        else:
            report = template_report(facts, rules, risk)
        if not checks and fact_check and self.checker:
            checks = self.checker.check(report, evidence, findings=facts, allowed_sections=allowed)
        t["report_ms"] = 1000 * (time.time() - t0)

        out.update(workers=[{**w, "box": [round(float(v), 1) for v in w["box"]]} for w in workers], counts=counts,
                   situation=situation, caption=caption, facts=facts, risk=pred, risk_sentences=risk, rules=rules, similar=similar, report=report,
                   checks=checks, check_summary=summarise(checks, report) if checks else None,
                   timings={k: round(v, 1) for k, v in t.items()}, violation=self._violation(counts))
        return out

    def heatmap(self, image):
        """EigenCAM heat map of the detector over the photo (PIL image), or None if no detector."""
        if self.detector is None:
            return None
        if getattr(self, "_cam", None) is None:
            from .cam import DetectorCAM
            self._cam = DetectorCAM(self.detector, self.imgsz, self.device)
        return self._cam.overlay(image, self._cam.heatmap(image))

    @staticmethod
    def _violation(counts):
        return bool(counts["no_helmet"] or counts["no_vest"] or counts.get("no_gloves") or counts.get("no_glasses"))

    def _write_checked(self, msgs, evidence, allowed, fallback, fact_check=True):
        """LLM text + fact check + one correction round (same as variant V3), or the template if no LLM."""
        checks, report = [], None
        if self.llm:
            try:
                report = self.llm.chat(msgs)
                if fact_check and self.checker:
                    checks = self.checker.check(report, evidence, allowed_sections=allowed)
                    bad = [c["sentence"] for c in checks if c["label"] != "supported"]
                    if bad:
                        report = self.llm.chat(fix_messages(msgs, report, bad))
                        checks = self.checker.check(report, evidence, allowed_sections=allowed)
            except Exception as e:
                report = fallback + f"\n\n(Language model unavailable: {str(e)[:100]})"; checks = []
        report = report or fallback
        if not checks and fact_check and self.checker:
            checks = self.checker.check(report, evidence, allowed_sections=allowed)
        return report, checks

    def incident(self, text, method=None, n_rules=3, fact_check=True):
        """Incident Analysis: incident/near-miss text -> accident type + word explanation + similar accidents + rules + summary."""
        if not self.classifier:
            raise RuntimeError("Accident classifier not loaded: put accident_classifier/ in backend/models")
        t, method = {}, (method or self.xai_method)
        t0 = time.time()
        ctx = self.classifier.context_only(text)
        pred = self.classifier.predict(text)
        t["classifier_ms"] = 1000 * (time.time() - t0)
        explanation = None
        if self.explainer and ctx.split():
            t0 = time.time()
            explanation = self.explainer.explain(ctx, task="event_group", method=method)
            t["explain_ms"] = 1000 * (time.time() - t0)
        risk = risk_sentences(pred)
        t0 = time.time()
        similar = self.similar.search(text, k=3) if self.similar else []
        t["similar_ms"] = 1000 * (time.time() - t0)
        t0 = time.time()
        rules = self.rules.search(text, k=n_rules) if self.rules else []
        t["rules_ms"] = 1000 * (time.time() - t0)
        top_words = []
        if explanation:
            order = sorted(range(len(explanation["scores"])), key=lambda i: -explanation["scores"][i])
            stop = {"a", "an", "the", "and", "or", "of", "to", "in", "on", "at", "was", "were", "is", "his", "her", "he", "she",
                    "it", "with", "from", "by", "for", "that", "this", "employee", "worker", "an"}
            top_words = [w for w in (explanation["words"][i].strip(".,;:") for i in order if explanation["scores"][i] > 0)
                         if w.lower() not in stop][:5]
        t0 = time.time()
        evidence = [text] + [r["text"] for r in rules] + risk
        report, checks = self._write_checked(incident_messages(text, rules, risk, similar), evidence, [r["section"] for r in rules],
                                             incident_template(text, rules, risk, top_words), fact_check)
        t["report_ms"] = 1000 * (time.time() - t0)
        # words the classifier never sees (outcome / how-it-happened words removed in training), for the UI
        kept = set(ctx.lower().split())
        hidden = sorted({w.strip(".,;:").lower() for w in text.split() if w.lower() not in kept and w.strip(".,;:")})
        return dict(text=text, context_text=ctx, hidden_words=hidden, risk=pred, risk_sentences=risk, explanation=explanation,
                    top_words=top_words, similar=similar, rules=rules, report=report, checks=checks,
                    check_summary=summarise(checks, report) if checks else None, timings={k: round(v, 1) for k, v in t.items()})

    def ask(self, question, k=3):
        """Rule question answering: top rules plus a short grounded answer (LLM if available)."""
        if not self.rules:
            raise RuntimeError("Rule index not loaded: put rule_index/ in backend/models")
        rules = self.rules.search(question, k=k)
        answer = None
        if self.llm:
            msgs = [{"role": "system", "content": "Answer the construction-safety question using ONLY the RULES. Cite section numbers in "
                     "square brackets. If the rules do not answer it, say so. Under 120 words."},
                    {"role": "user", "content": "RULES:\n" + "\n".join(f"[{r['section']}] {r['text'][:700]}" for r in rules) +
                     f"\n\nQUESTION: {question}"}]
            try:
                answer = self.llm.chat(msgs)
            except Exception as e:
                answer = f"(Language model unavailable: {str(e)[:100]})"
        checks = self.checker.check(answer, [r["text"] for r in rules], allowed_sections=[r["section"] for r in rules]) \
            if (answer and self.checker) else []
        return {"question": question, "rules": rules, "answer": answer, "checks": checks}
