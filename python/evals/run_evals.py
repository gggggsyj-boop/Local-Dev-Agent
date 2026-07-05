from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
RESULTS_PATH = THIS_DIR / "eval_results.json"


def main() -> int:
    start = time.time()
    suite = unittest.defaultTestLoader.discover(str(THIS_DIR), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    payload = {
        "success": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "duration_seconds": round(time.time() - start, 3),
        "scope": [
            "tool schema and deferred tool activation",
            "permission modes and project permission rules",
            "read-before-edit and mtime freshness protection",
            "tool result truncation",
            "context budget truncation, stale-result snip, and microcompact",
            "large tool-result persistence",
            "frontmatter parsing and memory index CRUD",
        ],
    }
    RESULTS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote eval summary to {RESULTS_PATH}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

