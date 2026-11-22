# SafeVision

**Explainable, per-worker PPE compliance checking with rule-grounded, fact-checked incident reports.**
MAAI901 (Deep Learning for Visual Data) and MAAI902 (NLP and LLMs) group project, University of Wollongong in Dubai.

SafeVision looks at a construction-site photo, finds every worker, checks **hard hat, high-visibility vest, gloves and
safety glasses on the right body part of each worker**, shows *where* the detector looked (heat map), predicts the most
likely accident from real OSHA construction injury reports, finds the safety rules that apply (OSHA 29 CFR 1926 and the
Dubai Municipality construction safety guide), and writes a short incident report in which **every sentence is checked
against the evidence**. A second page analyses a written incident description and shows which words drove the
prediction.

**The gap it addresses.** Most PPE systems check only hard hats and vests and do not say which worker is non-compliant;
large vision-language models such as GPT-4V produce many false alarms and unverifiable reasons on the ConstructionSite
10k benchmark (precision 0.20); and vision and safety-text analysis are usually studied separately. SafeVision combines
them into one explainable and verifiable pipeline.

```
photo ─► YOLO11s 8-class detector ─► zoom re-check of each worker ─► per-worker PPE matching ─┐
       └► Florence-2 scene caption (fine-tuned) ──────────────────────────────────────────────┤
                                                                                               ▼
   findings ─► DistilBERT accident classifier (+ LIME word explanation) ─► similar OSHA accidents (FAISS)
            ─► hybrid rule search (BM25 + embeddings + RRF + re-ranker) ─► LLM report (Groq gpt-oss-20b)
            ─► NLI fact checker (DeBERTa-v3) with one correction round ─► FastAPI ─► Next.js web app
```

## Repository layout

| Folder | What is inside |
|---|---|
| `notebooks/` | Training and evaluation notebooks (Colab or Kaggle). Every cell has a heading and explanation; each notebook ends with its references. |
| `backend/` | FastAPI API (`app/main.py`) and the pipeline modules. They are the **same code** that the notebooks evaluate. |
| `frontend/` | Next.js web app: Inspect a photo, Incident analysis, Rules assistant, History, PDF export. |
| `results/` | `SafeVision_Results.xlsx` (Summary, Ablations, per-class detector results) and the raw experiment logs. |
| `scripts/` | `merge_results.py` (rebuilds the results workbook), `export_test_photos.py`, `batch_test.py`. |
| `tests/` | Smoke tests: each notebook runs end to end on small fake data on a CPU (`python tests/test_nb.py <notebook> <fake_module>`). |
| `docs/` | Data contract examples and the NLP hand-over notes. |
| `test_photos/` | 16 ConstructionSite test photos with the expert labels (`expected_labels.csv`). |

## Notebooks and experiments

| Notebook | What it does | Experiments |
|---|---|---|
| `01_vision_detector` | 4-class detector (person, head, helmet, vest), SH17 | E1 (image size, test-time augmentation), E2 (CHV, never trained on) |
| `01x_ppe8_detector` | **8-class detector** (+ hands, gloves, face, glasses), used by the app | E1x, E2 (CHV), E2b (Construction-PPE) |
| `02_worker_matching_constructionsite` | Box vs pose matching of PPE to workers, ConstructionSite 10k | E3a-d, E4 (robustness) |
| `02x_ppe8_worker_matching` | Gloves / glasses / hard hat / vest per photo + zoom re-check, Construction-PPE | E3x |
| `02z_final_system_constructionsite` | The final vision system on the E3 benchmark | E3e, E3f, E4z |
| `03_accident_text_classifier_and_search` | DistilBERT multi-task classifier + similar-accident search, OSHA Severe Injury Reports | E5, E7 |
| `04_rule_search_rag` | Hybrid rule search over OSHA 1926 and the Dubai guide | E6a-c |
| `05_report_writer_fact_check` | Report variants V0-V3 and the NLI fact checker | E8a-c, E9 |
| `06_explainability_incident_analysis` | SHAP vs LIME vs Integrated Gradients, ERASER faithfulness | E10 |
| `07_florence2_caption_finetune` | Fine-tunes Florence-2-base on ConstructionSite captions | E11 |

Headline numbers and all ablations: `results/SafeVision_Results.xlsx` (rebuild with `python scripts/merge_results.py`).
Notebooks need a GPU and the secret `HF_TOKEN`; Notebook 5 also needs `GROQ_API_KEY`. Keys live only in Colab or Kaggle
Secrets and in `backend/.env`, never in the code.

## Run the web app

Tested on Windows with an NVIDIA GTX 1050 (4 GB); a CPU also works, only slower.

```bash
# 1) backend (Python 3.10-3.12)
cd backend
python -m venv .venv
.venv\Scripts\activate                    # Linux / Mac: source .venv/bin/activate
pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu121   # GPU; skip for CPU
pip install -r requirements.txt
python scripts/get_models.py              # downloads the trained models (about 1.2 GB, no account needed)
copy .env.example .env                    # then paste a free Groq key into .env (or set LLM_BACKEND=template)
python scripts/check_env.py ../test_photos/helmet_violation_01.jpg   # optional: checks every model loads
uvicorn app.main:app --port 8000

# 2) frontend (second terminal, Node 18+)
cd frontend
npm install
copy .env.local.example .env.local
npm run dev                               # open http://localhost:3000
```

## Privacy and ethics in the system

- **Faces are blurred** in every photo the app saves (History, heat map, PDF). The checks run on the original photo in memory. Switch: `BLUR_FACES` in `.env`.
- **Uncertainty is reported, not hidden:** a worker too small or hidden is "could not be checked", never "compliant".
- **Every report sentence is fact-checked**, and rule ids that were not retrieved are flagged.
- **No outcome leakage:** the accident classifier never sees injury-outcome words (it is trained on context only).
- The app supports a safety officer; it does not replace one.

## Trained models and data

The trained models are on Hugging Face (`Cypher4455/safevision-models`), shared for non-commercial research and education
because one training set (ConstructionSite 10k) is CC BY-NC 4.0. Datasets: SH17, CHV, Ultralytics Construction-PPE,
ConstructionSite 10k, OSHA Severe Injury Reports, OSHA 29 CFR 1926, Dubai Municipality construction safety guide.
