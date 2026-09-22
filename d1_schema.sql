CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    org TEXT NOT NULL,
    level TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    location TEXT NOT NULL,
    prize INTEGER NOT NULL,
    champion TEXT,
    runnerup TEXT,
    mvp TEXT,
    score TEXT,
    champion_roster TEXT,
    runnerup_roster TEXT
);
CREATE TABLE IF NOT EXISTS site_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rate_limits (
    key TEXT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0,
    reset_at INTEGER NOT NULL
);
INSERT OR IGNORE INTO site_settings(setting_key, setting_value) VALUES('last_modified', datetime('now','localtime'));