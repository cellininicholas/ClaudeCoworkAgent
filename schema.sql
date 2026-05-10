-- Signal Brain: knowledge-base schema
-- Designed for self-healing: provenance + temporal validity + reliability scores

CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- single-row table
    name TEXT NOT NULL,
    role TEXT NOT NULL,                      -- e.g., "Founder", "Head of Sales"
    company TEXT,
    bio TEXT NOT NULL,                       -- the story they want to tell publicly
    interests TEXT NOT NULL,                 -- comma-separated topic seeds
    voice_notes TEXT,                        -- how they like to write (tone, dos, don'ts)
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,                      -- 'hackernews' | 'reddit' | 'rss' | 'bluesky'
    handle TEXT NOT NULL,                    -- subreddit name, RSS url, bsky query, etc.
    label TEXT NOT NULL,                     -- human-friendly
    enabled INTEGER NOT NULL DEFAULT 1,
    reliability REAL NOT NULL DEFAULT 0.5,   -- 0..1, evolves with feedback
    last_fetch_at TEXT,
    UNIQUE(kind, handle)
);

CREATE TABLE IF NOT EXISTS raw_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    external_id TEXT NOT NULL,               -- HN id, Reddit id, RSS guid, bsky uri
    title TEXT,
    url TEXT,
    body TEXT,
    score INTEGER,                           -- upvotes/likes/etc.
    posted_at TEXT,                          -- ISO from source
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    content_hash TEXT NOT NULL,              -- sha256 of (title|url|body)
    UNIQUE(source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_items_hash ON raw_items(content_hash);
CREATE INDEX IF NOT EXISTS idx_raw_items_fetched ON raw_items(fetched_at);

-- A claim is an atomic statement extracted from a raw item.
-- Has temporal validity for self-healing.
CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_item_id INTEGER NOT NULL REFERENCES raw_items(id),
    text TEXT NOT NULL,                      -- canonical claim sentence
    stance TEXT NOT NULL,                    -- 'positive' | 'negative' | 'neutral'
    confidence REAL NOT NULL DEFAULT 0.7,    -- 0..1
    valid_from TEXT NOT NULL DEFAULT (datetime('now')),
    valid_to TEXT,                           -- NULL = still believed
    superseded_by INTEGER REFERENCES claims(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_claims_valid ON claims(valid_to);

CREATE TABLE IF NOT EXISTS concepts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description TEXT,
    momentum REAL NOT NULL DEFAULT 0,        -- decaying score; computed during audit
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    occurrences INTEGER NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0      -- archived by audit pass when stale
);

CREATE INDEX IF NOT EXISTS idx_concepts_momentum ON concepts(momentum DESC);

CREATE TABLE IF NOT EXISTS claim_concepts (
    claim_id INTEGER NOT NULL REFERENCES claims(id),
    concept_id INTEGER NOT NULL REFERENCES concepts(id),
    PRIMARY KEY (claim_id, concept_id)
);

CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,                      -- 'post' | 'callback' | 'meme' | 'thread'
    headline TEXT NOT NULL,
    body TEXT NOT NULL,
    rationale TEXT NOT NULL,                 -- why this should resonate (cites concepts)
    concept_ids TEXT NOT NULL,               -- JSON array
    source_ids TEXT NOT NULL,                -- JSON array of supporting sources
    callback_to TEXT,                        -- date or concept this calls back to
    feedback TEXT,                           -- 'accepted' | 'rejected' | NULL
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_suggestions_created ON suggestions(created_at DESC);

-- Audit log: every self-healing action gets an entry, so the user can see what the agent did
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,                    -- 'merge_concepts' | 'archive_concept' | 'flag_contradiction' | 'reliability_update' | 'decay'
    detail TEXT NOT NULL,                    -- human-readable summary
    metadata TEXT,                           -- JSON for any structured detail
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);
