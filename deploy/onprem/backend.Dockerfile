# Obserra SAP UAC backend — FastAPI + Uvicorn.
# Build context is the PACKAGE ROOT (so we can also bundle deploy/wheels for offline installs).
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
COPY deploy/wheels /wheels
# Air-gapped: if a full offline wheelhouse is present (deploy/wheels/OFFLINE, created by
# deploy/build-wheelhouse.sh) install everything from it with no network. Otherwise install
# from PyPI and take emergentintegrations from the bundled wheel, so the private package
# index is never needed.
RUN if [ -f /wheels/OFFLINE ]; then \
        pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt emergentintegrations ; \
    else \
        pip install --no-cache-dir -r requirements.txt && \
        pip install --no-cache-dir --find-links=/wheels emergentintegrations ; \
    fi

COPY backend/ .

EXPOSE 8001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
