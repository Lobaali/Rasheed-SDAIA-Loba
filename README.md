# Rasheed — Student Financial-Aid & Scholarship Screening Service

A backend service that automatically screens scholarship applications and
decides one of three outcomes: **auto-accept**, **send to committee
review**, or **reject** — built as the capstone project for SDA-AIE-113
(Software Engineering Practices for AI Systems).

This README explains not just *how to run it*, but *why it's built the
way it is* — every architectural choice, every trade-off, and every
lesson learned while building it.

---

## 1. The concept, in plain terms

A university receives scholarship applications. Each one has four pieces
of information:

- **GPA** (0.0–5.0)
- **Household size** (how many people the applicant's income supports)
- **Monthly family income** (in SAR)
- **Documents complete?** (true/false — did they submit all required paperwork)

The service looks at these four things and returns one of three decisions:

| Decision | Meaning |
|---|---|
| `auto_accept` | Strong applicant, no human needs to look at this one |
| `committee_review` | Borderline, or something needs a second look |
| `reject` | Doesn't meet the bar |

**One rule overrides everything else:** if `documents_complete` is
`false`, the decision is *always* `committee_review` — never an automatic
rejection. A missing document is an administrative problem, not evidence
the applicant is undeserving, so a human has to look at it. This one rule
is the most important business requirement in the whole project, and
it's enforced in a way that's structurally impossible to accidentally
break (explained in section 3).

---

## 2. Run it in under 10 minutes

    git clone <your-repo-url>
    cd Rasheed-SDAIA-Loba
    docker compose up -d --build

Wait ~25 seconds, then check both services are healthy:

    docker compose ps

You should see `rasheed-api` and `duplicate-cache` both showing `(healthy)`.

**Try a valid request:**

    curl -X POST localhost:8000/v1/predict \
      -H "Content-Type: application/json" \
      -d '{"application_id":"APP-1","gpa":3.8,"household_size":4,"monthly_family_income_sar":2500,"documents_complete":true}'

**Try a malformed one (should get rejected with a 4xx, not crash):**

    curl -X POST localhost:8000/v1/predict \
      -H "Content-Type: application/json" \
      -d '{"application_id":"APP-2","gpa":99,"household_size":4,"monthly_family_income_sar":2500,"documents_complete":true}'

Interactive API docs (Swagger UI) are at: **http://localhost:8000/docs**

When you're done:

    docker compose down

---

## 3. The architecture — four layers, and why each one exists

The code under `src/rasheed/` is split into four folders. This isn't
arbitrary organization — each layer has one job, and (critically) is
**forbidden from importing certain other layers**, enforced automatically
by a tool called `import-linter` (see section 8).

    src/rasheed/
    ├── domain/      ← pure business rules. No I/O, no framework, no model.
    ├── service/     ← orchestration. Wires domain + model together.
    ├── adapters/    ← the ONLY place external libraries (sklearn, redis) get touched.
    └── api/         ← the HTTP layer. FastAPI routes, request/response shapes.

### Why split it this way? The core idea: **the model must never see, or be able to override, a hard business rule.**

Here's the concrete example that makes this real. The "missing documents
→ always review" rule lives in `domain/policies.py`:

    def decide(application, score, ...):
        if not application.documents_complete:
            return Decision.COMMITTEE_REVIEW   # checked FIRST, unconditionally
        ...

And `domain/entities.py`'s `to_features()` method — which builds what the
model actually sees — **deliberately never includes `documents_complete`**
in the data sent to the model:

    def to_features(self) -> FeatureVector:
        return FeatureVector(values={
            "gpa_normalised": self.gpa / 5.0,
            "log_income_per_capita": ...,
            "household_size": ...,
            # documents_complete is NOT here, on purpose
        })

This means it's not just a policy written in a comment somewhere — it's
**structurally impossible** for the model to learn a weight for document
completeness and accidentally start using it to justify a rejection,
because the model's `predict_proba()` method literally never receives
that field. See `DECISIONS.md` #1 and #2 for the full reasoning, and
`tests/unit/test_features.py::test_documents_complete_never_enters_the_feature_vector`
for the test that locks this guarantee in place permanently.

### Layer by layer

**`domain/`** — the business rules, in plain Python, with zero
dependencies on anything else in this project or any external library
except `pydantic` (for data validation).

- `entities.py` — the core data shapes: `Application` (what comes in),
  `Decision` (the three possible outcomes, as an `Enum` — not a plain
  string, so a typo like `"aprove"` fails immediately instead of
  silently doing nothing), `RawScore` (the model's raw 0–1 output),
  `FeatureVector` (what the model actually consumes)
- `policies.py` — the `decide()` function: the single place that turns
  a score + application into a final `Decision`. All thresholds
  (`ACCEPT_THRESHOLD_DEFAULT`, `REJECT_THRESHOLD_DEFAULT`,
  `MIN_GPA_FOR_AUTO_ACCEPT_DEFAULT`) are named constants at the top of
  the file — not magic numbers buried in a function signature — so a
  non-engineer (a financial-aid officer, a reviewer) can read them
  without reading code logic.

**`service/`** — orchestration. This is the layer that says "first do
this, then do that."

- `interfaces.py` — defines the `Model` Protocol: anything with a
  `predict_proba(features) -> RawScore` method and a `model_version`
  attribute counts as "a model," whether it's the real sklearn one or a
  fake test double. Neither this layer nor `domain/` ever imports
  sklearn — they only know about this abstract shape.
- `duplicate_checker.py` — same idea, but for the duplicate-submission
  extension (see section 6): a `DuplicateChecker` Protocol, plus a
  `NullDuplicateChecker` that's a real, working "do nothing" stand-in
  used when no real cache is configured.
- `scorer.py` — `ScholarshipScorer`, the actual orchestrator: takes an
  `Application`, calls `to_features()`, feeds it to the model, runs
  `decide()`, checks for duplicates, returns a `ScoringResult`.

**`adapters/`** — the *only* two files in the entire project allowed to
import a specific external library.

- `sklearn_model.py` — the only file that imports `sklearn`. Loads the
  trained model file and wraps it to match the `Model` Protocol.
- `redis_duplicate_checker.py` — the only file that imports `redis`.
  Wraps a real Redis client to match the `DuplicateChecker` Protocol.

**`api/`** — the HTTP boundary. Talks to the outside world.

- `schemas.py` — request/response shapes. `ApplicationRequest` uses
  `extra="forbid"` (unknown fields in a request get rejected, not
  silently ignored) and `strict=True` (a real bug we caught during
  testing: pydantic's default *lenient* mode was silently converting
  the string `"yes"` into `True` for `documents_complete` — `strict=True`
  closes that gap).
- `routes.py` — the three endpoints (`/v1/health`, `/v1/ready`,
  `/v1/predict`), plus `get_scorer()`, the dependency-injection function
  that either returns the real scorer (once the model has loaded) or
  raises a `503` with a `Retry-After` header if it hasn't loaded yet.
- `app.py` — the FastAPI app factory. Runs the model-loading `lifespan`
  function at startup (never at import time — see section 7), sets up
  structured JSON logging, and defines a unified error envelope so every
  error response has the same shape (`error`, `detail`, `trace_id`).

### The rule that's automatically enforced: layers can't skip levels

    domain  cannot import →  service, adapters, api
    service cannot import →  adapters, api
    adapters cannot import → api

This isn't just documentation — it's enforced by `.importlinter`
(config file at the repo root) and checked by the `lint-imports` command,
which runs in CI on every push. If someone (even accidentally) writes
`from rasheed.adapters.sklearn_model import ...` inside `domain/policies.py`,
the build fails immediately with the exact line number of the violation.

---

## 4. The model

A small **LogisticRegression** trained on **synthetic data** — see
`notebooks/train_rasheed_model.ipynb`.

**Why a simple model, and why synthetic data?** The capstone spec is
explicit that a lightweight model is enough — the engineering discipline
*around* the model is what matters, not the model's sophistication. A
LogisticRegression trains in under a second and is trivial to reason
about, which matters when you're also trying to demonstrate behavioural
testing on top of it.

**Why train it in an external notebook instead of a script in the repo?**
Two reasons:

1. It mirrors the real-world "notebook for exploration, clean code for
   production" split that fraud-service's own `batch.py` docstring
   described — the messy, iterative training process shouldn't live
   alongside the clean, tested application code.
2. It keeps the actual deliverable (`models/rasheed_lr_v1.joblib`) small
   and version-controlled without needing scikit-learn's full training
   dependencies bundled into the app's dependency tree.

**Features the model sees** (computed by `Application.to_features()`):

- `gpa_normalised` — GPA divided by 5.0
- `log_income_per_capita` — `log(1 + monthly_income / household_size)`,
  log-transformed so extreme income values don't dominate
- `household_size` — as-is

**Feature NOT included:** `documents_complete` — see section 3.

**Ground truth used to generate the synthetic training labels:** higher
GPA increases eligibility; lower income-per-capita (more financial need)
increases eligibility. The notebook includes a built-in sanity check
that refuses to save the model artefact if this directional relationship
doesn't hold — so a broken model can never even reach the repo.

**To retrain:** open `notebooks/train_rasheed_model.ipynb`, run all
cells, download `rasheed_lr_v1.joblib`, place it at
`models/rasheed_lr_v1.joblib`, replacing the existing one.

---

## 5. The decision logic, step by step

    1. Is documents_complete == false?
       -> YES: COMMITTEE_REVIEW. Stop here. (Nothing else matters.)
       -> NO: continue.

    2. Is score >= 0.75 AND gpa >= 2.0?
       -> YES: AUTO_ACCEPT
       -> NO: continue.

    3. Is score <= 0.35?
       -> YES: REJECT
       -> NO: COMMITTEE_REVIEW (the middle band)

**Why is there a separate GPA floor (step 2) in addition to the score
threshold?** The score already blends GPA and financial need — a very
low-income applicant with a mediocre GPA can score highly on need alone.
The GPA floor is a second, independent check: *no matter how strong the
financial-need signal, don't auto-accept without a minimum academic bar
being cleared.* Full reasoning in `DECISIONS.md` #3.

---

## 6. Extension: duplicate-submission detection

**What it does:** if the same `application_id` is submitted twice, the
second submission can't land on `auto_accept` anymore — it gets
downgraded to `committee_review` and the response includes
`"duplicate_submission": true`. It never auto-*rejects* on this signal
alone — same philosophy as the missing-documents rule: suspicion routes
to a human, it doesn't auto-punish.

**Why `application_id` and not a random token:** in this design,
`application_id` represents the *student*, not a single form-submission
event. A real duplicate happens when: a
student re-applies after an earlier rejection, a browser double-submits
on a slow connection, or someone tweaks their numbers slightly hoping a
second attempt lands differently.

**How it's built:** same Protocol + adapter + null-object pattern as the
model itself — `DuplicateChecker` (Protocol) → `RedisDuplicateChecker`
(real, in `adapters/`) or `NullDuplicateChecker` (default no-op, used
when no cache is configured). This means the feature is fully optional
and the whole service still works correctly with zero Redis dependency
if you don't want it — see `service/duplicate_checker.py`.

**Backed by:** Redis, running as the `duplicate-cache` service in
`docker-compose.yml`, gated on a real health check
(`condition: service_healthy`) so the API doesn't start accepting
duplicate-sensitive traffic before Redis itself is actually reachable.

---

## 7. The API layer, in detail

### Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /v1/health` | Liveness — "is the process running at all" |
| `GET /v1/ready` | Readiness — "has the model finished loading" (returns 503 until it has) |
| `POST /v1/predict` | The actual scoring endpoint |

**Why two separate health endpoints instead of one?** `/health` answers
"is the process alive" (useful for basic liveness probes). `/ready`
answers "can this instance actually handle a real request right now" —
which is `false` for the first second or two while the model file is
still being loaded from disk. Conflating these two means a load balancer
might route real traffic to an instance that isn't ready yet, resulting
in confusing 503s that look like real errors.

### Model loading happens at startup, never at import time

The model is loaded inside FastAPI's `lifespan` context manager in
`api/app.py`, not at the top of any module. This matters because
import-time side effects (like loading a multi-megabyte file from disk)
make testing painful — every test file that merely *imports* the app
module would trigger a real model load, even tests that have nothing to
do with the model. Loading it in `lifespan` means it only happens once,
explicitly, when the actual server process starts.

### Every response has a unified shape

Successful responses (`PredictResponse`) and error responses
(`ErrorEnvelope`) both always carry a `trace_id` — either the one the
caller sent via the `X-Trace-Id` header, or a freshly generated UUID if
they didn't send one. This `trace_id` also appears in the structured
JSON log line for that request (see below), so a specific failed request
a user reports can be traced directly to its corresponding log entry.

### Structured JSON logging, with no personal data

Every log line is valid JSON, for example:

    {"timestamp": "...", "level": "INFO", "message": "scored", "logger": "rasheed", "trace_id": "...", "application_id": "APP-1", "decision": "auto_accept"}

Only `trace_id`, `application_id` (an opaque identifier), and `decision`
ever get logged — never `gpa`, `monthly_family_income_sar`, or anything
else that could be considered sensitive personal/financial data about a
real applicant. This was verified directly: a real request was sent and
its resulting log line was inspected to confirm no application data
leaked into it.

### A 500 error never leaks internal details

If something inside `ScholarshipScorer.score()` throws an unexpected
exception, the client gets back a generic "Internal error while scoring
the application" message and a 500 status — never the actual Python
exception type or message. The real error is logged server-side (with
`logger.exception(...)`, which captures the full traceback) for
debugging, but the client never sees it. Tested directly in
`tests/integration/test_predict_api.py::test_predict_500_hides_internal_details`.

---

## 8. Testing strategy — the three-level pyramid

    tests/
    ├── unit/           <- pure logic, milliseconds, no I/O
    ├── integration/    <- the real FastAPI app via TestClient, ~50ms/test
    └── behavioural/    <- the REAL trained model, marked @pytest.mark.slow

**The placement rule:** test a thing at the *lowest* level that can
catch its failure. Business rules (like the missing-documents rule) get
a unit test on `decide()` directly — no HTTP, no model, no Docker
needed, because none of that is relevant to whether the rule itself is
correct. The same rule *also* gets an integration test through the real
API, because that additionally proves the wiring between the HTTP layer
and the business logic actually works, which the unit test alone can't
prove.

### Unit tests (`tests/unit/`)

Test doubles only — `ConstantModel` (always returns a fixed score,
letting you deterministically hit every decision band),
`InMemoryDuplicateChecker` (a Python `set()`, no real Redis). Covers:
`decide()`'s decision bands and boundaries, `to_features()`'s math and
the guarantee that `documents_complete` never enters it, the duplicate
extension's downgrade-only behaviour, `ScholarshipScorer`'s basic wiring.

### Integration tests (`tests/integration/`)

The real `create_app()` FastAPI app, with the model swapped out via
`app.dependency_overrides[get_scorer]` — so these tests exercise real
HTTP request/response handling, real pydantic validation, real routing,
without needing the actual trained model or a running container. Covers:
the `/v1/predict` contract, a 14-file corpus of malformed payloads (each
must be rejected with a 4xx, never crash the server or return 200), the
500-hides-internal-details guarantee, `/health` and `/ready` behaviour
both before and after the real `lifespan` has run.

### Behavioural tests (`tests/behavioural/`, marked `@pytest.mark.slow`)

Run against the *real* trained model — these are excluded from the fast
per-commit gate (`pytest -m "not slow"`) and only run when explicitly
requested (`pytest -m slow`), since loading the real model takes real
time. Covers:

- **Invariance**: changing `application_id` (an opaque field) must not
  move the score at all
- **Directional**: a higher GPA must never produce a lower eligibility
  score than a lower GPA, all else equal
- **Golden reference**: scores 500 reference applications and compares
  against a versioned CSV (`tests/behavioural/golden_scores_v1.csv`).
  Any difference means either an unintended training/serving skew, or a
  genuine model change that needs review before the golden file is
  regenerated — regeneration is a deliberate, reviewed act
  (`make regen-golden`), never a way to silence a failing test.

### Coverage

`fail_under = 80` in `pyproject.toml`, measured on branch coverage
across `domain/`, `service/`, and `api/`. The thin Redis I/O wrapper
(`adapters/redis_duplicate_checker.py`) is deliberately excluded from
the coverage gate — it has no branching logic of its own, and testing it
meaningfully would require a real Redis instance, which the fast suite
intentionally avoids. The logic it wraps (the downgrade-on-duplicate
rule) *is* tested, via the in-memory fake.

---

## 9. Containerization

**Multi-stage Dockerfile** — two stages, `builder` and `runtime`:

- **`builder`**: has the full compiler toolchain (`build-essential`),
  installs Python dependencies into a virtual environment at `/opt/venv`.
  Nothing from this stage ships in the final image.
- **`runtime`**: starts fresh from `python:3.12-slim`, copies *only*
  `/opt/venv` and the trained model file from the builder stage. No
  compilers, no pip cache, no trace of any layer that isn't strictly
  needed to run the app.

**Final image size: 464 MB** (capstone requirement: ≤ 500 MB). Achieved
by: ordering the Dockerfile so the slow dependency-install layer is
cached separately from the fast-changing source-code layer; dropping
`uvicorn[standard]`'s extras (`uvloop`, `httptools`, `watchfiles`,
`websockets`) since none of them matter inside a container (they're
dev-reload and performance extras); dropping `curl` from the runtime
image entirely (~15MB) and replacing the healthcheck with a one-line
Python `urllib` call instead, since Python is already present and `curl`
isn't otherwise needed.

**Non-root user**: the container runs as `appuser` (uid 10001), not
root — created explicitly and switched to via `USER appuser` before the
`CMD` line. Verified with `docker run --rm rasheed:dev whoami`.

**Clean shutdown**: the `CMD` uses exec-form (a JSON array, not a shell
string), which makes `uvicorn` PID 1 inside the container and lets it
receive `SIGTERM` directly on `docker stop`. Verified directly: the
container stopped in 0.4 seconds (not the default 10-second force-kill
timeout) and its logs showed the full graceful shutdown sequence
(`Shutting down` -> `Waiting for application shutdown` ->
`Application shutdown complete`).

**Healthcheck** targets `/v1/ready`, not `/v1/health` — because
`/health` only confirms the process is alive, not that the model has
actually finished loading and the service can handle real traffic. Both
the Dockerfile's `HEALTHCHECK` *and* `docker-compose.yml`'s
`healthcheck:` block need to agree on this — a compose-level healthcheck
silently overrides whatever's baked into the image, which was a real bug
caught and fixed during this build (both were initially using `curl`,
which no longer existed in the trimmed image).

**`docker-compose.yml`** runs `rasheed-api` alongside `duplicate-cache`
(Redis), with the API's `depends_on` set to wait for Redis's
`service_healthy` condition — the API container won't even attempt to
start until Redis has passed its own healthcheck, not merely "the
container process exists."

---

## 10. CI/CD pipeline

`.github/workflows/ci.yml` runs on every push, with four jobs that only
proceed if the previous one passed:

    lint-and-typecheck -> test -> image-smoke-test -> publish

- **`lint-and-typecheck`**: `ruff check`, `lint-imports` (architecture
  contracts), `mypy`
- **`test`**: `pytest -m "not slow"` — the fast suite, with the 80%
  coverage gate baked into `pyproject.toml` (a coverage failure here
  fails the whole job)
- **`image-smoke-test`**: builds the real Docker image, starts it, waits
  for `/v1/ready`, sends one valid request and one malformed request
  (mirroring exactly the manual smoke test done locally throughout
  development)
- **`publish`**: only runs when the push is on `main` — never on a
  feature branch or a PR. Pushes to GitHub Container Registry, tagged
  with the exact commit SHA — never `latest`, since an untagged/mutable
  `latest` deployment makes "what's actually running in production"
  unanswerable. (Note: the image name has to be lowercased explicitly —
  Docker registries reject uppercase repository names, and GitHub's own
  `${{ github.repository }}` preserves the repo's original casing.)

**Branch protection on `main`**: requires all three non-publish checks
to pass, requires at least one PR approval, disables force-pushes.

---

## 11. Configuration

All settings live in **one place**: `src/rasheed/config.py`'s `Settings`
class (pydantic-settings, prefixed `RASHEED_`). Nothing else in the
codebase reads `os.environ` directly — verified with a repo-wide grep.
Being typed means a misconfigured value (wrong type in an env var) fails
immediately and clearly at startup, not silently or deep inside a
request handler later.

| Setting | Env var | Default |
|---|---|---|
| Model path | `RASHEED_MODEL_PATH` | `models/rasheed_lr_v1.joblib` |
| Accept threshold | `RASHEED_ACCEPT_THRESHOLD` | `0.75` |
| Reject threshold | `RASHEED_REJECT_THRESHOLD` | `0.35` |
| Min GPA for auto-accept | `RASHEED_MIN_GPA_FOR_AUTO_ACCEPT` | `2.0` |
| Log level | `RASHEED_LOG_LEVEL` | `INFO` |

No secrets exist in this project (no API keys, no passwords) — confirmed
by scanning the entire git history for secret-like patterns and for any
accidentally-committed `.env` file. Both scans came back clean.

---

## 12. Local development

    python3 -m venv .venv
    source .venv/bin/activate
    make install          # pip install -e ".[dev,api]"

    make test              # unit + integration, ~1s, 80%+ coverage gate
    make test-slow          # behavioural suite against the real model
    make lint                # ruff + import-linter architecture check
    make typecheck            # mypy

    make image               # docker build
    make up                   # docker compose up -d --build
    make smoke                # curl /v1/health and /v1/ready
    make down                 # docker compose down

    make regen-golden          # regenerate the golden reference file (deliberate act only)

---

## 13. Full project structure

    Rasheed-SDAIA-Loba/
    ├── .github/workflows/ci.yml      # CI/CD pipeline
    ├── .importlinter                 # architecture layer contracts
    ├── .dockerignore
    ├── Dockerfile                    # multi-stage build
    ├── docker-compose.yml            # rasheed-api + duplicate-cache (Redis)
    ├── Makefile                      # unified command interface
    ├── pyproject.toml                # packaging, pytest, coverage, ruff, mypy config
    ├── requirements.lock             # pinned runtime dependencies (prod-only)
    ├── README.md                     # this file
    ├── BENCHMARKS.md                 # real measured numbers
    ├── DECISIONS.md                  # documented engineering decisions
    ├── models/
    │   └── rasheed_lr_v1.joblib      # trained model artefact (committed)
    ├── notebooks/
    │   └── train_rasheed_model.ipynb # training notebook (committed)
    ├── scripts/
    │   ├── generate_golden_file.py
    │   └── startup_time.sh
    ├── payloads/malformed/           # 14-file malformed-request test corpus
    ├── src/rasheed/
    │   ├── config.py                 # Settings (single source of config)
    │   ├── domain/
    │   │   ├── entities.py           # Application, Decision, RawScore, FeatureVector
    │   │   └── policies.py           # decide() -- the core business rule
    │   ├── service/
    │   │   ├── interfaces.py         # Model Protocol
    │   │   ├── duplicate_checker.py  # DuplicateChecker Protocol + NullDuplicateChecker
    │   │   └── scorer.py             # ScholarshipScorer (the orchestrator)
    │   ├── adapters/
    │   │   ├── sklearn_model.py      # real Model implementation
    │   │   └── redis_duplicate_checker.py  # real DuplicateChecker implementation
    │   └── api/
    │       ├── schemas.py            # request/response contracts
    │       ├── routes.py             # /health, /ready, /predict
    │       └── app.py                # FastAPI factory, lifespan, logging
    └── tests/
        ├── conftest.py                # shared fixtures (client_factory, real_model, ...)
        ├── unit/                      # pure logic, test doubles only
        ├── integration/                # real FastAPI app via TestClient
        └── behavioural/                 # real trained model, marked @pytest.mark.slow