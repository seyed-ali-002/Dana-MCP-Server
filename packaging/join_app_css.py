#!/usr/bin/env python3
import base64, gzip
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
parts = sorted((ROOT/"packaging"/"css_parts").glob("part_*"))
b64 = "".join(p.read_text().strip() for p in parts)
data = gzip.decompress(base64.b64decode(b64))
(ROOT/"ui"/"src"/"App.css").write_bytes(data)
print("restored App.css", len(data))
