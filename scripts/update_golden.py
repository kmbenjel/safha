"""Rewrite tests/golden/*.json from the current method (review the diff before committing it)."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))
from golden_util import FIXTURES, HERE, make

os.makedirs(os.path.join(HERE, "golden"), exist_ok=True)
for name in FIXTURES:
    with open(os.path.join(HERE, "golden", name.replace(".pdf", ".json")), "w", encoding="utf-8") as f:
        json.dump(make(name), f, indent=1)
    print("golden:", name)
