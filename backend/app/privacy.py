"""SafeVision privacy: blur workers' faces in every photo the app SAVES (History, heat map, PDF export).

The analysis itself runs on the original photo in memory; only the stored copy is blurred. Faces come from the
8-class detector ('face' boxes). For heads without a detected face, the lower part of the head box (the face area
under a hard hat) is blurred too, so helmets stay visible. Turn off with BLUR_FACES=0 in backend/.env.
"""
from PIL import ImageFilter

from .matching import iou, inside_fraction


def privacy_regions(dets, face_conf=0.25, head_conf=0.35):
    """Face areas to blur, from a {class: [(box, conf)]} detection dict."""
    faces = [b for b, c in dets.get("face", []) if c >= face_conf]
    regions = list(faces)
    for b, c in dets.get("head", []):
        if c < head_conf or any(inside_fraction(f, b) > 0.5 or iou(f, b) > 0.2 for f in faces):
            continue
        x1, y1, x2, y2 = b
        regions.append([x1, y1 + 0.4 * (y2 - y1), x2, y2])        # face part of the head, below the hard hat
    return [[round(float(v), 1) for v in r] for r in regions]


def blur_regions(image, regions, pad=0.15):
    """Copy of the PIL image with each region strongly blurred (radius scales with the region size)."""
    img = image.copy()
    W, H = img.size
    for x1, y1, x2, y2 in regions:
        w, h = x2 - x1, y2 - y1
        box = (max(0, int(x1 - pad * w)), max(0, int(y1 - pad * h)), min(W, int(x2 + pad * w)), min(H, int(y2 + pad * h)))
        if box[2] - box[0] < 2 or box[3] - box[1] < 2:
            continue
        patch = img.crop(box)
        img.paste(patch.filter(ImageFilter.GaussianBlur(radius=max(3, 0.25 * max(w, h)))), box)
    return img
