#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
docker compose up -d --build
printf '\nAltium Financiero disponible en http://localhost:8501\n'
