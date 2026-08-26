#!/usr/bin/env python3
"""CLI for Phase 6 synthesis response validation/import."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evidence_store import EvidenceStore
from synthesis.contracts import validate_synthesis_response


def cmd_import(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir); payload = json.loads(Path(args.response).read_text(encoding="utf-8")); validated = validate_synthesis_response(payload); store = EvidenceStore(run_dir / "run.sqlite")
    try: store.replace_semantic_outputs(args.run_id, validated)
    finally: store.close()
    reports = run_dir / "reports"; reports.mkdir(parents=True, exist_ok=True); (reports / "synthesis_response.json").write_text(json.dumps(validated, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status":"imported","insights":len(validated["insights"]),"hypotheses":len(validated["hypotheses"]),"media_briefs":len(validated["media_briefs"])}, ensure_ascii=False)); return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Import evidence-backed synthesis outputs"); sub = parser.add_subparsers(dest="command", required=True); imp = sub.add_parser("import-response"); imp.add_argument("--run-dir", required=True); imp.add_argument("--run-id", required=True); imp.add_argument("--response", required=True); imp.set_defaults(func=cmd_import); args = parser.parse_args(); return int(args.func(args))

if __name__ == "__main__": raise SystemExit(main())
