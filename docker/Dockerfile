# ai-home-assistant — multi-arch Docker image
# Built for: linux/amd64, linux/arm64, linux/riscv64
# Build: `docker buildx build --platform linux/amd64,linux/arm64,linux/riscv64 ...`

# Slim Python base — wheel compatibility across all three arches
FROM python:3.11-slim AS base

# System deps that have native components (sqlite-native ones, hashing, http)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libsqlite3-0 \
    libffi8 \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

WORKDIR /app

# Python dependency layer (cached separately from source)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Source layer (changes most often; keep last)
COPY src/ /app/src/
COPY config/default.toml /app/config/default.toml

# Compile translation .mo files (Babel only needed at build time)
RUN pip install --no-cache-dir Babel==2.16.0 \
    && pybabel compile -d /app/src/ai_ha/web/i18n/locales -D ai_ha \
    && pip uninstall -y Babel

# Default data dir (mount a volume here in prod)
RUN mkdir -p /data
VOLUME /data

# Default config: copy default.toml on first run if /data/config.toml absent
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8124

ENV PYTHONUNBUFFERED=1
ENV AI_HA_CONFIG=/data/config.toml
ENV AI_HA_DATA_DIR=/data

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8124/api/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-m", "ai_ha"]

LABEL org.opencontainers.image.source="https://github.com/qiurui144/ai-home-assistant"
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.description="AI Home Assistant — learns your household, augments existing HA Core"
LABEL org.opencontainers.image.vendor="qiurui144"
