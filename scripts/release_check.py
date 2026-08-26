#!/usr/bin/env python3
"""Static release audit for a public modular-research checkout."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
REQUIRED = (
    "VERSION",
    "README.md",
    "SKILL.md",
    "requirements.txt",
    "config.example.json",
    "references/endpoints.json",
    "scripts/run_research.py",
    "scripts/live_validation.py",
    "scripts/media/video.py",
)
FORBIDDEN_ROOT_NAMES = {"config.json", ".env", "runs", "raw", "normalized", "media", "reports"}


def audit_repository(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    issues: list[str] = []
    for rel in REQUIRED:
        if not (root / rel).exists():
            issues.append(f"missing_required:{rel}")

    version_path = root / "VERSION"
    if version_path.exists():
        version = version_path.read_text(encoding="utf-8").strip()
        if not SEMVER_RE.fullmatch(version):
            issues.append("invalid_semver:VERSION")

    cfg_path = root / "config.example.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(f"invalid_json:config.example.json:{type(exc).__name__}")
        else:
            if str(cfg.get("api_key") or "").strip():
                issues.append("config.example.json api_key must be empty")

    for name in FORBIDDEN_ROOT_NAMES:
        if (root / name).exists():
            issues.append(f"forbidden_release_path:{name}")
    # Generated caches are intentionally ignored here: importing the checker
    # itself can create __pycache__. Distribution archives are audited
    # separately; this check focuses on dangerous root state and secrets.
    for pattern in ("*.sqlite", "*.sqlite3"):
        for path in root.glob(pattern):
            issues.append(f"forbidden_generated_file:{path.relative_to(root)}")

    gitignore = root / ".gitignore"
    if gitignore.exists():
        text = gitignore.read_text(encoding="utf-8")
        if "config.json" not in text:
            issues.append("gitignore_missing:config.json")
        if re.search(r"(?m)^media/$", text):
            issues.append("gitignore_would_hide:scripts/media")
    return {"ok": not issues, "issues": issues, "root": str(root)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit modular-research public release contents")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    report = audit_repository(args.root)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"RELEASE_CHECK={'PASS' if report['ok'] else 'FAIL'}")
        for issue in report["issues"]:
            print(f"ISSUE={issue}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
