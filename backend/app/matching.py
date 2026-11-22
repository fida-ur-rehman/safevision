"""SafeVision worker matching (step V2).

Turns raw detector boxes into one record per worker with a status for each PPE item:
"yes", "no" or "unsure" ("n/a" if the detector cannot see that item).
  * 4-class detector (Notebook 1):  person, head, helmet, vest
  * 8-class detector (Notebook 1x): + hands, gloves, face, glasses
Each item is checked on its own body part: helmet on the head, vest on the torso,
gloves on the hands, safety glasses on the face.

Two ways to find where a worker's head and torso are:
  * "box":  fixed fractions of the person box (top 30% = head area,
            20-65% = torso area). Simple, no extra model.
  * "pose": body keypoints from YOLO11-pose (nose/eyes/ears = head,
            shoulders/hips = torso), following the idea of matching PPE
            to body parts with pose estimation (Lopez et al., 2025, paper [4]).
If pose keypoints are missing for a person, "pose" falls back to "box".

The same file is used by Notebook 2 (experiments E3/E4) and by the backend,
so the app behaves exactly like the evaluated system.
"""
from __future__ import annotations

CLASSES = ["person", "head", "helmet", "vest", "hands", "gloves", "face", "glasses"]
# PPE item -> (bare body-part class that proves it is missing, PPE class that proves it is worn)
EXTRA_ITEMS = {"gloves": ("hands", "gloves"), "glasses": ("face", "glasses")}

# COCO keypoint indices used by YOLO11-pose
HEAD_KPTS = [0, 1, 2, 3, 4]          # nose, left/right eye, left/right ear
TORSO_KPTS = [5, 6, 11, 12]          # left/right shoulder, left/right hip


# ----------------------------------------------------------------- geometry
def area(b):
    """Area of an [x1, y1, x2, y2] box (0 if the box is empty)."""
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def intersection(a, b):
    """Area where two boxes overlap."""
    return area([max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])])


def iou(a, b):
    """Intersection over union of two boxes (0 = no overlap, 1 = identical)."""
    inter = intersection(a, b)
    union = area(a) + area(b) - inter
    return inter / union if union > 0 else 0.0


def inside_fraction(inner, outer):
    """Share of `inner` that lies inside `outer` (e.g. how much of a helmet is in the head area)."""
    a = area(inner)
    return intersection(inner, outer) / a if a > 0 else 0.0


# ------------------------------------------------------------ detections
def detections_from_result(result, min_conf=0.10):
    """Convert one Ultralytics detection result into {class_name: [(box, conf), ...]}."""
    names = result.names
    known = set(names.values()) if isinstance(names, dict) else set(names)
    dets = {c: [] for c in CLASSES if c in known or c in ("person", "head", "helmet", "vest")}   # missing classes -> "n/a"
    for box, conf, cls in zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist(), result.boxes.cls.tolist()):
        name = names[int(cls)]
        if name in dets and conf >= min_conf:
            dets[name].append((box, float(conf)))
    return dets


# ------------------------------------------------------- zoom re-check
ZOOM_ITEMS = {"helmet": ("head", "helmet"), "vest": ("vest",), "gloves": ("hands", "gloves"), "glasses": ("face", "glasses")}


def zoom_detections(model, image, person_boxes, imgsz=640, conf=0.03, pad=0.5, items=("helmet", "vest", "gloves")):
    """Zoom re-check: crop every detected worker (box grown by `pad`, 50 % keeps enough context), run the detector again on the enlarged crop
    and return the PPE / body-part boxes in full-image coordinates. Small helmets, gloves and faces become large
    enough to detect (the idea of SAHI slicing, Akyon et al. 2022, focused on each person). Only the classes of
    `items` are returned (Notebook 2x decides which items profit)."""
    keep = {c for it in items for c in ZOOM_ITEMS[it]}
    W, H = image.size
    crops, offsets = [], []
    for b in person_boxes:
        x1, y1, x2, y2 = expand(b, pad)
        x1, y1, x2, y2 = max(0, int(x1)), max(0, int(y1)), min(W, int(x2)), min(H, int(y2))
        if x2 - x1 > 4 and y2 - y1 > 4:
            crops.append(image.crop((x1, y1, x2, y2))); offsets.append((x1, y1))
    out = []
    if not crops:
        return out
    for (ox, oy), r in zip(offsets, model.predict(crops, imgsz=imgsz, conf=conf, verbose=False)):
        for b, s, c in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), r.boxes.cls.tolist()):
            name = r.names[int(c)]
            if name in keep:
                out.append((name, [b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy], float(s)))
    return out


