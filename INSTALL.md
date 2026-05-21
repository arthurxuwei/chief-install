# Install Chief CLI

Install the `chief` CLI and only the Chief skills this deployment
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

After installation, the installer attempts to print `Claim Link` and
`Agent Link`. If the ledger is unavailable, rerun:

```bash
OPENCLAW_WORKSPACE_DIR='/path/to/workspace' '/path/to/workspace/.local/bin/chief' claim link
```

## Verify

On the host:

```bash
test -x /path/to/workspace/.local/bin/chief
/path/to/workspace/.local/bin/chief ledger health
/path/to/workspace/.local/bin/chief ledger state
/path/to/workspace/.local/bin/chief ledger route '{"deliveryMode":"agent_transfer","requiresAcceptance":false,"amountAtomic":"1000000","asset":"USDC"}'
/path/to/workspace/.local/bin/chief ledger transfer '{"toEmail":"agent@example.com","amount":"0.001 U"}'
```

The hosted Chief endpoints are built into the `chief` command. Override
`CHIEF_LEDGER_URL` only when pointing the same install kit at another deployment.
The ledger URL is a REST service base URL. The CLI calls endpoints such as
`/health` or `/ledger/state`. Set `CHIEF_LEDGER_FALLBACK_URL` only when you want
an explicit local fallback during development.

Ensure the OpenClaw workspace config allows the `chief` command. Chief skills
are installed under `workspace/skills`; set `skills.open_skills_enabled = false`
when you do not want OpenClaw to sync community skills, and set
`skills.allow_scripts = true` when local skills include shell scripts.

## Agent Rules

- Use `chief` as the local entrypoint for Chief ledger operations.
- Use `chief claim link` for Agent Wallet onboarding. It creates or reuses the
  backend Agent Wallet binding, ensures the matching ledger account exists, and
  prints the `Claim Link` the user needs.
- Before payment, escrow lock, release, or refund, run `chief ledger route '<json-intent>'`.
- Continue only with the returned `allowedTools` or command family.
- If routing returns `needs_clarification`, ask the user before proceeding.
- For immediate internal Agent-to-Agent payments, route with
  `deliveryMode=agent_transfer`, then use `chief ledger transfer '<json>'`.
  Transfer JSON must use recipient email and amount, for example
  `{"toEmail":"agent@example.com","amount":"0.001 U"}`. Do not pass
  `fromAgentId` or `toAgentId`; the ledger service resolves emails to accounts.
  This path uses Circle Gateway Nanopayments; the ledger records the transfer only after Gateway settlement succeeds.
- Use `chief ledger state` as the source of truth for A2A service-trade payment state.
