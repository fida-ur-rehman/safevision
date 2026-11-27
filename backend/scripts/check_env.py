"""Checks the backend set-up: loads every SafeVision model the app uses and captions one test photo.

Nothing is changed or saved. Run from the backend folder:
    python scripts/check_env.py <photo.jpg>
Uses the same device set-up as the app.
"""
import sys, time, traceback
from pathlib import Path

ok = True
keep = []                                   # keep models in memory, like the running app does
def step(name, fn):
    global ok
    t = time.time()
    try:
        out = fn(); print(f"[OK]   {name} ({time.time() - t:.1f} s)" + (f": {out}" if out else ""))
    except Exception as e:
        ok = False; print(f"[FAIL] {name}: {e}"); traceback.print_exc(limit=1)

import torch, transformers
dev = "cuda" if torch.cuda.is_available() else "cpu"
low = dev == "cuda" and torch.cuda.get_device_properties(0).total_memory < 6 * 1024 ** 3
aux = dev                                   # same as the app: GPU (fp16), CPU fallback only if the GPU is full
print("torch", torch.__version__, "| transformers", transformers.__version__, "| device", dev,
      torch.cuda.get_device_name(0) if dev == "cuda" else "", "| rule search + fact checker on", aux)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
M = Path(__file__).resolve().parents[1] / "models"
photo = Path(sys.argv[1]) if len(sys.argv) > 1 else next((Path(__file__).resolve().parents[2] / "test_photos").glob("*.jpg"))

from PIL import Image
img = Image.open(photo).convert("RGB")

def detector():
    y = __import__("ultralytics").YOLO(str(M / "detector_best.pt")); keep.append(y)
    return f"{len(y.predict(img, verbose=False, device=dev)[0].boxes)} boxes"
def classifier():
    c = __import__("app.classifier", fromlist=["x"]).AccidentClassifier(M / "accident_classifier", dev); keep.append(c)
    return c.predict("worker on a ladder near a roof edge")["event_group"][0]
def rules():
    r = __import__("app.rules", fromlist=["x"]).RuleSearch(M / "rule_index", aux); keep.append(r)
    return r.search("hard hat required", k=1)[0]["section"]
def checker():
    f = __import__("app.factcheck", fromlist=["x"]).FactChecker(device=aux); keep.append(f); return "loaded"
def caption():
    c = __import__("app.caption", fromlist=["x"]).Captioner(M / "florence2_captioner", dev); keep.append(c)
    return c.caption(img)[:220]

step("CUDA works", lambda: str(torch.ones(2, device=dev).sum().item()))
for name, fn in [("Detector", detector), ("Accident classifier", classifier), ("Rule search", rules),
                 ("Fact checker", checker), ("Florence-2 captioner", caption)]:
    step(name, fn)
if dev == "cuda":
    print(f"GPU memory in use: {torch.cuda.memory_allocated() / 1024 ** 3:.2f} GB")
print("\nALL GOOD" if ok else "\nSome checks failed (see the messages above).")
