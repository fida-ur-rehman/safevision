"""SafeVision scene captioner: Florence-2-base fine-tuned on ConstructionSite 10k captions (Notebook 7, experiment E11).

The caption describes the scene (activity, machines, heights, surroundings), which the box detector cannot.
It is added to the situation text used by the accident-type classifier and the similar-accident search.
"""
import json, shutil, tempfile
from pathlib import Path

TASK = "<MORE_DETAILED_CAPTION>"


class Captioner:
    def __init__(self, model_dir, device="cpu", max_new_tokens=160, num_beams=3):
        import torch
        from transformers import AutoProcessor, Florence2ForConditionalGeneration
        d = Path(model_dir)
        self.torch, self.device = torch, device
        self.dtype = torch.float16 if device.startswith("cuda") else torch.float32
        self.processor = AutoProcessor.from_pretrained(self._processor_dir(d))
        self.model = Florence2ForConditionalGeneration.from_pretrained(d, dtype=self.dtype).to(device).eval()
        self.max_new_tokens, self.num_beams = max_new_tokens, num_beams

    def caption(self, image):
        """One PIL image -> caption text."""
        torch = self.torch
        inputs = self.processor(text=TASK, images=image.convert("RGB"), return_tensors="pt").to(self.device)
        inputs["pixel_values"] = inputs["pixel_values"].to(self.dtype)
        with torch.no_grad():
            ids = self.model.generate(input_ids=inputs["input_ids"], pixel_values=inputs["pixel_values"],
                                      max_new_tokens=self.max_new_tokens, num_beams=self.num_beams)
        return self.processor.batch_decode(ids, skip_special_tokens=True)[0].strip()

    @staticmethod
    def _processor_dir(d):
        """The model was saved with transformers 5 (Colab). transformers 4.x expects 'extra_special_tokens' as a dict:
        make a converted copy of the small processor/tokenizer files in a temp folder. The model folder is never changed."""
        cfg = json.load(open(d / "tokenizer_config.json", encoding="utf-8"))
        if not isinstance(cfg.get("extra_special_tokens"), list):
            return d                                   # already in the format this transformers version expects
        tmp = Path(tempfile.mkdtemp(prefix="florence2_proc_"))
        for f in ("processor_config.json", "tokenizer.json", "preprocessor_config.json", "special_tokens_map.json"):
            if (d / f).exists():
                shutil.copy(d / f, tmp / f)
        cfg["additional_special_tokens"] = cfg.pop("extra_special_tokens")
        cfg["extra_special_tokens"] = cfg.pop("model_specific_special_tokens", None) or {"image_token": "<image>"}
        cfg["tokenizer_class"] = "BartTokenizer"
        cfg.pop("backend", None)
        json.dump(cfg, open(tmp / "tokenizer_config.json", "w", encoding="utf-8"), indent=1)
        return tmp
