"""SafeVision heat maps for the YOLO detector: EigenCAM (Muhammad & Yeasin, 2020).

EigenCAM needs no gradients and no class score, so it works with any detector: it takes the feature maps
the detector uses to find objects (the three inputs of the YOLO Detect head, small / medium / large
objects), finds the main pattern in them (first principal component, via SVD) and shows where that
pattern is strong. Bright areas = the parts of the photo the detector paid most attention to.
"""
import numpy as np


def eigen_projection(act):
    """(C, H, W) activations -> (H, W) map along the first principal component (EigenCAM)."""
    c, h, w = act.shape
    x = act.reshape(c, -1).T                      # (H*W, C)
    x = x - x.mean(0, keepdims=True)
    _, _, vt = np.linalg.svd(x, full_matrices=False)
    proj = (x @ vt[0]).reshape(h, w)
    strength = np.linalg.norm(act, axis=0)        # SVD sign is arbitrary: make the map follow strong activations
    if np.corrcoef(proj.ravel(), strength.ravel())[0, 1] < 0:
        proj = -proj
    proj = np.maximum(proj, 0)
    return proj / (proj.max() + 1e-8)


class DetectorCAM:
    def __init__(self, yolo, imgsz=640, device="cpu"):
        import torch
        self.torch, self.imgsz, self.device = torch, int(np.ceil(imgsz / 32) * 32), device
        self.net = yolo.model.to(device).eval()
        head = self.net.model[-1]                    # Detect layer; .f = indices of its input layers
        self.layers = [self.net.model[i] for i in head.f]
        self.acts = []

    def heatmap(self, image):
        """PIL image -> (H, W) float map in [0, 1] at the photo's size."""
        torch = self.torch
        from PIL import Image
        img = image.convert("RGB")
        x = torch.from_numpy(np.asarray(img.resize((self.imgsz, self.imgsz)), dtype=np.float32) / 255.)
        x = x.permute(2, 0, 1)[None].to(self.device)
        x = x.half() if next(self.net.parameters()).dtype == torch.float16 else x
        self.acts = []
        hooks = [l.register_forward_hook(lambda m, i, o: self.acts.append(o.detach().float().cpu().numpy()[0])) for l in self.layers]
        try:
            with torch.no_grad():
                self.net(x)
        finally:
            for h in hooks:
                h.remove()
        maps = [np.asarray(Image.fromarray((eigen_projection(a) * 255).astype(np.uint8)).resize(img.size, Image.BILINEAR),
                           dtype=np.float32) / 255. for a in self.acts]
        m = np.mean(maps, axis=0)                     # small + medium + large object scales together
        return m / (m.max() + 1e-8)

    @staticmethod
    def overlay(image, heat, alpha=0.45):
        """Heat map drawn over the photo (blue = low, red = high)."""
        from PIL import Image
        import matplotlib
        rgb = (matplotlib.colormaps["jet"](heat)[..., :3] * 255).astype(np.uint8)
        return Image.blend(image.convert("RGB"), Image.fromarray(rgb), alpha)
