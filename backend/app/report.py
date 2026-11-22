"""SafeVision report writer (N5): turns vision findings + retrieved rules + accident-risk prediction into an incident report.

Backends: Groq API (Llama 3.1 8B, free tier), a local Ollama server, a local Hugging Face model, or a
rule-based template (no language model, used as the baseline). The prompt only allows facts from the
evidence and asks for section numbers in brackets, so the fact checker (factcheck.py) can verify them.
"""
import json, os, time

SYSTEM_PROMPT = (
    "You are a construction safety officer writing a short incident report from an automated site-photo check. "
    "Use ONLY the facts in FINDINGS, RULES and RISK. Do not invent numbers, people, places, dates or rules. "
    "Each rule in RULES starts with its id in square brackets, e.g. [1926.100] or [DM_Safety_Guide p.178]. "
    "When you cite a rule, copy that id exactly, in square brackets. Never invent an id. "
    "If something is unclear in the findings, say it is unclear. If FINDINGS say an item could not be checked, never "
    "write that it is worn or that there is no violation for it. Keep it under 180 words. "
    "Use exactly these headings, each on its own line: Summary:, Violations:, Applicable rules:, Likely accident risk:, Corrective actions:"
)


def plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


ITEM_TEXT = {  # item -> (worn phrase, missing phrase)
    "helmet": ("wearing a hard hat", "not wearing a hard hat"),
    "vest": ("wearing a high-visibility vest", "not wearing a high-visibility vest"),
    "gloves": ("wearing protective gloves", "not wearing protective gloves (bare hands)"),
    "glasses": ("wearing safety glasses", "not wearing safety glasses"),
}
ITEM_NAME = {"helmet": "a hard hat", "vest": "a high-visibility vest", "gloves": "gloves", "glasses": "safety glasses"}


def findings_from_workers(workers):
    """Worker list from matching.py -> (situation sentence for search/classifier, list of fact sentences, counts).

    Facts state only what was actually seen: items that could not be checked (too small, hidden) are reported
    as 'could not be checked', never as 'worn', so the report writer cannot turn uncertainty into compliance."""
    n = len(workers)
    st = lambda item, v: sum(w.get(item, "n/a") == v for w in workers)
    c = {"workers": n,
         "no_helmet": st("helmet", "no"), "helmet_unsure": st("helmet", "unsure"), "helmet_ok": st("helmet", "yes"),
         "no_vest": st("vest", "no"), "vest_unsure": st("vest", "unsure"), "vest_ok": st("vest", "yes"),
         "no_gloves": st("gloves", "no"), "gloves_unsure": st("gloves", "unsure"), "gloves_ok": st("gloves", "yes"),
         "no_glasses": st("glasses", "no"), "glasses_unsure": st("glasses", "unsure"), "glasses_ok": st("glasses", "yes")}
    facts = [f"The photo shows {plural(n, 'worker', 'workers')}." if n else "No workers were detected in the photo."]
    for item, (worn, missing) in ITEM_TEXT.items():
        if not n or all(w.get(item, "n/a") == "n/a" for w in workers):
            continue                                                   # item not checked by this detector
        no, ok, un = c[f"no_{item}"], c[f"{item}_ok"], c[f"{item}_unsure"]
        if no == 0 and un == 0:
            facts.append(f"Every worker is {worn}." if n > 1 else f"The worker is {worn}.")
            continue
        if no:
            facts.append(f"{plural(no, 'worker is', 'workers are')} {missing}.")
        if ok:
            facts.append(f"{plural(ok, 'worker is', 'workers are')} {worn}.")
        if un:
            facts.append(f"For {plural(un, 'worker', 'workers')}, it could not be checked whether {ITEM_NAME[item]} "
                         f"{'is' if item in ('helmet', 'vest') else 'are'} worn (too small or hidden in the photo).")
    parts = [f"construction site with {plural(n, 'worker', 'workers')}"]
    if c["no_helmet"]:
        parts.append(f"{plural(c['no_helmet'], 'worker', 'workers')} without a hard hat (head protection)")
    if c["no_vest"]:
        parts.append(f"{plural(c['no_vest'], 'worker', 'workers')} without a high-visibility vest")
    if c["no_gloves"]:
        parts.append(f"{plural(c['no_gloves'], 'worker', 'workers')} without protective gloves (bare hands)")
    if c["no_glasses"]:
        parts.append(f"{plural(c['no_glasses'], 'worker', 'workers')} without safety glasses (eye protection)")
    situation = "; ".join(parts) + "."
    return situation, facts, c


