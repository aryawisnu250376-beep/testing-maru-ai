# Image produksi: ffmpeg sistem (dengan libass) + Python + font brand
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=8080

# ffmpeg sistem dipakai lebih dulu supaya caption burn-in (libass) tersedia
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg fonts-dejavu-core ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# izin tulis untuk data DB + artefak render
RUN mkdir -p data out /app/out && chmod -R 777 data out

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/api/state',timeout=4)"

# Dashboard + worker antrean dalam satu proses
CMD ["python", "-m", "src.dashboard", "--host", "0.0.0.0", "--port", "8080"]
