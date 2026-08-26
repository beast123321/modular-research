#!/usr/bin/env python3
"""Local environment capability check for modular-research."""
from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import sys
from typing import Any

MIN_PYTHON = (3, 10)
MODULES = ("numpy", "cv2", "PIL", "pytesseract", "openpyxl")


def collect_environment() -> dict[str, Any]:
    version = tuple(sys.version_info[:3])
    return {
        "python": {
            "version": platform.python_version(),
            "supported": version >= MIN_PYTHON,
            "minimum": ".".join(map(str, MIN_PYTHON)),
        },
        "modules": {name: importlib.util.find_spec(name) is not None for name in MODULES},
        "commands": {"tesseract": shutil.which("tesseract") is not None},
    }


def evaluate_readiness(report: dict[str, Any], mode: str = "core") -> tuple[bool, list[str]]:
    if mode not in {"core", "video", "full"}:
        raise ValueError("mode must be core, video, or full")
    missing: list[str] = []
    if not bool(report.get("python", {}).get("supported")):
        missing.append("python>=3.10")
    required_modules: list[str] = []
    if mode in {"video", "full"}:
        required_modules += ["numpy", "cv2"]
    if mode == "full":
        required_modules += ["PIL", "pytesseract", "openpyxl"]
    modules = report.get("modules", {})
    for name in required_modules:
        if not bool(modules.get(name)):
            missing.append(f"module:{name}")
    if mode == "full" and not bool(report.get("commands", {}).get("tesseract")):
        missing.append("command:tesseract")
    return not missing, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Check modular-research local capabilities")
    parser.add_argument("--mode", choices=["core", "video", "full"], default="core")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    report = collect_environment()
    ready, missing = evaluate_readiness(report, args.mode)
    result = {"mode": args.mode, "ready": ready, "missing": missing, **report}
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"MODE={args.mode}")
        print(f"READY={'YES' if ready else 'NO'}")
        print(f"PYTHON={report['python']['version']}")
        print("MISSING=" + (",".join(missing) if missing else "NONE"))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
