"""Build results/SafeVision_Results.xlsx from the experiment logs of all notebooks.

Usage:  python scripts/merge_results.py [folder]      (default folder: results/logs)
Put each notebook's results folder (or its experiments_log.csv) anywhere under the folder, e.g.
results/logs/nb1x/experiments_log.csv. Every experiments_log.csv found is read.

Sheets
  Summary    one row per experiment: the question, the setting and the headline number (for the report tables)
  Ablations  every "with vs without" comparison (the Ablation Studies section of the paper)
  Detector   per-class detection results (E1, E1x, E2, E2b)
  log_<nb>   the raw log of each notebook
A value shows as "pending" when that notebook's log is not in the folder yet.
"""
import sys
from pathlib import Path
import pandas as pd

RAW = Path(sys.argv[1] if len(sys.argv) > 1 else "results/logs")
OUT = Path("results/SafeVision_Results.xlsx")
OUT.parent.mkdir(exist_ok=True)

logs = {}
for csv in sorted(RAW.rglob("experiments_log.csv")):
    df = pd.read_csv(csv)
    df["experiment"] = df["experiment"].astype(str)
    logs[csv.parent.name if csv.parent.name != "results" else csv.parent.parent.name] = df
    print(f"{csv}: {len(df)} rows, {sorted(df.experiment.unique())}")
ALL = pd.concat(logs.values(), ignore_index=True) if logs else pd.DataFrame(columns=["experiment", "run", "metric", "value"])


def v(run, metric, **f):
    """Value of one metric of one run (extra column filters allowed), or 'pending'."""
    d = ALL[(ALL.run.astype(str) == run) & (ALL.metric == metric)]
    for k, x in f.items():
        if k in d:
            d = d[d[k].astype(str) == str(x)]
    return round(float(d.value.iloc[-1]), 3) if len(d) else "pending"


# ------------------------------------------------------------------ Summary
S = [
    ("E1", "NB1", "How well does the 4-class detector find person/head/helmet/vest? (SH17 test)", "YOLO11s, 960 px", "mAP50", v("E1b_yolo11s_960", "mAP50", class_name="all")),
    ("E1x", "NB1x", "Same, 8-class detector (adds hands, gloves, face, glasses)", "YOLO11s, 960 px", "mAP50", v("E1x_yolo11s_960_ppe8", "mAP50", class_name="all")),
    ("E2", "NB1x", "Generalisation to a dataset never trained on (CHV)", "8-class detector", "mAP50", v("E2_E1x_on_CHV", "mAP50", class_name="all")),
    ("E2b", "NB1x", "Generalisation to Construction-PPE (incl. gloves, glasses)", "8-class detector", "mAP50", v("E2b_E1x_on_CPPE", "mAP50", class_name="all")),
    ("E3a", "NB2", "Photo-level helmet violations, ConstructionSite 10k test (2,956 photos)", "4-class + box matching", "F1", v("E3a_box_matching", "F1")),
    ("E3e", "NB2z", "Same benchmark, final detector", "8-class + box matching", "F1", v("E3e_box_matching", "F1")),
    ("E3f", "NB2z", "Same benchmark, final system (as in the web app)", "8-class + zoom re-check", "F1", v("E3f_box+zoom_matching", "F1")),
    ("E3x", "NB2x", "Missing gloves per photo, Construction-PPE val", "matching + zoom", "F1", v("E3x_gloves_matching+zoom", "F1", subset="clear")),
    ("E3x", "NB2x", "Missing safety glasses per photo, Construction-PPE val", "matching", "F1", v("E3x_glasses_matching", "F1", subset="clear")),
    ("E3x", "NB2x", "Missing hard hat per photo, Construction-PPE val", "matching + zoom", "F1", v("E3x_helmet_matching+zoom", "F1", subset="clear")),
    ("E3x", "NB2x", "Missing vest per photo, Construction-PPE val", "matching + zoom", "F1", v("E3x_vest_matching+zoom", "F1", subset="clear")),
    ("E4", "NB2", "Robustness: short vs long camera distance (helmet F1)", "4-class + box", "F1 short / long",
     f'{v("E4_box", "F1", class_name="camera_distance=short distance")} / {v("E4_box", "F1", class_name="camera_distance=long distance")}'),
    ("E5", "NB3", "Accident type / body part / severity from text (OSHA SIR test years)", "DistilBERT multi-task, context-only", "macro-F1 (type)",
     v("E5c_distilbert_context_only", "macro_F1", target="event_group")),
    ("E6", "NB4", "Find the right safety rule for a question", "hybrid (BM25+dense, RRF) + re-ranker", "Recall@3", v("E6a_hybrid + re-ranker_200w", "Recall@3")),
    ("E7", "NB3", "Are retrieved past accidents of the same type?", "bge-small embeddings", "precision@3", v("E7_bge-small", "precision_at_3", target="event_group")),
    ("E8a", "NB5", "Share of report sentences supported by evidence", "LLM + rules + risk + fact-check loop (V3)", "supported %", v("E8a_V3_llama3.1:8b", "supported_pct")),
    ("E8c", "NB5", "Does the fact checker catch invented rule ids?", "NLI DeBERTa-v3 + id check", "detection rate", v("E8c_fake_rule", "detection_rate")),
    ("E9", "NB5", "Time for the vision step per photo", "detector + matching", "ms", v("E9_latency", "ms_per_image", variant="vision (detector + matching)")),
    ("E10", "NB6", "Most faithful word explanation (200 OSHA test reports)", "LIME (winner)", "faithfulness", v("E10a_lime", "faithfulness")),
    ("E11", "NB7", "Construction scene captions, ConstructionSite test (500 photos)", "Florence-2-base fine-tuned", "CIDEr", v("E11a_fine-tuned", "CIDEr")),
]
summary = pd.DataFrame(S, columns=["experiment", "notebook", "question", "setting", "metric", "value"])

