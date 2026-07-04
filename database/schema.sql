-- ===========================================================================
-- DogeBox Reward Tracker - SQLite schema (multi-user)
-- Applied automatically on start-up by database/db.py (idempotent).
-- ===========================================================================

-- Monitored wallet addresses, scoped per Telegram user.
-- A user cannot add the same address twice, but two different users may each
-- track the same address.
CREATE TABLE IF NOT EXISTS wallets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT    NOT NULL,
    address    TEXT    NOT NULL,
    label      TEXT,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, address)
);

CREATE INDEX IF NOT EXISTS idx_wallets_user ON wallets (user_id);

-- Shared cache of per-wallet CUMULATIVE reward amounts for each epoch date.
-- Reward data is public and identical for everyone, so this cache is global
-- and benefits every user. Per-epoch (daily) rewards are derived as diffs.
CREATE TABLE IF NOT EXISTS reward_cache (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    epoch_date TEXT    NOT NULL,
    wallet     TEXT    NOT NULL,
    reward     REAL    NOT NULL DEFAULT 0,   -- cumulative amount in CYS
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (epoch_date, wallet)
);

CREATE INDEX IF NOT EXISTS idx_reward_cache_epoch  ON reward_cache (epoch_date);
CREATE INDEX IF NOT EXISTS idx_reward_cache_wallet ON reward_cache (wallet);
