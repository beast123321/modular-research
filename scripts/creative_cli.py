#!/usr/bin/env python3
"""CLI helpers for Phase 5 creative analysis handoff."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from creative.agent_bridge import import_analysis_response
from creative.runner import run_video_understanding
from evidence_store import EvidenceStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Modular Research V2 creative analysis bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    prep = sub.add_parser("prepare", help="prepare shortlist/media analysis requests for an existing run")
    prep.add_argument("--run-dir", required=True)
    prep.add_argument("--run-id", required=True)
    prep.add_argument("--limit", type=int, default=20)
    prep.add_argument("--download-media", action="store_true")

    imp = sub.add_parser("import-response", help="validate and persist one CreativeAnalysis response")
    imp.add_argument("--run-dir", required=True)
    imp.add_argument("--run-id", required=True)
    imp.add_argument("--response", required=True)

    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    db_path = run_dir / "run.sqlite"
    if not db_path.exists():
        print(f"run.sqlite not found: {db_path}", file=sys.stderr)
        return 2

    if args.command == "prepare":
        result = run_video_understanding(
            db_path, run_dir, args.run_id, limit=args.limit, download=args.download_media
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    store = EvidenceStore(db_path)
    try:
        result = import_analysis_response(args.response, store, args.run_id)
    except Exception as exc:
        print(f"creative response invalid: {exc}", file=sys.stderr)
        return 2
    finally:
        store.close()
    print(json.dumps({"status": "imported", "video_id": result["video_id"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