# ------------------------------------------------------------------ Ablations
A = [
    # component, ablation, variant A, value A, variant B, value B, metric
    ("Detector", "Input size", "640 px (E1a)", v("E1a_yolo11s_640", "mAP50", class_name="all"), "960 px (E1b)", v("E1b_yolo11s_960", "mAP50", class_name="all"), "mAP50, SH17"),
    ("Detector", "Test-time augmentation", "off (E1b)", v("E1b_yolo11s_960", "mAP50", class_name="all"), "on (E1d)", v("E1d_TTA_on_E1b", "mAP50", class_name="all"), "mAP50, SH17"),
    ("Detector", "Number of classes (helmet)", "4 classes", v("E1b_yolo11s_960", "mAP50", class_name="helmet"), "8 classes", v("E1x_yolo11s_960_ppe8", "mAP50", class_name="helmet"), "helmet mAP50, SH17"),
    ("Detector", "Number of classes (vest)", "4 classes", v("E1b_yolo11s_960", "mAP50", class_name="vest"), "8 classes", v("E1x_yolo11s_960_ppe8", "mAP50", class_name="vest"), "vest mAP50, SH17"),
    ("Matching", "Box vs pose matching", "box (E3a)", v("E3a_box_matching", "F1"), "pose (E3b)", v("E3b_pose_matching", "F1"), "F1, CS10k helmet"),
    ("Matching", "Zoom re-check (CS10k)", "off (E3e)", v("E3e_box_matching", "F1"), "on (E3f)", v("E3f_box+zoom_matching", "F1"), "F1, CS10k helmet"),
    ("Matching", "Zoom re-check (hard hat)", "off", v("E3x_helmet_matching", "F1", subset="clear"), "on", v("E3x_helmet_matching+zoom", "F1", subset="clear"), "F1, Construction-PPE val"),
    ("Matching", "Zoom re-check (gloves)", "off", v("E3x_gloves_matching", "F1", subset="clear"), "on", v("E3x_gloves_matching+zoom", "F1", subset="clear"), "F1, Construction-PPE val"),
    ("Matching", "Zoom re-check (glasses)", "off", v("E3x_glasses_matching", "F1", subset="clear"), "on", v("E3x_glasses_matching+zoom", "F1", subset="clear"), "F1, Construction-PPE val"),
    ("Matching", "Per-worker matching vs detector only (gloves)", "detector only", v("E3x_gloves_detector-only", "F1", subset="clear"), "matching + zoom", v("E3x_gloves_matching+zoom", "F1", subset="clear"), "F1, Construction-PPE val"),
    ("Classifier", "Model", "TF-IDF + LogReg", v("E5a_tfidf_context-only", "macro_F1", target="event_group"), "DistilBERT", v("E5c_distilbert_context_only", "macro_F1", target="event_group"), "macro-F1 accident type"),
    ("Classifier", "Outcome words in the input (leakage)", "full text", v("E5b_distilbert_full", "macro_F1", target="body_group"), "context only (used)", v("E5c_distilbert_context_only", "macro_F1", target="body_group"), "macro-F1 body part"),
    ("Rule search", "Retriever", "BM25", v("E6a_BM25_200w", "Recall@3"), "hybrid + re-ranker", v("E6a_hybrid + re-ranker_200w", "Recall@3"), "Recall@3"),
    ("Rule search", "Re-ranker", "hybrid (RRF)", v("E6a_hybrid (RRF)_200w", "Recall@3"), "hybrid + re-ranker", v("E6a_hybrid + re-ranker_200w", "Recall@3"), "Recall@3"),
    ("Rule search", "Chunk size", "100 words", v("E6b_hybrid + re-ranker_100w", "Recall@3"), "400 words", v("E6b_hybrid + re-ranker_400w", "Recall@3"), "Recall@3 (with re-ranker)"),
    ("Similar accidents", "Retriever", "BM25", v("E7_BM25", "precision_at_3", target="event_group"), "bge-small embeddings", v("E7_bge-small", "precision_at_3", target="event_group"), "precision@3"),
    ("Report writer", "Grounding (rules + risk in prompt)", "findings only (V1)", v("E8a_V1_llama3.1:8b", "supported_pct"), "+ rules + risk (V2)", v("E8a_V2_llama3.1:8b", "supported_pct"), "supported sentences %"),
    ("Report writer", "Fact-check correction loop", "without (V2)", v("E8a_V2_llama3.1:8b", "supported_pct"), "with (V3)", v("E8a_V3_llama3.1:8b", "supported_pct"), "supported sentences %"),
    ("Report writer", "Invented rule ids", "findings only (V1)", v("E8a_V1_llama3.1:8b", "invented_citations_per_report"), "with rules (V2)", v("E8a_V2_llama3.1:8b", "invented_citations_per_report"), "invented ids per report"),
    ("Explanations", "Method", "SHAP", v("E10a_shap", "faithfulness"), "LIME", v("E10a_lime", "faithfulness"), "faithfulness (comp - suff)"),
    ("Explanations", "Method vs random", "random words", v("E10a_random", "faithfulness"), "LIME", v("E10a_lime", "faithfulness"), "faithfulness (comp - suff)"),
    ("Captioner", "Fine-tuning", "pretrained", v("E11a_pretrained", "CIDEr"), "fine-tuned", v("E11a_fine-tuned", "CIDEr"), "CIDEr"),
    ("Captioner", "Fine-tuning (meaning)", "pretrained", v("E11a_pretrained", "BERTScore_F1"), "fine-tuned", v("E11a_fine-tuned", "BERTScore_F1"), "BERTScore-F1"),
]
abl = pd.DataFrame(A, columns=["component", "ablation", "variant A", "A", "variant B", "B", "metric"])
abl["B - A"] = [round(b - a, 3) if isinstance(a, float) and isinstance(b, float) else "" for a, b in zip(abl.A, abl.B)]

# ------------------------------------------------------------------ Detector per class
det = ALL[ALL.experiment.isin(["E1", "E1x", "E2", "E2b"]) & ALL.metric.isin(["mAP50", "mAP50_95", "precision", "recall"])] if "class_name" in ALL else ALL.iloc[:0]
if len(det):
    det = det.pivot_table(index=["experiment", "run", "dataset", "class_name"], columns="metric", values="value").round(3).reset_index()

with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
    summary.to_excel(xw, sheet_name="Summary", index=False)
    abl.to_excel(xw, sheet_name="Ablations", index=False)
    det.to_excel(xw, sheet_name="Detector", index=False)
    for name, df in logs.items():
        df.drop(columns=[c for c in ("timestamp",) if c in df]).to_excel(xw, sheet_name=f"log_{name}"[:31], index=False)
    for ws in xw.book.worksheets:                        # readable column widths
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(60, max(10, max(len(str(c.value or "")) for c in col) + 2))
print("Wrote", OUT, "| pending:", int((summary.value == "pending").sum()), "summary rows,",
      int((abl.A == "pending").sum() + (abl.B == "pending").sum()), "ablation values")
