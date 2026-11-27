# Exam generator web app: interface + API + LaTeX in one container.
# Built from the repository root (see ../docker-compose.yml):  docker compose up -d
ARG REGISTRY=docker.io/library

FROM ${REGISTRY}/node:22-slim AS ui
WORKDIR /ui
COPY app/frontend/package.json app/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY app/frontend/ ./
RUN npm run build

FROM ${REGISTRY}/python:3.12-slim
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    EXAM_APP_HOME=/data EXAMGEN_AUTH=1 EXAMGEN_SEED=/app/seed FORWARDED_ALLOW_IPS=127.0.0.1
RUN apt-get update && apt-get install -y --no-install-recommends \
      texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-lang-french \
      texlive-science texlive-pictures texlive-fonts-recommended lmodern \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY app/backend/ /app/
COPY --from=ui /ui/dist/ /app/examgen/static/
RUN pip install --no-cache-dir .
# Starter library: the question bank of this repository, copied into /data on first start.
COPY questions/ /app/seed/questions/
COPY figures/ /app/seed/figures/
COPY exams/ /app/seed/exams/
COPY config.yaml /app/seed/config.yaml
COPY app/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && useradd --system --home-dir /data --shell /usr/sbin/nologin examgen
VOLUME /data
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8765/api/health')"
ENTRYPOINT ["docker-entrypoint.sh"]
# One worker on purpose: login rate limits and the first-run setup code live in this process.
CMD ["uvicorn", "examgen.api:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "1", \
     "--proxy-headers", "--no-server-header"]
