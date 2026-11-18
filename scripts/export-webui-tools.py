"""Regenerate the Open WebUI import file after editing workspace_tools.py."""

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
bundle = [{
    "id": "spark_workspace",
    "name": "Spark Workspace",
    "content": (root / "workspace_tools.py").read_text(),
    "meta": {"description": "Search local notes and explore CSV datasets on the Spark."},
}]
target = root / "examples" / "openwebui-tools.json"
target.write_text(json.dumps(bundle, indent=2) + "\n")
print(f"Ready to import: {target}")
