"""Download the trained SafeVision models into backend/models (no account or token needed).

Usage (from the backend folder):   python scripts/get_models.py
Optional: SAFEVISION_MODELS_REPO=<user>/<repo> to use another copy.
"""
import os
from pathlib import Path
from huggingface_hub import snapshot_download

REPO = os.environ.get("SAFEVISION_MODELS_REPO", "Cypher4455/safevision-models")
MODELS = Path(__file__).resolve().parents[1] / "models"
MODELS.mkdir(exist_ok=True)
print(f"Downloading {REPO} (about 1.2 GB) into {MODELS} ...")
snapshot_download(REPO, local_dir=str(MODELS), ignore_patterns=["README.md", ".gitattributes"])
print("Done:", sorted(p.name for p in MODELS.iterdir() if not p.name.startswith(".")))
