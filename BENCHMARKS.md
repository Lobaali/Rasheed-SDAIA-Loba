# Benchmarks

Real measurements from my own runs on my machine — numbers will vary
on other hardware, and that's expected. What matters is the shape of
the result (which is smaller/faster, and roughly by how much), not
matching any reference numbers exactly.

## Docker

| Metric | Value |
|---|---|
| Multi-stage image size | 464 MB |
| Cold build time (`docker builder prune -af` first) | 1m 49.9s |
| Warm rebuild (one-line code change, cache intact) | 8.5s |
| Time-to-ready (`scripts/startup_time.sh`, cold containers) | 2s |

## Tests

| Metric | Value |
|---|---|
| `pytest -m "not slow"` — pass count / duration | 37 passed / 1.09s |
| `pytest -m slow` — pass count / duration | 3 passed / 0.67s |
| Branch coverage (domain + service + api) | 95.20% |

## Static analysis

| Check | Result |
|---|---|
| `ruff check src/ tests/` | All checks passed |
| `mypy src/rasheed` | Success, 0 issues, 16 source files |
| `lint-imports` (architecture contracts) | 3 kept, 0 broken |