def merge_detections(dets, extra, min_conf=0.10, same_iou=0.5):
    """Add zoomed boxes to a {class: [(box, conf)]} dict. A zoomed box that overlaps a box of the same class
    (IoU > same_iou) is the same object: only the more confident of the two is kept."""
    for name, b, s in extra:
        if s < min_conf or name not in dets:
            continue
        same = [i for i, (ob, oc) in enumerate(dets[name]) if iou(ob, b) > same_iou]
        if not same:
            dets[name].append((b, s))
        else:
            i = max(same, key=lambda k: dets[name][k][1])
            if s > dets[name][i][1]:
                dets[name][i] = (b, s)
    return dets


def poses_from_result(result, kpt_conf=0.5):
    """Convert one YOLO11-pose result into a list of (person_box, {kpt_index: (x, y)})."""
    out = []
    if result.keypoints is None:
        return out
    xy = result.keypoints.xy.tolist()
    kc = result.keypoints.conf.tolist() if result.keypoints.conf is not None else None
    for i, box in enumerate(result.boxes.xyxy.tolist()):
        pts = {}
        for k, (x, y) in enumerate(xy[i]):
            if kc is None or kc[i][k] >= kpt_conf:
                pts[k] = (x, y)
        out.append((box, pts))
    return out


# ------------------------------------------------------- body regions
def box_regions(p):
    """Head and torso areas as fixed fractions of a person box (method 'box')."""
    x1, y1, x2, y2 = p
    h = y2 - y1
    head = [x1, y1 - 0.05 * h, x2, y1 + 0.30 * h]      # a little above the box too: helmets stick out
    torso = [x1, y1 + 0.20 * h, x2, y1 + 0.65 * h]
    return head, torso


def pose_regions(p, pose_list):
    """Head and torso areas from the best-matching pose skeleton (method 'pose'); None if unavailable."""
    best, best_iou = None, 0.5                          # pose person must overlap the detected person well
    for pbox, pts in pose_list:
        v = iou(p, pbox)
        if v > best_iou:
            best, best_iou = pts, v
    if best is None:
        return None
    head_pts = [best[k] for k in HEAD_KPTS if k in best]
    torso_pts = [best[k] for k in TORSO_KPTS if k in best]
    if len(head_pts) < 2 or len(torso_pts) < 2:
        return None
    ph = p[3] - p[1]
    hx = [x for x, _ in head_pts]; hy = [y for _, y in head_pts]
    cx, cy = sum(hx) / len(hx), sum(hy) / len(hy)
    s = max(max(hx) - min(hx), max(hy) - min(hy), 0.08 * ph)
    head = [cx - 1.2 * s, cy - 2.0 * s, cx + 1.2 * s, cy + 0.8 * s]     # helmets sit above the eyes
    tx = [x for x, _ in torso_pts]; ty = [y for _, y in torso_pts]
    pad = 0.1 * (max(tx) - min(tx) + 1)
    torso = [min(tx) - pad, min(ty) - pad, max(tx) + pad, max(ty) + pad]
    return head, torso


def expand(b, f):
    """Box grown by a fraction f of its size on every side (hands stick out of the person box)."""
    w, h = b[2] - b[0], b[3] - b[1]
    return [b[0] - f * w, b[1] - f * h, b[2] + f * w, b[3] + f * h]


def covered(b, items, thr=0.3):
    """True if box b overlaps one of the boxes in items (e.g. a 'hands' box that is really a gloved hand)."""
    return any(iou(b, o) > thr or inside_fraction(b, o) > 0.6 for o, _ in items)


def _item_status(dets, item, region, used, conf_yes, conf_no):
    """Status of an extra PPE item (gloves on hands, glasses on face) inside one body region."""
    bare_cls, ppe_cls = EXTRA_ITEMS[item]
    if bare_cls not in dets or ppe_cls not in dets:
        return "n/a", 0.0
    ppe = _best(dets[ppe_cls], region, 0.5, used.setdefault(ppe_cls, set()))
    if ppe and ppe[2] >= conf_yes:
        used[ppe_cls].add(ppe[0])
        return "yes", ppe[2]
    bare = [(i, b, c) for i, (b, c) in enumerate(dets[bare_cls])
            if i not in used.setdefault(bare_cls, set()) and inside_fraction(b, region) >= 0.5 and c >= conf_no
            and not covered(b, dets[ppe_cls])]
    if bare:
        i, b, c = max(bare, key=lambda t: t[2]); used[bare_cls].add(i)
        return "no", c
    return "unsure", ppe[2] if ppe else 0.0


def _best(items, region, min_inside, used):
    """Highest-confidence item (index, box, conf) mostly inside `region` and not used by another worker."""
    best = None
    for i, (b, c) in enumerate(items):
        if i in used:
            continue
        if inside_fraction(b, region) >= min_inside and (best is None or c > best[2]):
            best = (i, b, c)
    return best


