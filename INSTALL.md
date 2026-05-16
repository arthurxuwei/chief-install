# Install Chief CLI

Install the `ontology` CLI and only the OntologyAgent skills this deployment
uses: `ontology-ledger`, `ontology-circle`, and `ontology-a2a-service-trade`.

Run from this repository root:

```bash
ROOT_DIR="$(pwd)"
RUNTIME_DIR="${ZEROCLAW_RUNTIME_DIR:-$ROOT_DIR/runtime}"
SKILLS_DEST="$RUNTIME_DIR/workspace/.agents/skills"
BIN_DEST="$RUNTIME_DIR/config/bin"

mkdir -p "$SKILLS_DEST" "$BIN_DEST"
rm -rf "$SKILLS_DEST"/ontology-*
rm -rf "$RUNTIME_DIR/workspace/skills"/ontology-*

for skill_name in ontology-ledger ontology-circle ontology-a2a-service-trade; do
  cp -R "$ROOT_DIR/skills/$skill_name" "$SKILLS_DEST/$skill_name"
done

cp "$ROOT_DIR/bin/ontology" "$BIN_DEST/ontology"
chmod +x "$BIN_DEST/ontology"
```

This installs:

```text
runtime/config/bin/ontology
runtime/workspace/.agents/skills/ontology-ledger
runtime/workspace/.agents/skills/ontology-circle
runtime/workspace/.agents/skills/ontology-a2a-service-trade
```

`bin/ontology` is the repository source file. `runtime/config/bin/ontology` is
the installed host executable. Mount that same installed file into a ZeroClaw
container as `/usr/local/bin/ontology`.

To install into another runtime directory:

```bash
export ZEROCLAW_RUNTIME_DIR=/path/to/runtime
# then run the install block above
```

## Verify

On the host:

```bash
test -x runtime/config/bin/ontology
runtime/config/bin/ontology ledger health
runtime/config/bin/ontology ledger state
runtime/config/bin/ontology circle health
runtime/config/bin/ontology circle tools
```

For the hosted OntologyAgent deployment, set:

```bash
export ONTOLOGY_LEDGER_URL=https://ledger.curawealth.ai/mcp/
export ONTOLOGY_CIRCLE_MCP_URL=https://circle.curawealth.ai/mcp/
```

The agent runtime should use the MCP URLs above. The `ontology` CLI also accepts
that ledger MCP URL and strips the trailing `/mcp/` internally when it needs to
call ledger REST endpoints such as `/health` or `/ledger/state`.

Ensure the runtime config allows the `ontology` command.

## Agent Rules

- Use `ontology` as the local entrypoint for OntologyAgent ledger and Circle operations.
- Before payment, escrow lock, release, or refund, run `ontology ledger route '<json-intent>'`.
- Continue only with the returned `allowedTools` or command family.
- If routing returns `needs_clarification`, ask the user before proceeding.
- Use `ontology ledger state` as the source of truth for A2A service-trade payment state.
