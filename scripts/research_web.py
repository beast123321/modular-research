#!/usr/bin/env python3
"""Launch the bundled local Research Workbench."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import webbrowser

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.backend.app import create_app


def resolve_runs_root(skill_root: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    social = skill_root / "social-research" / "runs"
    legacy = skill_root / "runs"
    if social.exists():
        return social.resolve()
    if legacy.exists():
        return legacy.resolve()
    return social.resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Open the local modular-research Workbench")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--runs-root")
    parser.add_argument("--no-open", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= int(args.port) <= 65535:
        raise SystemExit("--port must be between 1 and 65535")
    runs_root = resolve_runs_root(ROOT, args.runs_root)
    frontend_dist = ROOT / "web" / "frontend" / "dist"
    if not (frontend_dist / "index.html").is_file():
        print(
            "Research Workbench frontend build is missing. Expected web/frontend/dist/index.html. "
            "Install/build the released Skill before launching the Workbench.",
            file=sys.stderr,
        )
        return 2
    app = create_app(runs_root, frontend_dist=frontend_dist)
    url = f"http://127.0.0.1:{args.port}"
    if not args.no_open:
        webbrowser.open(url)
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
