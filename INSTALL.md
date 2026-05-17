# Install Chief CLI

Install the `chief` CLI and only the Chief skills this deployment
uses: `chief-ledger` and `chief-a2a-service-trade`.

Run from this repository root:

```bash
ROOT_DIR="$(pwd)"
RUNTIME_DIR="${ZEROCLAW_RUNTIME_DIR:-$ROOT_DIR/runtime}"
SKILLS_DEST="$RUNTIME_DIR/workspace/.agents/skills"
BIN_DEST="$RUNTIME_DIR/workspace/.local/bin"

mkdir -p "$SKILLS_DEST" "$BIN_DEST"
find "$SKILLS_DEST" -maxdepth 1 -type d -name 'chief-*' -exec rm -rf {} +
if [ -d "$RUNTIME_DIR/workspace/skills" ]; then
  find "$RUNTIME_DIR/workspace/skills" -maxdepth 1 -type d -name 'chief-*' -exec rm -rf {} +
fi

for skill_name in chief-ledger chief-a2a-service-trade; do
  cp -R "$ROOT_DIR/skills/$skill_name" "$SKILLS_DEST/$skill_name"
done

cp "$ROOT_DIR/bin/chief" "$BIN_DEST/chief"
chmod +x "$BIN_DEST/chief"
```

This installs:

```text
runtime/config/bin/chief
runtime/workspace/.agents/skills/chief-ledger
runtime/workspace/.agents/skills/chief-a2a-service-trade
```

`bin/chief` is the repository source file. `runtime/config/bin/chief` is
the installed host executable. Mount that same installed file into a ZeroClaw
container as `/usr/local/bin/chief`.

To install into another runtime directory:

```bash
export ZEROCLAW_RUNTIME_DIR=/path/to/runtime
# then run the install block above
```

## Verify

On the host:

```bash
test -x runtime/config/bin/chief
runtime/config/bin/chief ledger health
runtime/config/bin/chief ledger state
```

The hosted Chief endpoints are built into the `chief` command. Override
`CHIEF_LEDGER_URL` only when pointing the same install kit at another deployment.
The ledger URL may be either a service base URL or an MCP URL; the CLI strips the
trailing `/mcp/` internally when it needs to call ledger REST endpoints such as
`/health` or `/ledger/state`. Set `CHIEF_LEDGER_FALLBACK_URL` only when you want
an explicit local fallback during development.

Ensure the runtime config allows the `chief` command.

## Agent Rules

- Use `chief` as the local entrypoint for Chief ledger operations.
- Use `chief ledger wallet get-or-create '<json>'` to create or reuse the
  backend Agent Wallet binding and ensure the matching ledger account exists.
- Before payment, escrow lock, release, or refund, run `chief ledger route '<json-intent>'`.
- Continue only with the returned `allowedTools` or command family.
- If routing returns `needs_clarification`, ask the user before proceeding.
- Use `chief ledger state` as the source of truth for A2A service-trade payment state.
