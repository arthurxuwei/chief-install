# Install Chief CLI

Install the Go-based `chief` CLI and only the Chief skills this deployment
uses: `chief-ledger` and `chief-a2a-service-trade`.

Chief installs into OpenClaw workspaces only.

By default, run the installer from the directory that contains
`runtime-openclaw-*/workspace`:

```bash
curl -fsSL https://raw.githubusercontent.com/arthurxuwei/chief-install/main/install.sh | bash
```

To install one workspace explicitly:

```bash
curl -fsSL https://raw.githubusercontent.com/arthurxuwei/chief-install/main/install.sh \
  | OPENCLAW_WORKSPACE_DIR='/path/to/runtime-openclaw-x/workspace' bash
```

The installer is still the supported installation path. Normal users do not
need Go; `install.sh` downloads the platform binary from GitHub releases by
default using `CHIEF_INSTALL_BIN_BASE_URL`, which defaults to
`https://github.com/arthurxuwei/chief-install/releases/latest/download`.

Supported release platforms:

- `darwin/amd64`
- `darwin/arm64`
- `linux/amd64`
- `linux/arm64`

After installation, the installer attempts to print `Claim Link` and
`Agent Link` by running `chief claim link` for the current OpenClaw profile.
The owner email comes from that profile. If the ledger is unavailable, rerun:

```bash
OPENCLAW_WORKSPACE_DIR='/path/to/workspace' '/path/to/workspace/.local/bin/chief' claim link
```

## Verify

On the host:

```bash
test -x /path/to/workspace/.local/bin/chief
/path/to/workspace/.local/bin/chief version
/path/to/workspace/.local/bin/chief ledger health
/path/to/workspace/.local/bin/chief ledger state
/path/to/workspace/.local/bin/chief ledger route '{"deliveryMode":"agent_transfer","requiresAcceptance":false,"amountAtomic":"1000000","asset":"USDC"}'
/path/to/workspace/.local/bin/chief ledger transfer '{"toEmail":"agent@example.com","amount":"0.001 U","paymentContext":{"source":"local_user_test","userApproved":true,"reason":"Local user asked this agent to run an online transfer test"}}'
```

The hosted Chief service defaults are built into the `chief` command. Override
them only under operator guidance or when pointing this install kit at another
deployment. The install docs intentionally avoid service path details; agents
should use the `chief` commands instead of constructing backend calls.

For developer verification, run:

```bash
./scripts/build-release.sh
go test ./...
```

Ensure the OpenClaw workspace config allows the `chief` command. Chief skills
are installed under `workspace/skills`; set `skills.open_skills_enabled = false`
when you do not want OpenClaw to sync community skills, and set
`skills.allow_scripts = true` when local skills include shell scripts.
