# 🐕 DogeBox Reward Tracker

A public, multi-user Telegram bot that tracks **Cysic (CYS)** rewards on the
**OpenForge** network. Every user manages their **own private** wallet list and
gets their own daily/weekly reports and charts.

- 👥 **Multi-user** — each Telegram user has a private wallet list (DM-only)
- 📊 Daily & weekly reward reports
- 📈 Minimalist black-and-white graphs (7 / 14 / 21 / 28 epochs)
- 👛 EVM (`0x…`) and bech32 (`cysic1…`) addresses
- 🗓️ Daily auto-report pushed to each user; survives restarts
- 🛡️ Per-user wallet cap + built-in rate limiting
- 🧾 Structured logging, shared SQLite cache, PM2-ready, Ubuntu 22.04+

---

## Table of contents

1. [How it works](#how-it-works)
2. [Project structure](#project-structure)
3. [Quick start](#quick-start)
4. [Telegram / BotFather setup](#telegram--botfather-setup)
5. [Configuration](#configuration)
6. [Running with PM2](#running-with-pm2)
7. [Commands](#commands)
8. [Publishing to GitHub](#publishing-to-github)
9. [Updating](#updating)
10. [Troubleshooting](#troubleshooting)
11. [How rewards are calculated](#how-rewards-are-calculated)
12. [License](#license)

---

## How it works

The OpenForge dashboard (`dash.openforge.one`) is a client-rendered SPA with no
data in its HTML. The real reward data is served as per-epoch merkle files:

```
https://merkle.openforge.one/<YYYY-MM-DD>.json
```

The bot builds that URL **dynamically from the current date** (never
hard-coded), falls back to earlier dates if today's epoch isn't published yet,
and caches results in SQLite. The reward cache is **shared** across users
(on-chain data is public and identical for everyone), so more users means fewer
redundant downloads. Each user's **wallet list is private**.

## Project structure

```
dogebox-reward-tracker/
├── main.py                     # Entry point
├── requirements.txt
├── ecosystem.config.js         # PM2 process definition
├── .env.example
├── LICENSE                     # MIT
├── README.md
├── bot/
│   ├── telegram_bot.py         # App wiring + rate limiter
│   ├── formatting.py
│   └── commands/
│       ├── common.py           # /start, /help, group notice, errors
│       ├── wallets.py          # /add, /remove, /list  (per-user)
│       ├── reports.py          # /report daily|weekly
│       └── graphs.py           # /graph weekly|weekly2|weekly3|monthly
├── services/
│   ├── reward_lookup.py        # Merkle fetch + date fallback + cache
│   ├── reward_parser.py        # Merkle-leaf + generic parsing
│   ├── report_service.py       # Per-user daily/weekly aggregation
│   └── scheduler.py            # Daily per-user push (restart-safe)
├── database/
│   ├── schema.sql              # wallets(user_id) + shared reward_cache
│   ├── db.py
│   └── repositories.py
├── models/models.py
├── charts/chart_generator.py   # Matplotlib B/W PNG charts
├── utils/                      # config, logging, validators, dates
├── config/                     # (reserved)
└── logs/                       # runtime logs
```

## Quick start

Tested on **Ubuntu 22.04+** with **Python 3.10+** (3.11/3.12 recommended).

```bash
# 1. System packages
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git

# 2. Get the code
git clone <your-repo-url> dogebox-reward-tracker
cd dogebox-reward-tracker

# 3. Virtualenv + dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
nano .env          # set TELEGRAM_BOT_TOKEN

# 5. Run
python3 main.py
```

Message your bot `/start`, then `/add <your-wallet>`.

## Telegram / BotFather setup

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the **token**
   into `.env` as `TELEGRAM_BOT_TOKEN`.
2. Recommended BotFather settings for a public bot:
   - `/setjoingroups` → **Disable** (this bot is DM-only).
   - `/setprivacy` → **Enable**.
   - `/setdescription` and `/setabouttext` → a short blurb.
   - `/setcommands` → paste:
     ```
     add - Monitor a wallet address
     remove - Stop monitoring a wallet
     list - Show your monitored wallets
     report - Daily or weekly reward report
     graph - Reward chart (weekly/weekly2/weekly3/monthly)
     help - How to use the bot
     ```

## Configuration

| Variable               | Required | Default                      | Description                                   |
|------------------------|----------|------------------------------|-----------------------------------------------|
| `TELEGRAM_BOT_TOKEN`   | ✅       | —                            | BotFather token                               |
| `TELEGRAM_CHAT_ID`     | ➖       | *(empty)*                    | Your id, for optional admin alerts only       |
| `DATABASE_PATH`        | ➖       | `database/dogebox.db`        | SQLite file path                              |
| `TIMEZONE`             | ➖       | `Asia/Jakarta`               | IANA timezone for dates & scheduler           |
| `DAILY_REPORT_TIME`    | ➖       | `07:30`                      | Daily push time (HH:MM, in `TIMEZONE`)        |
| `MAX_WALLETS_PER_USER` | ➖       | `20`                         | Per-user wallet cap                           |
| `MERKLE_BASE_URL`      | ➖       | `https://merkle.openforge.one` | Reward data host                            |
| `DASHBOARD_BASE_URL`   | ➖       | `https://dash.openforge.one` | Dashboard (reference only)                    |
| `TOKEN_DECIMALS`       | ➖       | `18`                         | wei → CYS conversion                          |
| `EPOCH_LOOKBACK_DAYS`  | ➖       | `14`                         | Days to search back for a missing epoch       |
| `REQUEST_TIMEOUT`      | ➖       | `20`                         | HTTP timeout (seconds)                        |
| `LOG_LEVEL`            | ➖       | `INFO`                       | DEBUG/INFO/WARNING/ERROR                       |
| `LOG_DIR`              | ➖       | `logs`                       | Log directory                                 |

## Running with PM2

```bash
npm install -g pm2                    # needs Node.js

pm2 start ecosystem.config.js         # uses ./.venv/bin/python3
pm2 save
pm2 startup                           # run the printed command once

pm2 logs    dogebox-reward-tracker
pm2 restart dogebox-reward-tracker
pm2 stop    dogebox-reward-tracker
pm2 delete  dogebox-reward-tracker
```

Bare alternative: `pm2 start main.py --interpreter ./.venv/bin/python3 --name dogebox-reward-tracker`

## Commands

| Command                | Description                                        |
|------------------------|----------------------------------------------------|
| `/start`, `/help`      | Show help                                          |
| `/add <address>`       | Monitor a wallet (validated, de-duplicated)        |
| `/remove <address>`    | Stop monitoring a wallet                           |
| `/list`                | List your monitored wallets                        |
| `/report daily`        | Latest-epoch reward per wallet + total             |
| `/report weekly`       | Last 7 epochs: totals, average, highest, lowest    |
| `/graph weekly`        | Chart of last 7 epochs                             |
| `/graph weekly2`       | Chart of last 14 epochs                            |
| `/graph weekly3`       | Chart of last 21 epochs                            |
| `/graph monthly`       | Chart of last 28 epochs                            |

All commands work in **private chat only**. Each user only ever sees their own
wallets and rewards.

## Publishing to GitHub

The repo is safe to publish — secrets live in `.env`, which is git-ignored.

```bash
cd dogebox-reward-tracker
git init
git add .
git commit -m "Initial commit: DogeBox Reward Tracker"
git branch -M main
git remote add origin https://github.com/<you>/dogebox-reward-tracker.git
git push -u origin main
```

Double-check `.env` is **not** staged: `git status` should never list it.

## Updating

```bash
cd dogebox-reward-tracker
git pull
source .venv/bin/activate
pip install -r requirements.txt
pm2 restart dogebox-reward-tracker
```

The SQLite schema is applied idempotently on every start, so updates are safe.

## Troubleshooting

| Symptom                                   | Fix                                                                     |
|-------------------------------------------|-------------------------------------------------------------------------|
| `Configuration error: TELEGRAM_BOT_TOKEN` | Set the token in `.env`.                                                 |
| Commands ignored in a group               | Expected — the bot is DM-only. Talk to it in a private chat.             |
| `/report` says "No epoch data was found"  | `merkle.openforge.one` unreachable or format changed (see below).       |
| Reward shows `0.00`                        | The wallet earned nothing new that epoch, or first appeared today.      |
| `JobQueue unavailable`                    | `pip install "python-telegram-bot[job-queue]"`.                         |
| Inspect what happened                     | `pm2 logs dogebox-reward-tracker` or `tail -f logs/dogebox-reward-tracker.log`. |

## How rewards are calculated

Each merkle leaf looks like:

```json
{ "address": "0x45af…abb", "cumulativeAmount": "2062634152172845000" }
```

`cumulativeAmount` is in **wei** (÷`10**TOKEN_DECIMALS` → CYS) and is a
**cumulative** running total. A wallet's reward for a given epoch is therefore a
difference between consecutive epochs:

```
reward(epoch) = cumulative(epoch) − cumulative(previous available epoch)
```

The bot fetches one extra (older) epoch to compute this diff, and caches
cumulative values. If OpenForge ever changes the host or field names, adjust
`MERKLE_BASE_URL` / `TOKEN_DECIMALS` in `.env`, or the `*_KEYS` sets in
`services/reward_parser.py`. Set `LOG_LEVEL=DEBUG` to see which parse strategy
matched.

## License

[MIT](LICENSE) — use, modify and share freely.
