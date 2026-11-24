"""Test the scene check on photos before trusting it in the demo.

Usage (backend folder, venv active):
    python scripts/check_scene.py ../test_photos              # all 16 site photos should say SITE
    python scripts/check_scene.py C:\\path\\to\\other\\photos     # selfies, rooms, streets should say NOT SITE
Prints one line per photo and a summary. Change the threshold with SCENE_MIN (default 0.5).
"""
import os, sys
from pathlib import Path
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.scene import SceneCheck

folder = Path(sys.argv[1] if len(sys.argv) > 1 else "../test_photos")
sc = SceneCheck(device=os.environ.get("SCENE_DEVICE", "cpu"), threshold=float(os.environ.get("SCENE_MIN", 0.5)))
print(f"Scene check model: {sc.name}\n")
photos = sorted(p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
n_site = 0
for p in photos:
    r = sc.check(ImageOps.exif_transpose(Image.open(p)).convert("RGB"))
    n_site += r["is_site"]
    print(f"{'SITE    ' if r['is_site'] else 'NOT SITE'}  score {r['site_score']:.2f}  best: {r['best_match']:<55} {p.name}")
print(f"\n{n_site} of {len(photos)} photos counted as a work site (threshold {sc.threshold}).")
