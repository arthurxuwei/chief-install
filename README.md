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

Release binaries are built for `darwin/amd64`, `darwin/arm64`,
`linux/amd64`, and `linux/arm64`. Normal users install those prebuilt
binaries through `install.sh` and do not need Go installed.

By default, `install.sh` downloads `chief` from GitHub releases using
`CHIEF_INSTALL_BIN_BASE_URL`. Override that variable only when testing local
assets or installing from another release host.

Hosted service defaults live in `chief`; override them with `CHIEF_*`
environment variables only when using another deployment.

Developer verification:

```bash
./scripts/build-release.sh
go test ./...
python3 -m unittest discover -s tests
```
