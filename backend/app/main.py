"""SafeVision API (FastAPI).

Endpoints
  GET  /health                 which models are loaded
  POST /analyze                upload a site photo -> workers, report, rules, risk, fact check (saved to history)
  GET  /incidents              history list (newest first)
  GET  /incidents/{id}         one saved result
  GET  /incidents/{id}/image   the uploaded photo
  GET  /incidents/{id}/heatmap EigenCAM heat map of the detector (where it looked)
  DELETE /incidents/{id}       remove one result
  POST /ask                    rule question -> top rules + grounded answer
  POST /incident-analysis      incident text -> accident type, word explanation (XAI), similar accidents, rules, summary

Run:  uvicorn app.main:app --reload --port 8000   (from the backend folder)
"""
import io, json, os, sqlite3, uuid, datetime
from pathlib import Path

try:                                              # read backend/.env if python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from PIL import Image, ImageOps

from .privacy import blur_regions
from .pipeline import Pipeline

DATA = Path(os.environ.get("SAFEVISION_DATA", Path(__file__).resolve().parents[1] / "data"))
(DATA / "images").mkdir(parents=True, exist_ok=True)
DB = DATA / "safevision.db"
MAX_SIDE = 1600                                   # large phone photos are shrunk before analysis

app = FastAPI(title="SafeVision API", version="1.0")
origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])
pipe = None


def clean(o):
    """Make a result JSON-safe: numpy numbers -> Python numbers, NaN -> None."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if hasattr(o, "item"):
        o = o.item()
    if isinstance(o, float) and o != o:
        return None
    return o


def db():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, created TEXT, filename TEXT, "
                "violation INTEGER, workers INTEGER, no_helmet INTEGER, no_vest INTEGER, result TEXT)")
    return con


@app.on_event("startup")
def load_models():
    global pipe
    pipe = Pipeline()
    if os.environ.get("WARM_UP", "1") == "1":      # set WARM_UP=0 to skip and start faster
        print("Warming up models:", pipe.warm_up())


@app.get("/health")
def health():
    return {"status": "ok", "device": pipe.device, "components": pipe.status}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...), fact_check: bool = True):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "Please upload an image file (JPG or PNG).")
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(await file.read()))).convert("RGB")
    except Exception:
        raise HTTPException(400, "The file could not be read as an image.")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    try:
        result = clean(pipe.analyze(img, fact_check=fact_check))
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    iid = uuid.uuid4().hex[:12]
    regions = result.pop("privacy_regions", [])
    blur = os.environ.get("BLUR_FACES", "1") != "0"           # privacy: stored photos have faces blurred
    (blur_regions(img, regions) if blur and regions else img).save(DATA / "images" / f"{iid}.jpg", quality=90)
    result["privacy"] = {"faces_blurred": len(regions) if blur else 0, "blur_on": blur}
    result.update(id=iid, created=datetime.datetime.now().isoformat(timespec="seconds"), filename=file.filename)
    with db() as con:
        con.execute("INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?)",
                    (iid, result["created"], file.filename, int(result["violation"]), result["counts"]["workers"],
                     result["counts"]["no_helmet"], result["counts"]["no_vest"], json.dumps(result)))
    return result


@app.get("/incidents")
def incidents(limit: int = 100):
    with db() as con:
        rows = con.execute("SELECT id, created, filename, violation, workers, no_helmet, no_vest FROM incidents "
                           "ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
    keys = ["id", "created", "filename", "violation", "workers", "no_helmet", "no_vest"]
    return [dict(zip(keys, r)) for r in rows]


@app.get("/incidents/{iid}")
def incident(iid: str):
    with db() as con:
        row = con.execute("SELECT result FROM incidents WHERE id = ?", (iid,)).fetchone()
    if not row:
        raise HTTPException(404, "Not found")
    return json.loads(row[0])


@app.get("/incidents/{iid}/image")
def incident_image(iid: str):
    p = DATA / "images" / f"{Path(iid).name}.jpg"
    if not p.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(p, media_type="image/jpeg")


@app.get("/incidents/{iid}/heatmap")
def incident_heatmap(iid: str):
    """EigenCAM heat map for a saved photo (made on first request, then cached)."""
    src = DATA / "images" / f"{Path(iid).name}.jpg"
    out = DATA / "images" / f"{Path(iid).name}_cam.jpg"
    if not src.exists():
        raise HTTPException(404, "Not found")
    if not out.exists():
        cam = pipe.heatmap(Image.open(src))
        if cam is None:
            raise HTTPException(503, "Detector not loaded")
        cam.save(out, quality=88)
    return FileResponse(out, media_type="image/jpeg")


@app.delete("/incidents/{iid}")
def delete_incident(iid: str):
    with db() as con:
        con.execute("DELETE FROM incidents WHERE id = ?", (iid,))
    (DATA / "images" / f"{Path(iid).name}.jpg").unlink(missing_ok=True)
    (DATA / "images" / f"{Path(iid).name}_cam.jpg").unlink(missing_ok=True)
    return {"deleted": iid}


class Question(BaseModel):
    question: str
    k: int = 3


@app.post("/ask")
def ask(q: Question):
    if not q.question.strip():
        raise HTTPException(400, "Empty question")
    try:
        return clean(pipe.ask(q.question.strip(), k=max(1, min(q.k, 8))))
    except RuntimeError as e:
        raise HTTPException(503, str(e))


class IncidentText(BaseModel):
    text: str
    method: str | None = None          # 'shap' | 'lime' | 'ig' (default: the winner of Notebook 6, xai_choice.json)
    fact_check: bool = True


@app.post("/incident-analysis")
def incident_analysis(body: IncidentText):
    text = body.text.strip()
    if len(text.split()) < 3:
        raise HTTPException(400, "Please describe the incident in at least a few words")
    if body.method and body.method not in ("shap", "lime", "ig"):
        raise HTTPException(400, "method must be shap, lime or ig")
    try:
        return clean(pipe.incident(text[:3000], method=body.method, fact_check=body.fact_check))
    except RuntimeError as e:
        raise HTTPException(503, str(e))
