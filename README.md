# DB-TG-Explorer

A read-only Telegram bot that provides an interactive explorer UX over a PostgreSQL database. Built for browsing health data from a Railway-hosted Postgres instance, with schema introspection, drill-down views, pagination, trend snapshots, and single-user security.

## Features

- **Home menu** with inline keyboard buttons for all sections
- **Today / Week / Month** summaries across weight, steps, sleep, heart rate
- **Domain views** (Weight, Steps, Sleep, Heart) with pagination, trends, and sparkline graphs
- **Schema introspection** -- `/tables`, `/describe` work on any database
- **Safe query builder** -- guided table browser + restricted raw SQL (SELECT only)
- **Single-user auth** -- only your Telegram user ID can interact
- **Graceful degradation** -- missing tables or DB outages produce friendly messages, not crashes

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot token from [@BotFather](https://t.me/BotFather) |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `TG_ALLOWED_USER_ID` | Yes | Your Telegram numeric user ID |
| `TZ` | No | Display timezone (IANA name). Default: `Atlantic/Reykjavik` |

### How to get your Telegram user ID

Send `/start` to [@userinfobot](https://t.me/userinfobot) on Telegram. It will reply with your numeric user ID.

## Run Locally

### 1. Clone and install

```bash
git clone <repo-url>
cd DB-TG-Explorer
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

### 2. Configure

Copy the example env file and fill in your values:

```bash
cp .env.example .env
# Edit .env with your real values
```

### 3. Start the bot

```bash
python -m bot.main
```

The bot will connect to the database, detect available health tables, and start polling Telegram for updates. You should see log output like:

```
INFO  Starting DB-TG-Explorer bot  (tz=Atlantic/Reykjavik)
INFO  Database pool created (min=2, max=5)
INFO  Domain ready: weight
INFO  Domain unavailable: heart (table not found or columns unresolvable)
INFO  Bot is polling...
```

## Deploy to Railway

### 1. Create a new Railway project

Push this repo to GitHub, then connect it as a Railway service.

### 2. Set environment variables

In the Railway service settings, add:

- `TELEGRAM_BOT_TOKEN`
- `DATABASE_URL` (Railway provides this automatically if you link a Postgres plugin)
- `TG_ALLOWED_USER_ID`
- `TZ` (optional)

### 3. Deploy

Railway will detect the `Procfile` and run `python -m bot.main` as a worker process (no web port needed).

The `Procfile` contains:

```
worker: python -m bot.main
```

Make sure the service type is set to **Worker** (not Web) in Railway settings so it doesn't expect a PORT binding.

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Home menu with all section buttons |
| `/today` | Today's health snapshot |
| `/week` | 7-day summary |
| `/month` | 30-day summary |
| `/weight` | Weight records with trend + graph |
| `/steps` | Step records with averages + graph |
| `/sleep` | Sleep sessions |
| `/heart` | Heart rate data + graph |
| `/tables` | List all database tables |
| `/describe <table>` | Show columns/types for a table |
| `/q` | Advanced query (guided or raw SQL) |
| `/health` | Bot status, DB connectivity, uptime |

## Architecture

```
bot/
  main.py            Entrypoint: creates bot, registers routers, starts polling
  config.py          Environment variable parsing
  db.py              asyncpg connection pool + query helpers
  middleware.py       Auth guard + rate limiter
  queries/
    generic.py       Schema introspection (tables, describe, browse)
    weight.py        Weight queries with auto-detected table/columns
    steps.py         Steps queries
    sleep.py         Sleep queries
    heart.py         Heart rate queries
    summary.py       Cross-domain aggregation for today/week/month
  handlers/
    start.py         /start home menu
    health.py        /health status
    today.py         /today
    period.py        /week, /month + drill-down
    weight.py        /weight + trend + graph
    steps.py         /steps + graph
    sleep.py         /sleep
    heart.py         /heart + graph
    tables.py        /tables, /describe, browse
    query.py         /q guided builder + raw SQL
  ui/
    keyboards.py     Inline keyboard factories
    formatters.py    HTML formatting, sparklines, tables
  utils/
    paging.py        Pagination callback encoding
    security.py      User authorization check
    time.py          Timezone helpers
```

## Schema Auto-Detection

The bot does not hardcode table or column names. Each domain module (weight, steps, sleep, heart) defines a list of candidate table names and candidate column names. At startup, it introspects the database to find which candidates exist and caches the mapping.

If your tables have different names, either:
1. Add your table name to the `TABLE_CANDIDATES` list in the relevant `bot/queries/*.py` module
2. Or use the generic `/tables` and `/describe` commands to explore any schema

## Security Notes

- Only the user matching `TG_ALLOWED_USER_ID` can interact with the bot
- All other users receive a generic denial message
- The bot is strictly read-only -- no INSERT/UPDATE/DELETE/DROP operations exist in the code
- Raw SQL queries are validated (SELECT only, blocked keywords, no semicolons) and executed inside a READ ONLY transaction
- All database queries use parameterized arguments (no string interpolation for values)
- Rate limiting prevents accidental spam loops (30 messages per 60 seconds)