# ------------------------------------------------------------ main function
def match_workers(dets, img_h, pose_list=None, method="box", conf_yes=0.40, conf_no=0.40,
                  min_person_conf=0.30, item_conf=None):
    """Assign helmets, heads and vests to workers.

    Returns a list of worker dicts:
      box, source ('person' or 'head-only'), person_conf,
      helmet ('yes'/'no'/'unsure'), helmet_conf, vest ('yes'/'no'/'unsure'), vest_conf.

    Rules (helmet):  matched helmet with conf >= conf_yes            -> 'yes'
                     else matched bare head with conf >= conf_no      -> 'no'
                     else                                             -> 'unsure'
    Gloves / glasses (8-class detector only):
                     PPE box (gloves / glasses) on the hand / face area, conf >= conf_yes -> 'yes'
                     else a bare hand / face there (not overlapping a PPE box), conf >= conf_no -> 'no'
                     else -> 'unsure' (hands or face not visible); 'n/a' with the 4-class detector
    Rules (vest):    matched vest with conf >= conf_yes               -> 'yes'
                     else person clearly visible (conf >= 0.5 and
                          at least 15% of the image height)           -> 'no'
                     else                                             -> 'unsure'
    item_conf: optional {"gloves": (conf_yes, conf_no), "glasses": (...)} to tune those items separately
    (tuned in Notebook 2x, experiment E3x); otherwise they use conf_yes / conf_no.
    Bare heads that belong to no detected person (occlusion, crowds) become
    extra 'head-only' workers, so a hidden body does not hide a missing helmet.
    """
    workers = []
    item_conf = item_conf or {}
    gy, gn = item_conf.get("gloves", (conf_yes, conf_no))
    ey, en = item_conf.get("glasses", (conf_yes, conf_no))
    used = {"head": set(), "helmet": set(), "vest": set()}
    persons = sorted([p for p in dets["person"] if p[1] >= min_person_conf], key=lambda t: -t[1])
    for pbox, pconf in persons:
        regions = pose_regions(pbox, pose_list) if (method == "pose" and pose_list) else None
        head_r, torso_r = regions if regions else box_regions(pbox)
        helmet = _best(dets["helmet"], head_r, 0.5, used["helmet"])
        head = _best(dets["head"], head_r, 0.5, used["head"])
        vest = _best(dets["vest"], torso_r, 0.3, used["vest"])
        for key, hit in (("helmet", helmet), ("head", head), ("vest", vest)):
            if hit:
                used[key].add(hit[0])
        if helmet and helmet[2] >= conf_yes:
            h_status, h_conf = "yes", helmet[2]
        elif head and head[2] >= conf_no:
            h_status, h_conf = "no", head[2]
        else:
            h_status, h_conf = "unsure", max([x[2] for x in (helmet, head) if x] or [0.0])
        visible = pconf >= 0.5 and (pbox[3] - pbox[1]) >= 0.15 * img_h
        if vest and vest[2] >= conf_yes:
            v_status, v_conf = "yes", vest[2]
        elif visible:
            v_status, v_conf = "no", pconf
        else:
            v_status, v_conf = "unsure", vest[2] if vest else 0.0
        g_status, g_conf = _item_status(dets, "gloves", expand(pbox, 0.15), used, gy, gn)
        e_status, e_conf = _item_status(dets, "glasses", head_r, used, ey, en)
        workers.append(dict(box=pbox, source="person", person_conf=pconf, helmet=h_status,
                            helmet_conf=h_conf, vest=v_status, vest_conf=v_conf,
                            gloves=g_status, gloves_conf=g_conf, glasses=e_status, glasses_conf=e_conf))
    # Bare heads with no person around them -> extra workers without a helmet.
    for i, (hb, hc) in enumerate(dets["head"]):
        if i in used["head"] or hc < conf_no:
            continue
        if any(iou(hb, hl) > 0.3 or inside_fraction(hl, hb) > 0.5 for hl, _ in dets["helmet"]):
            continue                                       # a helmet sits on this head
        workers.append(dict(box=hb, source="head-only", person_conf=0.0, helmet="no",
                            helmet_conf=hc, vest="unsure", vest_conf=0.0,
                            gloves="unsure" if "gloves" in dets else "n/a", gloves_conf=0.0,
                            glasses=_item_status(dets, "glasses", expand(hb, 0.1), used, ey, en)[0]
                            if "glasses" in dets else "n/a", glasses_conf=0.0))
    return workers


def image_has_helmet_violation(workers):
    """Image-level decision: at least one worker clearly without a helmet."""
    return any(w["helmet"] == "no" for w in workers)
