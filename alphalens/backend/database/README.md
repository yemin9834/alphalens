# AlphaLens Database

Aurora PostgreSQL via RDS Data API. Shared library for API and agents.

## Setup

1. Deploy `alphalens/terraform/1_database` and add ARNs to `alphalens/.env`
2. From this directory:

```bash
uv sync
uv run test_data_api.py
uv run run_migrations.py
uv run reset_db.py --with-test-data   # optional demo data
uv run verify_database.py
```

## Usage in Python

```python
from src import Database
from src.schemas import UserCreate

db = Database()
user = db.users.find_by_clerk_id("clerk_123")
```

## Tables

- `users` — risk profile and investment preferences
- `portfolios` / `holdings` — weighted positions
- `discovery_runs` / `candidates` — ecosystem stock pool
- `analysis_jobs` — ranked + recommendation JSON payloads

## Scripts

| Script | Purpose |
|--------|---------|
| `test_data_api.py` | Verify Aurora Data API connection |
| `run_migrations.py` | Create schema |
| `reset_db.py` | Drop and recreate (`--with-test-data`) |
| `verify_database.py` | Health check report |
| `test_db.py` | Quick model smoke test |
