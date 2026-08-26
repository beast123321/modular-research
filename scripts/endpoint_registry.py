"""Machine-readable endpoint registry for modular-research."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY_PATH = ROOT / "references" / "endpoints.json"
_REQUIRED = {"provider", "platform", "capability", "method", "path", "free_credit", "status"}


class EndpointRegistry:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else DEFAULT_REGISTRY_PATH
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        entries = payload.get("endpoints")
        if not isinstance(entries, list):
            raise ValueError("endpoint registry must contain endpoints[]")
        providers = payload.get("providers") or {}
        if not isinstance(providers, dict):
            raise ValueError("endpoint registry providers must be an object")
        self._providers: dict[str, dict[str, Any]] = {
            str(name).lower(): dict(config)
            for name, config in providers.items()
            if isinstance(config, dict)
        }
        self._entries: dict[tuple[str, str, str], dict[str, Any]] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("endpoint entry must be an object")
            missing = sorted(_REQUIRED - set(entry))
            if missing:
                raise ValueError(f"endpoint entry missing keys: {missing}")
            key = (
                str(entry["provider"]).lower(),
                str(entry["platform"]).lower(),
                str(entry["capability"]),
            )
            if key in self._entries:
                raise ValueError(f"duplicate endpoint: {key}")
            self._entries[key] = dict(entry)

    def get(self, provider: str, platform: str, capability: str) -> dict[str, Any]:
        key = (provider.lower(), platform.lower(), capability)
        if key not in self._entries:
            available = self.list_capabilities(provider, platform)
            raise KeyError(
                f"未找到端点: provider={provider} platform={platform} need={capability}. "
                f"该平台已有: {available}. 在 references/endpoints.json 中补充即可。"
            )
        return dict(self._entries[key])

    def get_pricing(self, provider: str, platform: str, capability: str) -> dict[str, Any]:
        """Return pricing with provenance instead of pretending estimates are exact."""
        entry = self.get(provider, platform, capability)
        explicit = entry.get("unit_price_usd")
        if explicit not in (None, ""):
            return {
                "unit_price_usd": str(explicit),
                "price_source": "endpoint_explicit",
                "is_endpoint_exact": True,
                "source_ref": entry.get("docs_ref"),
            }

        provider_cfg = self._providers.get(provider.lower(), {})
        default = provider_cfg.get("default_unit_price_usd")
        if default not in (None, ""):
            return {
                "unit_price_usd": str(default),
                "price_source": "provider_default",
                "is_endpoint_exact": False,
                "source_ref": provider_cfg.get("docs_ref"),
            }

        return {
            "unit_price_usd": None,
            "price_source": "unknown",
            "is_endpoint_exact": False,
            "source_ref": None,
        }

    def list_capabilities(self, provider: str, platform: str) -> list[str]:
        p, plat = provider.lower(), platform.lower()
        return sorted(
            capability
            for (prov, platform_name, capability) in self._entries
            if prov == p and platform_name == plat
        )
