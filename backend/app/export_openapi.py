"""Write the OpenAPI document that the frontend types are generated from.

Usage: python -m app.export_openapi [path]   (default: ../frontend/openapi.json)"""

import json
import sys
from pathlib import Path

from app.main import app

DEFAULT = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    target.write_text(render(), encoding="utf-8")
    print(f"wrote {target}")
