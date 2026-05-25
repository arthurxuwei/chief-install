#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT_DIR/dist"

for target in darwin/amd64 darwin/arm64 linux/amd64 linux/arm64; do
  os="${target%/*}"
  arch="${target#*/}"
  out="$ROOT_DIR/dist/chief_${os}_${arch}"
  echo "building $out"
  GOOS="$os" GOARCH="$arch" "$ROOT_DIR/scripts/build-chief.sh" "$out"
done
