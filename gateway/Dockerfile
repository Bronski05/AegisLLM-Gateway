# ==========================================
# Etap 1: Budowanie zależności (Builder)
# ==========================================
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ==========================================
# Etap 2: Obraz uruchomieniowy (Runner)
# ==========================================
FROM python:3.11-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc

WORKDIR /app

# Inicjalizacja użytkownika i grupy systemowej
RUN groupadd -g 10001 aegisgroup && \
    useradd -u 10001 -g aegisgroup -M -s /sbin/nologin aegisuser && \
    mkdir /tmp/prometheus_multiproc

COPY --from=builder /opt/venv /opt/venv
COPY . .

# KRYTYCZNA FIX: Pełny chown dla /app oraz /tmp, a następnie bezpieczne maski (750 / 770)
RUN chown -R aegisuser:aegisgroup /app /tmp/prometheus_multiproc && \
    chmod -R 750 /app && \
    chmod -R 770 /tmp/prometheus_multiproc

USER 10001

EXPOSE 8000

ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]