"""Send every photo in a folder to the running SafeVision API and save all results in one place.

Needs the backend running (uvicorn app.main:app --port 8000). Uses only the Python standard library + Pillow.

Usage (from the SafeVision folder, any venv with Pillow, e.g. .venv-tools):
    python scripts/batch_test.py --photos test_photos --out test_results

Creates in --out:
  results.csv          one row per photo: expected label, app answer, correct?, counts, fact-check, timings
  summary.txt          accuracy, precision, recall, F1 for "helmet violation" (same definition as experiment E3)
  reports.md           the full incident report the app wrote for each photo
  annotated/<photo>    each photo with the app's worker boxes (red = missing PPE, yellow = unclear, green = OK)
"""
import argparse, csv, json, mimetypes, time, uuid, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw

COLORS = {"no": (229, 56, 59), "unsure": (244, 180, 0), "yes": (47, 191, 113)}


def post_image(api, path, fact_check=True):
    """POST one image to /analyze as multipart/form-data and return the JSON result."""
    boundary = uuid.uuid4().hex
    ctype = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{api}/analyze?fact_check={str(fact_check).lower()}", data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def worker_color(w):
    if "no" in (w["helmet"], w["vest"]):
        return COLORS["no"]
    if "unsure" in (w["helmet"], w["vest"]):
        return COLORS["unsure"]
    return COLORS["yes"]


def draw_boxes(src, result, dest):
    """Save a copy of the photo with the app's worker boxes drawn on it."""
    img = Image.open(src).convert("RGB")
    img.thumbnail((result["width"], result["height"]))           # same size the API analysed
    d = ImageDraw.Draw(img)
    lw = max(2, img.width // 300)
    for i, w in enumerate(result["workers"], 1):
        x1, y1, x2, y2 = w["box"]
        c = worker_color(w)
        d.rectangle([x1, y1, x2, y2], outline=c, width=lw)
        d.text((x1 + 3, max(0, y1 - 14)), f"{i} H:{w['helmet']} V:{w['vest']}", fill=c)
    img.save(dest, quality=90)


ap = argparse.ArgumentParser()
ap.add_argument("--photos", default="test_photos")
ap.add_argument("--out", default="test_results")
ap.add_argument("--api", default="http://localhost:8000")
ap.add_argument("--no-fact-check", action="store_true", help="faster: skip the fact checker")
args = ap.parse_args()

photos, out = Path(args.photos), Path(args.out)
(out / "annotated").mkdir(parents=True, exist_ok=True)
expected = {}
if (photos / "expected_labels.csv").exists():
    for r in csv.DictReader(open(photos / "expected_labels.csv", encoding="utf-8")):
        expected[r["file"]] = r

files = sorted(p for p in photos.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
print(f"Testing {len(files)} photos against {args.api} ...")
rows, md = [], ["# SafeVision batch test: reports\n"]
for n, p in enumerate(files, 1):
    exp = expected.get(p.name, {})
    exp_label = exp.get("expected") or ("helmet_violation" if "violation" in p.stem and not p.stem.startswith("no_") else "unknown")
    t0 = time.time()
    try:
        r = post_image(args.api, p, fact_check=not args.no_fact_check)
    except Exception as e:
        print(f"[{n}/{len(files)}] {p.name}: ERROR {e}")
        rows.append({"file": p.name, "expected": exp_label, "error": str(e)}); continue
    c = r["counts"]
    pred = "helmet_violation" if c["no_helmet"] > 0 else "no_violation"
    s = r.get("check_summary") or {}
    row = {"file": p.name, "expected": exp_label, "app_says": pred,
           "correct": (pred == exp_label) if exp_label != "unknown" else "",
           "workers": c["workers"], "no_hard_hat": c["no_helmet"], "hard_hat_unclear": c["helmet_unsure"],
           "no_vest": c["no_vest"], "any_ppe_violation": r["violation"],
           "report_supported_pct": round(s.get("supported_pct", 0), 1) if s else "",
           "report_contradicted_pct": round(s.get("contradicted_pct", 0), 1) if s else "",
           "rules_retrieved": "; ".join(x["section"] for x in r.get("rules", [])),
           "top_accident_risk": (r.get("risk") or {}).get("event_group", [["", 0]])[0][0] if r.get("risk") else "",
           "seconds": round(time.time() - t0, 1), "expert_reason": exp.get("expert_reason", ""), "id": r.get("id", "")}
    rows.append(row)
    draw_boxes(p, r, out / "annotated" / p.name)
    md += [f"## {p.name}", f"- Expected: **{exp_label}** · App: **{pred}** · {'correct' if row['correct'] is True else 'WRONG' if row['correct'] is False else ''}",
           f"- Expert reason: {exp.get('expert_reason', '-')}", f"- Situation: {r['situation']}", "", "```", r["report"], "```", ""]
    print(f"[{n}/{len(files)}] {p.name}: expected={exp_label} app={pred} "
          f"({'OK' if row['correct'] is True else 'WRONG' if row['correct'] is False else '-'}) in {row['seconds']} s")

fields = ["file", "expected", "app_says", "correct", "workers", "no_hard_hat", "hard_hat_unclear", "no_vest",
          "any_ppe_violation", "report_supported_pct", "report_contradicted_pct", "rules_retrieved",
          "top_accident_risk", "seconds", "expert_reason", "id", "error"]
with open(out / "results.csv", "w", newline="", encoding="utf-8-sig") as f:      # utf-8-sig opens cleanly in Excel
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
(out / "reports.md").write_text("\n".join(md), encoding="utf-8")

# Summary: helmet violation as the positive class (same as experiment E3)
ok = [r for r in rows if r.get("correct") in (True, False)]
tp = sum(r["expected"] == "helmet_violation" and r["app_says"] == "helmet_violation" for r in ok)
fp = sum(r["expected"] == "no_violation" and r["app_says"] == "helmet_violation" for r in ok)
fn = sum(r["expected"] == "helmet_violation" and r["app_says"] == "no_violation" for r in ok)
tn = sum(r["expected"] == "no_violation" and r["app_says"] == "no_violation" for r in ok)
prec = tp / (tp + fp) if tp + fp else 0; rec = tp / (tp + fn) if tp + fn else 0
f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
sup = [r["report_supported_pct"] for r in rows if isinstance(r.get("report_supported_pct"), float)]
summary = (f"SafeVision batch test ({len(rows)} photos, {time.strftime('%Y-%m-%d %H:%M')})\n"
           f"Correct: {tp + tn}/{len(ok)}  (accuracy {(tp + tn) / max(len(ok), 1):.2f})\n"
           f"Helmet violations: TP={tp}  FN={fn}  |  Clean photos: TN={tn}  FP={fp}\n"
           f"Precision={prec:.2f}  Recall={rec:.2f}  F1={f1:.2f}\n"
           f"Average report sentences supported by evidence: {sum(sup) / len(sup):.1f}%\n" if sup else "")
summary = summary or f"{len(rows)} photos tested.\n"
(out / "summary.txt").write_text(summary, encoding="utf-8")
print("\n" + summary + f"Saved: {out / 'results.csv'}, {out / 'summary.txt'}, {out / 'reports.md'}, {out / 'annotated'}")
