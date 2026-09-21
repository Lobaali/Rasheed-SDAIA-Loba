# ---------- Stage 1: builder ----------
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y \
        --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) Dependency layer: changes rarely => cached across every code edit
COPY requirements.lock .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --no-compile \
       -r requirements.lock

# 2) Source layer: changes every commit, cheap to rebuild
COPY pyproject.toml README.md ./
COPY src/ src/
RUN /opt/venv/bin/pip install --no-cache-dir --no-deps --no-compile . \
    && find /opt/venv -type d \( -name "tests" -o -name "test" -o -name "__pycache__" \) \
       -exec rm -rf {} + \
    && find /opt/venv -name "*.pyc" -delete \
    && rm -rf /opt/venv/lib/python3.12/site-packages/pip \
              /opt/venv/lib/python3.12/site-packages/pip-* \
              /opt/venv/bin/pip*


# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser

COPY --from=builder /opt/venv /opt/venv
# 3) Model layer: baked into the image (pattern "a" - atomic,
# reproducible, one image = one model version). The training
# notebook/process is NOT part of this image at all - only the
# finished .joblib artefact ever gets COPY'd in.
COPY models/rasheed_lr_v1.joblib models/rasheed_lr_v1.joblib

ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s \
    --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/v1/ready').status==200 else 1)"
CMD ["uvicorn", "rasheed.api.app:create_app", \
     "--factory", "--host", "0.0.0.0", "--port", "8000"]