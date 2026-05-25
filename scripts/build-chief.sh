#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT_DIR/dist/chief}"

mkdir -p "$(dirname "$OUT")"
GOOS="${GOOS:-$(go env GOOS)}" GOARCH="${GOARCH:-$(go env GOARCH)}" \
  go build -trimpath -ldflags="-s -w" -o "$OUT" "$ROOT_DIR/cmd/chief"
