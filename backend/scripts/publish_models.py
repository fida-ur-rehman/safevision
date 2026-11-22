"""Upload the trained SafeVision models from backend/models to a PUBLIC Hugging Face model repo (run once).

Only model weights and small config files are uploaded: no API keys, no photos, no datasets.
Usage (from the backend folder, with a WRITE token from huggingface.co -> Settings -> Access Tokens):
    python scripts/publish_models.py
"""
import getpass
from pathlib import Path
from huggingface_hub import HfApi

MODELS = Path(__file__).resolve().parents[1] / "models"
REPO_NAME = "safevision-models"
FILES = ["detector_best.pt", "run_config.json", "matching_thresholds.json", "matching_thresholds_ppe8.json", "xai_choice.json",
         "similar_accidents.faiss", "similar_accidents_config.json", "similar_accidents_meta.parquet"]
FOLDERS = ["accident_classifier", "rule_index", "florence2_captioner"]

CARD = """---
license: cc-by-nc-4.0
tags: [construction-safety, ppe-detection, yolo, florence-2, distilbert, rag, explainable-ai]
---
# SafeVision models

Trained models of **SafeVision** (MAAI901 / MAAI902 project, University of Wollongong in Dubai): explainable, per-worker
PPE compliance checking with rule-grounded, fact-checked incident reports. Code: see the project's GitHub repository.

| File / folder | What it is | Trained on |
|---|---|---|
| `detector_best.pt` | YOLO11s, 8 classes (person, head, helmet, vest, hands, gloves, face, glasses), 960 px | SH17 |
| `accident_classifier/` | DistilBERT multi-task (accident type, body part, severity), context-only text | OSHA Severe Injury Reports |
| `similar_accidents.*` | bge-small embeddings + FAISS index of OSHA construction narratives | OSHA Severe Injury Reports |
| `rule_index/` | Hybrid rule search index (BM25 + embeddings) over OSHA 29 CFR 1926 and the Dubai Municipality construction safety guide | public rule texts |
| `florence2_captioner/` | Florence-2-base fine-tuned for construction scene captions | ConstructionSite 10k captions |
| `*.json` | matching thresholds, explanation-method choice, run settings | Notebooks 2, 2x, 6 |

**Licences and attribution.** The Florence-2 captioner is fine-tuned on ConstructionSite 10k (Chen & Zou, CC BY-NC 4.0),
so these models are shared for **non-commercial research and education** only. The detector was trained with Ultralytics
YOLO11 (AGPL-3.0). Rule texts belong to their publishers (OSHA, Dubai Municipality). Please cite the original datasets.

**Limitations.** Small or distant workers are often reported as "could not be checked"; vests are the weakest class;
outputs must be confirmed by a qualified safety officer.
"""

token = getpass.getpass("Hugging Face WRITE token: ")
api = HfApi(token=token)
repo = f"{api.whoami()['name']}/{REPO_NAME}"
api.create_repo(repo, repo_type="model", private=False, exist_ok=True)
missing = [f for f in FILES + FOLDERS if not (MODELS / f).exists()]
if missing:
    print("Not found in backend/models (skipped):", missing)
(MODELS / "README.md").write_text(CARD, encoding="utf-8")
api.upload_folder(folder_path=str(MODELS), repo_id=repo,
                  allow_patterns=FILES + [f"{d}/**" for d in FOLDERS] + ["README.md"],
                  commit_message="SafeVision trained models")
(MODELS / "README.md").unlink()
print(f"Done: https://huggingface.co/{repo}")
