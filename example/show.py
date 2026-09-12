#!/usr/bin/env python3
"""Print the numbers a claim file publishes, straight from example/data.json.

A receipt is normally a command that already exists in the repository (a counter,
a build step, a validator). This fake one exists so the example is runnable.
"""

import json
from pathlib import Path

data = json.loads((Path(__file__).parent / "data.json").read_text(encoding="utf-8"))
print(f"{data['restaurants']}{data['visits']}")
