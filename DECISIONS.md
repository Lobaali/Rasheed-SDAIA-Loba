# Engineering Decisions

## 1. `documents_complete` never enters the model's feature vector

`Application.to_features()` deliberately excludes it. Document
completeness is a hard business rule ("never auto-reject on missing
documents"), not a
signal the model should be allowed to learn a weight for and
potentially override. Enforced with a unit test
(`test_documents_complete_never_enters_the_feature_vector`) so a
future refactor can't silently reintroduce it.

## 2. `min_gpa_for_auto_accept` is a separate floor from the score threshold

The eligibility score blends GPA with financial need (income-per-capita) —
a low-income applicant with a mediocre GPA can still score highly on
need alone. `min_gpa_for_auto_accept` is a separate, independent floor:
no matter how strong the financial-need signal, an application can't be
auto-accepted unless GPA itself clears a minimum academic bar. The score
threshold and the GPA floor answer two different questions ("is this
applicant eligible overall?" vs. "does academic standing alone meet the
bar for skipping human review?"), so a single blended number can't
replace both.

## 3. Policy thresholds are named module-level constants, not bare defaults

`ACCEPT_THRESHOLD_DEFAULT`, `REJECT_THRESHOLD_DEFAULT`, and
`MIN_GPA_FOR_AUTO_ACCEPT_DEFAULT` are defined at the top of
`policies.py` rather than left as unnamed literals in the function
signature. These are business decisions, not implementation details —
naming them lets a non-engineer (a financial-aid officer, a reviewer)
scan the top of the file and see every policy number without reading
the function body.

## 4. `strict=True` on the request schema

Found during testing: Pydantic v2's default (lenient) mode coerces
strings like `"yes"` into `bool`, which would have silently let a
malformed `documents_complete` field through as valid. Switched
`ApplicationRequest` to `strict=True` — closes the gap, caught by the
malformed-payload corpus test.

## 5. `redis_duplicate_checker.py` is excluded from the coverage gate

It's a thin I/O wrapper around a real Redis client with no branching
logic of its own — testing it meaningfully would require a real Redis
instance, which the fast per-commit suite intentionally avoids. Per the
course's own guidance ("exclude thin adapter I/O rather than game the
number"), it's listed in `pyproject.toml`'s `[tool.coverage.run] omit`.
The logic it wraps (the downgrade-on-duplicate rule) IS tested, via
`InMemoryDuplicateChecker` test doubles in
`tests/unit/test_duplicate_checker_extension.py`.