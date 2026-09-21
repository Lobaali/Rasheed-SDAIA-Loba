.PHONY: install test lint typecheck image smoke up down regen-golden startup-time

install:
	pip install -e ".[dev,api]"

test:
	pytest -m "not slow" --durations=10

test-slow:
	pytest -m slow -v --no-cov

lint:
	ruff check src/ tests/
	lint-imports

typecheck:
	mypy src/rasheed

image:
	docker build -t rasheed:dev .

image-size:
	docker images rasheed:dev --format "{{.Size}}"

up:
	docker compose up -d --build

down:
	docker compose down

smoke:
	curl -fsS localhost:8000/v1/health
	curl -fsS localhost:8000/v1/ready

startup-time:
	./scripts/startup_time.sh

regen-golden:
	@echo "Regenerating golden_scores_v1.csv - a REVIEWED, deliberate act."
	python scripts/generate_golden_file.py