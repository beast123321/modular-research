#!/usr/bin/env python3
"""Evidence-gated provider verification promotion.

This module consumes a redacted live-validation report and produces a sanitized
verification manifest. Registry mutation is opt-in and changes verification
metadata only; endpoint contracts and pricing fields are preserved verbatim.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


_ALLOWED_PRICING_BASES = {"provider_default", "endpoint_explicit", "unknown"}
_VERIFICATION_FIELDS = {
    "status",
    "verified_at",
    "verification_basis",
    "validation_calls",
    "normalizer_validation",
}


def _parse_verified_at(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("generated_at is required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("generated_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date().isoformat()


def _validation_calls(report: dict[str, Any]) -> dict[str, int]:
    try:
        attempted = int(report["calls_attempted"])
        succeeded = int(report["calls_succeeded"])
        failed = int(report["calls_failed"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("validation call counts are required integers") from exc
    if min(attempted, succeeded, failed) < 0 or attempted != succeeded + failed:
        raise ValueError("validation call counts are inconsistent")
    return {"attempted": attempted, "succeeded": succeeded, "failed": failed}


def _failure_reason(row: dict[str, Any]) -> str:
    error_class = str(row.get("error_class") or "").strip().lower()
    if error_class:
        return f"{error_class}_error"
    if row.get("status") == "ok" and not isinstance(row.get("normalizer_counts"), dict):
        return "missing_normalizer_validation"
    return "not_successful"


def build_verification_manifest(report: dict, *, platform: str) -> dict:
    """Build a deterministic sanitized verification manifest.

    Only successful result rows with a completed normalizer are promotable. The
    returned object intentionally excludes raw response shapes, request payloads,
    response content, and credentials.
    """
    if not isinstance(report, dict):
        raise ValueError("live-validation report must be an object")
    requested_platform = str(platform).strip().lower()
    report_platform = str(report.get("platform") or "").strip().lower()
    if not requested_platform or report_platform != requested_platform:
        raise ValueError(
            f"report platform mismatch: expected {requested_platform}, got {report_platform}"
        )

    results = report.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError("live-validation report must contain non-empty results")

    pricing_basis = str(report.get("pricing_basis") or "").strip()
    if pricing_basis not in _ALLOWED_PRICING_BASES:
        raise ValueError("live-validation report must carry explicit pricing_basis")

    calls = _validation_calls(report)
    verified_at = _parse_verified_at(report.get("generated_at"))

    promoted: set[str] = set()
    non_promoted_reasons: dict[str, str] = {}
    for raw_row in results:
        if not isinstance(raw_row, dict):
            continue
        capability = str(raw_row.get("capability") or "").strip()
        if not capability:
            continue
        provider_code = raw_row.get("provider_code")
        normalizer_counts = raw_row.get("normalizer_counts")
        is_success = (
            raw_row.get("status") == "ok"
            and provider_code in (None, 200)
            and isinstance(normalizer_counts, dict)
        )
        if is_success:
            promoted.add(capability)
            non_promoted_reasons.pop(capability, None)
        elif capability not in promoted:
            non_promoted_reasons.setdefault(capability, _failure_reason(raw_row))

    return {
        "schema_version": "1.0",
        "platform": requested_platform,
        "verified_at": verified_at,
        "source_status": str(report.get("status") or "UNKNOWN"),
        "validation_calls": calls,
        "pricing_basis": pricing_basis,
        "promoted_capabilities": sorted(promoted),
        "non_promoted_capabilities": [
            {"capability": capability, "reason": non_promoted_reasons[capability]}
            for capability in sorted(non_promoted_reasons)
            if capability not in promoted
        ],
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def apply_registry_promotions(
    report: dict, registry_path: Path, *, platform: str
) -> dict:
    """Apply only evidence-backed verification metadata to the endpoint registry."""
    manifest = build_verification_manifest(report, platform=platform)
    registry_path = Path(registry_path)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    endpoints = registry.get("endpoints")
    if not isinstance(endpoints, list):
        raise ValueError("endpoint registry must contain an endpoints list")

    calls = manifest["validation_calls"]
    for capability in manifest["promoted_capabilities"]:
        matches = [
            row
            for row in endpoints
            if isinstance(row, dict)
            and row.get("provider") == "tikhub"
            and row.get("platform") == manifest["platform"]
            and row.get("capability") == capability
        ]
        if len(matches) != 1:
            raise ValueError(
                f"expected exactly one registry entry for {manifest['platform']}:{capability}"
            )
        entry = matches[0]
        before_contract = {
            key: value for key, value in entry.items() if key not in _VERIFICATION_FIELDS
        }
        entry.update(
            {
                "status": "live_verified",
                "verified_at": manifest["verified_at"],
                "verification_basis": "real_provider_response",
                "validation_calls": dict(calls),
                "normalizer_validation": "PASS",
            }
        )
        after_contract = {
            key: value for key, value in entry.items() if key not in _VERIFICATION_FIELDS
        }
        if after_contract != before_contract:
            raise AssertionError("verification promotion modified endpoint contract metadata")

    _atomic_write_json(registry_path, registry)
    return manifest


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Build/apply sanitized provider verification metadata"
    )
    parser.add_argument("--report", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument(
        "--registry", default=str(root / "references" / "endpoints.json")
    )
    parser.add_argument("--manifest-out")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    if args.apply:
        manifest = apply_registry_promotions(
            report, Path(args.registry), platform=args.platform
        )
    else:
        manifest = build_verification_manifest(report, platform=args.platform)

    if args.manifest_out:
        _atomic_write_json(Path(args.manifest_out), manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
