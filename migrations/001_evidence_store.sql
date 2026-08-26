PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS research_runs (
    id TEXT PRIMARY KEY,
    request_json TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS raw_evidence (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    source_type TEXT,
    source_key TEXT,
    fetched_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES research_runs(id)
);

CREATE TABLE IF NOT EXISTS creators (
    creator_id TEXT PRIMARY KEY,
    sec_user_id TEXT,
    unique_id TEXT,
    nickname TEXT,
    bio TEXT,
    region TEXT,
    verified INTEGER,
    followers INTEGER,
    following INTEGER,
    total_likes INTEGER,
    video_count INTEGER,
    last_seen_at TEXT,
    raw_evidence_id TEXT
);

CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    creator_id TEXT,
    caption TEXT,
    create_time TEXT,
    duration_sec REAL,
    region TEXT,
    cover_url TEXT,
    video_url TEXT,
    music_id TEXT,
    music_title TEXT,
    hashtags_json TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    raw_evidence_id TEXT
);

CREATE TABLE IF NOT EXISTS video_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    views INTEGER,
    likes INTEGER,
    comments INTEGER,
    shares INTEGER,
    favorites INTEGER,
    author_followers INTEGER,
    captured_at TEXT NOT NULL,
    raw_evidence_id TEXT
);

CREATE TABLE IF NOT EXISTS discoveries (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    query_text TEXT,
    source_rank INTEGER,
    sort_type TEXT,
    time_window TEXT,
    discovered_at TEXT NOT NULL,
    raw_evidence_id TEXT
);

CREATE TABLE IF NOT EXISTS comments (
    comment_id TEXT PRIMARY KEY,
    video_id TEXT,
    author_id TEXT,
    text TEXT NOT NULL,
    like_count INTEGER,
    reply_count INTEGER,
    language TEXT,
    created_at TEXT,
    raw_evidence_id TEXT
);

CREATE TABLE IF NOT EXISTS ads (
    material_id TEXT PRIMARY KEY,
    ads_id TEXT,
    video_id TEXT,
    ad_title TEXT,
    description TEXT,
    brand_name TEXT,
    advertiser_name TEXT,
    landing_page TEXT,
    industry_key TEXT,
    objective_key TEXT,
    cost_level INTEGER,
    ctr_raw REAL,
    likes INTEGER,
    comments INTEGER,
    shares INTEGER,
    create_time TEXT,
    raw_evidence_id TEXT
);

CREATE TABLE IF NOT EXISTS ad_timeseries (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    material_id TEXT NOT NULL,
    analysis_type TEXT NOT NULL,
    metric TEXT NOT NULL,
    second REAL NOT NULL,
    value REAL,
    is_drop INTEGER NOT NULL DEFAULT 0,
    is_highlight INTEGER NOT NULL DEFAULT 0,
    captured_at TEXT NOT NULL,
    raw_evidence_id TEXT
);

CREATE TABLE IF NOT EXISTS search_insights (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    query_id TEXT NOT NULL,
    keyword TEXT NOT NULL,
    insight_type TEXT,
    region TEXT,
    language TEXT,
    rank INTEGER,
    trend_json TEXT,
    demographics_json TEXT,
    raw_metrics_json TEXT,
    captured_at TEXT NOT NULL,
    raw_evidence_id TEXT
);
