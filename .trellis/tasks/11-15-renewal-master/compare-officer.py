"""Compare synthetic officer screenshots without reading application documents."""
from pathlib import Path
import json
from PIL import Image, ImageChops

root = Path(__file__).resolve().parent
rows = []
for name in ("programs", "list", "review"):
    before_path = root / "shots" / f"baseline-{name}.png"
    after_path = root / "shots" / f"final-{name}.png"
    if not before_path.is_file() or not after_path.is_file():
        rows.append({"screen": name, "result": "missing screenshot"})
        continue
    with Image.open(before_path) as before, Image.open(after_path) as after:
        result = {"screen": name, "baseline_size": list(before.size), "final_size": list(after.size)}
        if before.size != after.size:
            result["result"] = "different dimensions"
        else:
            delta = ImageChops.difference(before.convert("RGB"), after.convert("RGB"))
            changed = sum(any(pixel) for pixel in delta.getdata())
            result.update(result="identical" if changed == 0 else "changed", changed_pixels=changed,
                          changed_ratio=changed / (before.width * before.height))
        rows.append(result)
(root / "visual-pixel-comparison.json").write_text(json.dumps(rows, indent=2) + "\n")
print(json.dumps(rows, indent=2))
