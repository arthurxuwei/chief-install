# chief-install

Install kit for exposing Chief ledger capabilities to a ZeroClaw-style agent
runtime. The repository distributes a Go-based `chief` CLI plus the Chief
skills needed by agent workspaces.

This repository intentionally contains only the distribution artifacts an agent
needs:

- `cmd/chief`: Go CLI source for the local `chief` entrypoint used by agents
- `skills/chief-ledger`: ledger, Agent Wallet onboarding, direct Agent transfer, and escrow workflow skill
- `skills/chief-a2a-service-trade`: A2A service-trade settlement skill
- `install.sh`: curl-pipe installer for ZeroClaw runtime files
- `INSTALL.md`: install and verification steps

See [INSTALL.md](INSTALL.md) for installation.

Normal users install prebuilt binaries through `install.sh` and do not need Go
installed. Supported platforms, binary download settings, and developer
verification commands are documented in [INSTALL.md](INSTALL.md).

Hosted service defaults live in `chief`; override them with `CHIEF_*`
environment variables only when using another deployment.
