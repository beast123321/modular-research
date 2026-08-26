PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS creative_patterns (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    performance_metric TEXT NOT NULL,
    pattern_field TEXT NOT NULL,
    pattern_value TEXT NOT NULL,
    top_cohort_size INTEGER NOT NULL,
    baseline_size INTEGER NOT NULL,
    top_support INTEGER NOT NULL,
    baseline_support INTEGER NOT NULL,
    top_share REAL NOT NULL,
    baseline_share REAL NOT NULL,
    lift REAL,
    creator_support INTEGER NOT NULL,
    organic_support INTEGER NOT NULL,
    ad_support INTEGER NOT NULL,
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS insights (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    statement TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    analyzer_name TEXT NOT NULL,
    analyzer_version TEXT,
    analyzer_mode TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS creative_hypotheses (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    statement TEXT NOT NULL,
    objective TEXT NOT NULL,
    hook_type TEXT,
    format TEXT,
    selling_angle TEXT,
    proof_type TEXT,
    evidence_refs_json TEXT NOT NULL,
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    status TEXT NOT NULL DEFAULT 'PROPOSED' CHECK(status IN ('PROPOSED','TESTING','SUPPORTED','REJECTED','ARCHIVED')),
    analyzer_name TEXT NOT NULL,
    analyzer_version TEXT,
    analyzer_mode TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS media_briefs (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    hypothesis_id TEXT NOT NULL,
    objective TEXT NOT NULL,
    target_audience TEXT,
    duration_target_sec REAL,
    timeline_json TEXT NOT NULL DEFAULT '[]',
    cta TEXT,
    evidence_refs_json TEXT NOT NULL,
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    analyzer_name TEXT NOT NULL,
    analyzer_version TEXT,
    analyzer_mode TEXT NOT NULL,
    created_at TEXT NOT NULL
);
