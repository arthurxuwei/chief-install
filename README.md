# chief-install

Install kit for exposing Chief ledger capabilities to a ZeroClaw-style agent
runtime.

This repository intentionally contains only the distribution artifacts an agent
needs:

- `bin/chief`: local CLI entrypoint used by agents
- `skills/chief-ledger`: ledger, Agent Wallet onboarding, and escrow workflow skill
- `skills/chief-a2a-service-trade`: A2A service-trade settlement skill
- `install.sh`: curl-pipe installer for ZeroClaw runtime files
- `INSTALL.md`: install and verification steps

See [INSTALL.md](INSTALL.md) for installation.

Hosted endpoint defaults live in `bin/chief`; override them with `CHIEF_*`
environment variables only when using another deployment.
