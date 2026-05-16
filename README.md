# chief-install

Install kit for exposing Chief ledger and Circle capabilities to a
ZeroClaw-style agent runtime.

This repository intentionally contains only the distribution artifacts an agent
needs:

- `bin/chief`: local CLI entrypoint used by agents
- `skills/chief-ledger`: ledger and escrow workflow skill
- `skills/chief-circle`: Circle Agent Wallet workflow skill
- `skills/chief-a2a-service-trade`: A2A service-trade settlement skill
- `INSTALL.md`: copy-and-mount install steps

See [INSTALL.md](INSTALL.md) for installation.

Hosted endpoints:

```bash
export CHIEF_LEDGER_URL=https://ledger.curawealth.ai/mcp/
export CHIEF_CIRCLE_MCP_URL=https://circle.curawealth.ai/mcp/
```
