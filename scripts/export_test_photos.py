"""Export test photos from ConstructionSite 10k (test split) to try the SafeVision app.

Saves N photos WITH a helmet violation and N photos WITHOUT any PPE violation, plus a CSV with the
expert's reason, so you can compare the app's answer with the human label.

Usage (from the SafeVision folder, backend venv active):
    pip install datasets
    huggingface-cli login            # once; your account must have accepted the ConstructionSite 10k terms
    python scripts/export_test_photos.py --n 8 --out test_photos
"""
import argparse, csv, json, os, re
from getpass import getpass
from pathlib import Path
from datasets import load_dataset

HELMET_WORDS = re.compile(r"\b(hard ?hats?|hardhats?|helmets?|head protection|safety hats?)\b", re.I)


def rule1(rec):
    """(has_violation, reason) for rule 1 (PPE)."""
    v = rec.get("rule_1_violation")
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            return bool(v.strip()), v
    if not v:
        return False, ""
    return True, (v.get("reason") or "") if isinstance(v, dict) else str(v)


ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=8, help="photos per group")
ap.add_argument("--out", default="test_photos")
args = ap.parse_args()
out = Path(args.out); out.mkdir(exist_ok=True)

# Token: from the HF_TOKEN environment variable, otherwise asked here (typing is hidden; nothing is saved)
token = os.environ.get("HF_TOKEN") or getpass("Paste your Hugging Face token (hf_...) and press Enter: ").strip()
ds = load_dataset("LouisChen15/ConstructionSite", split="test", streaming=True, token=token)   # streams; no full download
print("Connected. Downloading the first block of test photos (can take 2-5 minutes, please wait)...")
got = {"helmet_violation": 0, "no_violation": 0}
rows = []
for i, rec in enumerate(ds):
    if i % 100 == 0:
        print(f"  scanned {i} photos...")
    has, reason = rule1(rec)
    group = "helmet_violation" if (has and HELMET_WORDS.search(reason)) else ("no_violation" if not has else None)
    if group is None or got[group] >= args.n:
        continue
    got[group] += 1
    name = f"{group}_{got[group]:02d}.jpg"
    rec["image"].convert("RGB").save(out / name, quality=92)
    rows.append({"file": name, "expected": group, "expert_reason": reason, "caption": rec.get("image_caption", "")})
    print("saved", name)
    if all(v >= args.n for v in got.values()):
        break

with open(out / "expected_labels.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["file", "expected", "expert_reason", "caption"])
    w.writeheader(); w.writerows(rows)
print(f"Done: {len(rows)} photos in {out.resolve()} (see expected_labels.csv)")
