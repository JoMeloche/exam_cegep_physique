# Exam generator web app: UI + API + LaTeX in one container.
# Build:  docker build -t examgen .
# Run:    docker run -p 8765:8765 -v ~/exam_app:/data examgen

ARG REGISTRY=docker.io/library
FROM ${REGISTRY}/node:22-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM ${REGISTRY}/python:3.12-slim
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    EXAM_APP_HOME=/data
RUN apt-get update && apt-get install -y --no-install-recommends \
      texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-lang-french \
      texlive-science texlive-pictures texlive-fonts-recommended lmodern \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/ /app/
COPY --from=ui /ui/dist/ /app/examgen/static/
RUN pip install --no-cache-dir .
# A starter library (Jo's imported SN3 bank) is copied into /data on first start if it is empty.
COPY seed/ /app/seed/
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
VOLUME /data
EXPOSE 8765
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "examgen.api:app", "--host", "0.0.0.0", "--port", "8765"]
