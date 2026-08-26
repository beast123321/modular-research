PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS video_metrics_derived (
    run_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    engagement_rate REAL,
    like_rate REAL,
    comment_rate REAL,
    share_rate REAL,
    save_rate REAL,
    follower_leverage REAL,
    view_velocity_per_hour REAL,
    like_velocity_per_hour REAL,
    comment_velocity_per_hour REAL,
    views_percentile REAL,
    engagement_percentile REAL,
    share_rate_percentile REAL,
    follower_leverage_percentile REAL,
    creator_overperformance REAL,
    creator_baseline_views REAL,
    creator_baseline_sample INTEGER,
    cohort_json TEXT NOT NULL DEFAULT '{}',
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    computed_at TEXT NOT NULL,
    PRIMARY KEY(run_id, video_id)
);

CREATE TABLE IF NOT EXISTS creator_metrics_derived (
    run_id TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    baseline_views REAL,
    sample_size INTEGER NOT NULL,
    median_engagement_rate REAL,
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    computed_at TEXT NOT NULL,
    PRIMARY KEY(run_id, creator_id)
);

CREATE TABLE IF NOT EXISTS comment_labels (
    run_id TEXT NOT NULL,
    comment_id TEXT NOT NULL,
    labels_json TEXT NOT NULL,
    matched_terms_json TEXT NOT NULL,
    weighted_intensity REAL NOT NULL,
    classifier_version TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    computed_at TEXT NOT NULL,
    PRIMARY KEY(run_id, comment_id)
);

CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    finding_type TEXT NOT NULL CHECK(finding_type = 'OBSERVATION'),
    category TEXT NOT NULL,
    statement TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    support_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
