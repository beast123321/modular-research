PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS media_assets (
    run_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    source_url TEXT,
    local_path TEXT,
    sha256 TEXT,
    byte_size INTEGER,
    duration_sec REAL,
    width INTEGER,
    height INTEGER,
    fps REAL,
    status TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY(run_id, video_id)
);

CREATE TABLE IF NOT EXISTS media_keyframes (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    timestamp_sec REAL NOT NULL,
    local_path TEXT NOT NULL,
    scene_index INTEGER,
    ocr_text TEXT,
    ocr_confidence REAL,
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    start_sec REAL,
    end_sec REAL,
    text TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL,
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS creative_analysis (
    run_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    analyzer_name TEXT NOT NULL,
    analyzer_version TEXT,
    analyzer_mode TEXT NOT NULL,
    hook_type TEXT,
    hook_text TEXT,
    product_visible_at REAL,
    format TEXT,
    selling_angle TEXT,
    proof_type TEXT,
    cta_text TEXT,
    cta_at REAL,
    shot_count INTEGER,
    avg_shot_length REAL,
    visual_style TEXT,
    timeline_json TEXT NOT NULL DEFAULT '[]',
    confidence_json TEXT NOT NULL DEFAULT '{}',
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    PRIMARY KEY(run_id, video_id, analyzer_name)
);