def rule_query(counts):
    """Search query for the rule book, built from the violations only (the worker count does not help retrieval)."""
    parts = []
    if counts.get("no_helmet"):
        parts.append("worker not wearing a hard hat; head protection helmet required where objects may fall")
    if counts.get("no_vest"):
        parts.append("worker not wearing a high-visibility vest; reflective warning garment required on site")
    if counts.get("no_gloves"):
        parts.append("worker with bare hands; hand protection gloves required for cuts, abrasions, chemicals")
    if counts.get("no_glasses"):
        parts.append("worker without safety glasses; eye and face protection required for flying particles")
    if counts.get("helmet_unsure") and not parts:
        parts.append("hard hat head protection requirements for construction workers")
    return " ".join(parts) or "personal protective equipment requirements for construction workers"


def risk_sentences(prediction):
    """Classifier output -> evidence sentences about the likely accident (top class of each output)."""
    if not prediction:
        return []
    names = {"event_group": "accident type", "body_group": "injured body part", "severity": "severity"}
    vague = {"Non-classifiable", "Other or unspecified"}      # not a useful risk hint
    out = []
    for t, v in prediction.items():
        label, p = v[0]
        if label in vague:               # the model is not specific for this output: say nothing rather than a weak guess
            continue
        out.append(f"In similar past OSHA reports, the most likely {names.get(t, t)} is {label} (probability {p:.2f}).")
    return out


def build_messages(facts, rules=None, risk=None):
    """Chat messages for the report writer. rules=None gives the 'no rules' variant."""
    # full chunk text (about 200 words): cutting it short can drop the very sentence that applies
    rules_txt = "\n".join(f"[{r['section']}] {r['text'][:1800]}" for r in (rules or [])) or "(no rules provided)"
    user = ("FINDINGS:\n" + "\n".join(f"- {f}" for f in facts) +
            "\n\nRULES:\n" + rules_txt +
            "\n\nRISK:\n" + ("\n".join(f"- {r}" for r in risk) if risk else "(not available)") +
            "\n\nWrite the incident report now.")
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def fix_messages(messages, report, bad_sentences):
    """Follow-up turn asking the model to remove or correct sentences the fact checker could not verify."""
    bad = "\n".join(f"- {s}" for s in bad_sentences)
    return messages + [{"role": "assistant", "content": report},
                       {"role": "user", "content": "These sentences are not supported by FINDINGS, RULES or RISK, or cite a rule "
                        "that is not in RULES:\n" + bad + "\nRewrite the whole report with the same headings. Remove or correct "
                        "these sentences and do not add new facts."}]


def template_report(facts, rules=None, risk=None):
    """Rule-based report without a language model (baseline variant)."""
    bad = [f for f in facts[1:] if "not wearing" in f]
    other = [f for f in facts[1:] if f not in bad]
    lines = ["Summary:", " ".join([facts[0]] + other)]
    lines += ["Violations:"] + ([f"- {f}" for f in bad] or ["- None found."])
    lines += ["Applicable rules:"] + ([f"- [{r['section']}] {r['heading']}" for r in rules] if rules else ["- None retrieved."])
    lines += ["Likely accident risk:"] + ([f"- {r}" for r in risk] if risk else ["- Not available."])
    lines += ["Corrective actions:"]
    lines += (["- Stop work for the affected workers until the missing protective equipment is worn."]
              if any("not wearing" in f for f in facts) else ["- No action needed beyond routine site checks."])
    return "\n".join(lines)


