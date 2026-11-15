"""Compare unchanged legacy surfaces without DOM or coordinate calibration."""
from pathlib import Path
import json
from PIL import Image, ImageChops
TASK = Path(__file__).resolve().parent
results = {}
for name in ('job-list', 'job-review'):
    before = Image.open(TASK / f'shots/before/{name}.png').convert('RGB')
    after = Image.open(TASK / f'shots/after/{name}.png').convert('RGB')
    assert before.size == after.size
    delta = ImageChops.difference(before, after)
    count = sum(any(pixel) for pixel in delta.get_flattened_data())
    results[name] = {'different_pixels': count, 'size': list(before.size),
                     'max_channel_difference': max(max(channel) for channel in delta.getextrema())}
(TASK / 'pixel-comparison.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results))
assert all(row['different_pixels'] == 0 for row in results.values())
