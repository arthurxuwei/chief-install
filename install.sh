#!/usr/bin/env bash
set -euo pipefail

CHIEF_INSTALL_BASE_URL="${CHIEF_INSTALL_BASE_URL:-https://raw.githubusercontent.com/arthurxuwei/chief-install/main}"
ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="${ZEROCLAW_RUNTIME_DIR:-$PWD/runtime}"
SKILLS_DEST="$RUNTIME_DIR/workspace/.agents/skills"
BIN_DEST="$RUNTIME_DIR/workspace/.local/bin"

download_file() {
  local path="$1"
  local dest="$2"
  curl -fsSL "$CHIEF_INSTALL_BASE_URL/$path" -o "$dest"
}

install_file() {
  local path="$1"
  local dest="$2"

  if [ -f "$ROOT_DIR/$path" ]; then
    cp "$ROOT_DIR/$path" "$dest"
  else
    download_file "$path" "$dest"
  fi
}

install_skill() {
  local skill_name="$1"
  local dest_dir="$SKILLS_DEST/$skill_name"

  rm -rf "$dest_dir"
  mkdir -p "$dest_dir"

  if [ -d "$ROOT_DIR/skills/$skill_name" ]; then
    cp -R "$ROOT_DIR/skills/$skill_name/." "$dest_dir/"
  else
    install_file "skills/$skill_name/SKILL.md" "$dest_dir/SKILL.md"
  fi
}

mkdir -p "$SKILLS_DEST" "$BIN_DEST"

find "$SKILLS_DEST" -maxdepth 1 -type d -name 'chief-*' -exec rm -rf {} +
if [ -d "$RUNTIME_DIR/workspace/skills" ]; then
  find "$RUNTIME_DIR/workspace/skills" -maxdepth 1 -type d -name 'chief-*' -exec rm -rf {} +
fi

install_skill chief-ledger
install_skill chief-a2a-service-trade

install_file "bin/chief" "$BIN_DEST/chief"
chmod +x "$BIN_DEST/chief"

cat <<EOF
Chief installed successfully.

Runtime: $RUNTIME_DIR
CLI:     $BIN_DEST/chief
Skills:  $SKILLS_DEST/chief-ledger
         $SKILLS_DEST/chief-a2a-service-trade
EOF