class LLMClient:
    """Small chat client. backend: 'groq' | 'ollama' | 'hf' | 'template'."""

    def __init__(self, backend="groq", model=None, api_key=None, url=None, min_interval=2.1, device=None):
        self.backend = backend
        # Groq retired llama-3.1-8b-instant for free accounts on 16 Aug 2026; its recommended replacement is
        # openai/gpt-oss-20b (open-weight, Apache 2.0). Ollama/HF backends can still run Llama locally.
        self.model = model or {"groq": "openai/gpt-oss-20b", "ollama": "llama3.1:8b",
                               "hf": "Qwen/Qwen2.5-1.5B-Instruct"}.get(backend)
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.url = url or {"groq": "https://api.groq.com/openai/v1/chat/completions",
                           "ollama": "http://localhost:11434/api/chat"}.get(backend)
        self.min_interval = min_interval          # Groq free tier: 30 requests per minute
        self._last = 0.0
        self._pipe = None
        if backend == "hf":
            from transformers import pipeline
            self._pipe = pipeline("text-generation", model=self.model, device_map="auto" if device is None else None,
                                  device=device)

    def chat(self, messages, temperature=0.2, max_tokens=450):
        """Send the messages and return the reply text."""
        if self.backend == "groq":
            import requests
            for attempt in range(5):
                wait = self.min_interval - (time.time() - self._last)
                if wait > 0:
                    time.sleep(wait)
                self._last = time.time()
                body = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
                if "gpt-oss" in self.model:
                    # reasoning models spend tokens on thinking first: keep it short and leave room for the answer
                    body.update(reasoning_effort="low", max_tokens=max(max_tokens, 1500))
                r = requests.post(self.url, headers={"Authorization": f"Bearer {self.api_key}"}, timeout=120, json=body)
                if r.status_code == 400 and "reasoning_effort" in r.text:    # older API: drop the option and retry
                    body.pop("reasoning_effort", None)
                    r = requests.post(self.url, headers={"Authorization": f"Bearer {self.api_key}"}, timeout=120, json=body)
                if r.status_code == 429:                       # rate limited: wait as told, then retry
                    time.sleep(float(r.headers.get("retry-after", 10)))
                    continue
                if r.status_code == 404:
                    raise RuntimeError(f"Groq model '{self.model}' not available (404). Set LLM_MODEL to a model listed at console.groq.com/docs/models")
                r.raise_for_status()
                return (r.json()["choices"][0]["message"].get("content") or "").strip()
            raise RuntimeError("Groq rate limit: too many retries")
        if self.backend == "ollama":
            import requests
            r = requests.post(self.url, timeout=300, json={"model": self.model, "messages": messages, "stream": False,
                                                           "options": {"temperature": temperature, "num_predict": max_tokens,
                                                                       "num_ctx": 8192}})   # room for 3 full rule texts
            r.raise_for_status()
            return r.json()["message"]["content"].strip()
        if self.backend == "hf":
            out = self._pipe(messages, max_new_tokens=max_tokens, do_sample=temperature > 0,
                             temperature=max(temperature, 1e-3), return_full_text=False)
            gen = out[0]["generated_text"]
            return (gen[-1]["content"] if isinstance(gen, list) else gen).strip()
        raise ValueError(f"Unknown backend {self.backend}")


# ---------------- Incident Analysis (text in -> causes, rules, actions) ----------------
INCIDENT_PROMPT = (
    "You are a construction safety officer analysing an incident or near-miss description. "
    "Use ONLY the facts in INCIDENT, RULES, RISK and SIMILAR. Do not invent numbers, people, places, dates or rules. "
    "Each rule in RULES starts with its id in square brackets; when you cite a rule, copy that id exactly. Never invent an id. "
    "If the description does not say something, write that it is not stated. Keep it under 200 words. "
    "Use exactly these headings, each on its own line: Summary:, Likely accident type:, Contributing factors:, "
    "Applicable rules:, Corrective actions:"
)


def incident_messages(text, rules=None, risk=None, similar=None):
    """Chat messages for the Incident Analysis summary."""
    rules_txt = "\n".join(f"[{r['section']}] {r['text'][:1800]}" for r in (rules or [])) or "(no rules provided)"
    sim_txt = "\n".join(f"- ({s['year']}, {s['event_group']}) {s['narrative'][:300]}" for s in (similar or [])) or "(none)"
    user = ("INCIDENT:\n" + text.strip() + "\n\nRULES:\n" + rules_txt +
            "\n\nRISK:\n" + ("\n".join(f"- {r}" for r in risk) if risk else "(not available)") +
            "\n\nSIMILAR PAST ACCIDENTS (for context only):\n" + sim_txt + "\n\nWrite the incident analysis now.")
    return [{"role": "system", "content": INCIDENT_PROMPT}, {"role": "user", "content": user}]


def incident_template(text, rules=None, risk=None, top_words=None):
    """Incident analysis without a language model."""
    lines = ["Summary:", text.strip()[:400], "Likely accident type:"]
    lines += [f"- {r}" for r in risk] if risk else ["- Not available."]
    lines += ["Contributing factors:"]
    lines += [f"- The model relied most on: {', '.join(top_words)}."] if top_words else ["- Not stated."]
    lines += ["Applicable rules:"] + ([f"- [{r['section']}] {r['heading']}" for r in rules] if rules else ["- None retrieved."])
    lines += ["Corrective actions:", "- Review the applicable rules above with the crew and correct the conditions described."]
    return "\n".join(lines)
