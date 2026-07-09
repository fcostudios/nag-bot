FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 nagbot

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN mkdir -p /data /config && chown -R nagbot:nagbot /data /config
USER nagbot

ENV NAGBOT_CONFIG_PATH=/config/nagbot.yaml \
    NAGBOT_DB_PATH=/data/nagbot.db

EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s --start-period=20s \
    CMD curl -fsS http://localhost:8080/healthz || exit 1

CMD ["python", "-m", "nagbot", "serve"]
