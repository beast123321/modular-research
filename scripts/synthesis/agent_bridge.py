"""Build a provider-neutral request for host-agent research synthesis."""
from __future__ import annotations
from typing import Any


def build_synthesis_request(*, run_id: str, patterns: list[dict[str, Any]], observations: list[dict[str, Any]], voc_summary: dict[str, Any], topic: str | None) -> dict[str, Any]:
    return {
        "schema_version":"1.0","run_id":run_id,"topic":topic,
        "task":"Generate evidence-backed insights, testable creative hypotheses, and media briefs from the supplied evidence.",
        "reasoning_rules":[
            "Treat pattern lift as correlation/association evidence, not causal proof.",
            "Do not claim Business Truth; hypotheses remain proposed until real market tests support them.",
            "Every insight, hypothesis, and media brief must cite evidence_refs from the supplied evidence graph.",
            "Prefer cross-creator and cross-source support; explicitly lower confidence when evidence is narrow.",
            "Do not invent metrics, comments, videos, ads, customer claims, or market results.",
        ],
        "evidence":{"patterns":patterns,"observations":observations,"voc_summary":voc_summary},
        "required_output_schema":{
            "schema_version":"1.0","analyzer":{"name":"string","version":"string|null","mode":"reasoning"},
            "insights":[{"id":"string","statement":"string","evidence_refs":["string"],"confidence":"0..1"}],
            "hypotheses":[{"id":"string","statement":"string","objective":"string","hook_type":"creative taxonomy value|null","format":"creative taxonomy value|null","selling_angle":"creative taxonomy value|null","proof_type":"creative taxonomy value|null","evidence_refs":["string"],"confidence":"0..1"}],
            "media_briefs":[{"id":"string","hypothesis_id":"string","objective":"string","target_audience":"string|null","duration_target_sec":"number|null","timeline":[{"start_sec":"number","end_sec":"number","event":"string","instruction":"string"}],"cta":"string|null","evidence_refs":["string"],"confidence":"0..1"}],
        },
    }
