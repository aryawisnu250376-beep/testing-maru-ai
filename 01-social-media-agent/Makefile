# Perintah harian. Semua aman dijalankan tanpa API key.
.DEFAULT_GOAL := help
SHELL := /bin/bash

help:  ## tampilkan daftar perintah
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install:  ## pasang dependency
	pip install -r requirements.txt

test:  ## jalankan test suite
	python -m pytest tests -q

lint:  ## cek gaya & bug statis (ruff)
	ruff check src tests

doctor:  ## diagnosa lingkungan: ffmpeg, paket, 9Router, folder, DB
	python -m src.cli doctor

setup:  ## pasang dependency lalu diagnosa
	pip install -r requirements.txt
	python -m src.cli doctor

scan:  ## pindai trend hari ini
	python -m src.cli scan

script:  ## tulis script dari tema teratas
	python -m src.cli script

list:  ## lihat semua episode
	python -m src.cli list

worker:  ## jalankan worker antrean (foreground)
	python -m src.cli worker

jobs:  ## lihat antrean
	python -m src.cli jobs

learn:  ## laporan pola pemenang
	python -m src.cli learn

studio:  ## STUDIO otonom: agent bekerja sendiri, kamu cuma ACC/revisi
	python -m src.dashboard --port 8080

studio-headless:  ## sama, tapi tanpa halaman web (hanya log di terminal)
	python -m src.cli studio

dashboard:  ## alias lama = studio
	python -m src.dashboard --port 8080

agents:  ## lihat status tiap agent dari terminal
	python -m src.cli studio --once --json

mcp:  ## jalankan MCP server (stdio) untuk Hermes
	python -m src.mcp_server

demo:  ## alur penuh sekali jalan (berhenti di gerbang ACC)
	python -m src.cli run

docker:  ## build + jalankan via docker compose
	docker compose up -d --build
	docker compose logs -f agent

clean:  ## bersihkan artefak render (script & DB tetap)
	rm -rf out/*/work
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +

reset:  ## HAPUS semua state (hati-hati)
	rm -rf data/pipeline.db out/*

.PHONY: help install test lint doctor setup scan script list worker jobs learn studio studio-headless dashboard agents mcp demo docker clean reset
