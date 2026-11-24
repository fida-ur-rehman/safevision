"""Scene check: is this photo a work site at all? (runs before the PPE check)

Without it, any photo with a person (a selfie, a classroom) would be analysed as a construction site and the
person reported as a worker missing a hard hat. We use CLIP (Radford et al., 2021) zero-shot: the photo is
compared with short text descriptions of work sites and of common other scenes, and the probabilities of the
work-site descriptions are added up. Below SCENE_MIN (default 0.5) the app stops and asks the user, who can
still choose "Analyse anyway". No training is involved, so the result is a gate, not a measured classifier.
"""
import torch

SITE = [
    "a photo of a construction site",
    "a photo of workers on a building site",
    "a photo of construction workers wearing hard hats",
    "a photo of road works with workers",
    "a photo of an industrial work site or factory floor",
    "a photo of scaffolding on a building under construction",
]
OTHER = [
    "a selfie",
    "a portrait photo of a person",
    "a photo of people at home",
    "a photo of an office",
    "a photo of a classroom or lecture hall",
    "a photo of a city street",
    "a photo of nature or a landscape",
    "a photo of food",
    "a photo of an animal",
    "a screenshot of a phone or computer screen",
    "a photo of a document or text",
]


class SceneCheck:
    # Loaded as safetensors only: transformers refuses the older .bin format with torch < 2.6 (CVE-2025-32434),
    # and safetensors cannot run code when loaded. The first model that has safetensors weights is used.
    CANDIDATES = ("openai/clip-vit-base-patch32", "openai/clip-vit-base-patch16", "laion/CLIP-ViT-B-32-laion2B-s34B-b79K")

    def __init__(self, model=None, device="cpu", threshold=0.5):
        from transformers import CLIPModel, CLIPProcessor
        self.device, self.threshold = device, threshold
        errors = []
        for name in ([model] if model else list(self.CANDIDATES)):
            try:
                self.model = CLIPModel.from_pretrained(name, use_safetensors=True).to(device).eval()
                self.proc = CLIPProcessor.from_pretrained(name)
                self.name = name
                break
            except Exception as e:
                errors.append(f"{name}: {str(e).splitlines()[0][:150]}")
        else:
            raise RuntimeError("No CLIP model with safetensors weights could be loaded. " + " | ".join(errors))
        self.labels = SITE + OTHER
        with torch.no_grad():   # text side is fixed: encode it once
            t = self.proc(text=self.labels, return_tensors="pt", padding=True).to(device)
            self.text = torch.nn.functional.normalize(self.model.get_text_features(**t), dim=-1)

    @torch.no_grad()
    def check(self, image):
        px = self.proc(images=image, return_tensors="pt").to(self.device)
        img = torch.nn.functional.normalize(self.model.get_image_features(**px), dim=-1)
        probs = (self.model.logit_scale.exp() * img @ self.text.T).softmax(-1)[0].cpu()
        site = float(probs[:len(SITE)].sum())
        best = int(probs.argmax())
        return {"is_site": site >= self.threshold, "site_score": round(site, 3),
                "best_match": self.labels[best], "threshold": self.threshold}
