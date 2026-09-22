"""Regenerates tests/behavioural/golden_scores_v1.csv from the CURRENT
model artefact. Run ONLY as a deliberate, reviewed act - never to
silence a failing golden-file test. See DECISIONS.md.
"""
from __future__ import annotations

import csv
import random
import sys

sys.path.insert(0, "src")

from config import Settings
from rasheed.adapters.sklearn_model import SklearnModel  # noqa: E402
from rasheed.domain.entities import Application  # noqa: E402

OUT_PATH = "tests/behavioural/golden_scores_v1.csv"
N_ROWS = 500
SEED = 7


def main() -> None:
    settings = Settings()
    model = SklearnModel.load(str(settings.model_path))    
    rng = random.Random(SEED)
    rows = []
    for i in range(N_ROWS):
        app = Application(
            application_id=f"APP-{i:05d}",
            gpa=round(rng.uniform(0, 5), 2),
            household_size=rng.randint(1, 7),
            monthly_family_income_sar=round(rng.uniform(500, 15000), 2),
            documents_complete=True,
        )
        score = model.predict_proba(app.to_features()).value
        rows.append([app.application_id, app.gpa, app.household_size,
                     app.monthly_family_income_sar, round(score, 6)])

    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["application_id", "gpa", "household_size",
                          "monthly_family_income_sar", "score"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows using model_version={model.model_version}")


if __name__ == "__main__":
    main()