# Install Chief CLI

Install the `chief` CLI and only the Chief skills this deployment
uses: `chief-ledger` and `chief-a2a-service-trade`.

Install with:

```bash
curl -fsSL https://raw.githubusercontent.com/arthurxuwei/chief-install/main/install.sh | bash
```

This installs:

```text
runtime/workspace/.local/bin/chief
runtime/workspace/.agents/skills/chief-ledger
runtime/workspace/.agents/skills/chief-a2a-service-trade
```

`bin/chief` is the repository source file. `runtime/workspace/.local/bin/chief`
is the installed host executable. Add `runtime/workspace/.local/bin` to the
ZeroClaw runtime `PATH`, or mount that same installed file into a ZeroClaw
container as `/usr/local/bin/chief`.

To install into another runtime directory:

```bash
export ZEROCLAW_RUNTIME_DIR=/path/to/runtime
curl -fsSL https://raw.githubusercontent.com/arthurxuwei/chief-install/main/install.sh | bash
```

## Verify

On the host:

```bash
test -x runtime/workspace/.local/bin/chief
runtime/workspace/.local/bin/chief ledger health
runtime/workspace/.local/bin/chief ledger state
runtime/workspace/.local/bin/chief ledger route '{"deliveryMode":"agent_transfer","requiresAcceptance":false,"amountAtomic":"1000000","asset":"USDC"}'
runtime/workspace/.local/bin/chief ledger transfer '{"toEmail":"agent@example.com","amount":"0.001 U"}'
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
- For immediate internal Agent-to-Agent payments, route with
  `deliveryMode=agent_transfer`, then use `chief ledger transfer '<json>'`.
  Transfer JSON must use recipient email and amount, for example
  `{"toEmail":"agent@example.com","amount":"0.001 U"}`. Do not pass
  `fromAgentId` or `toAgentId`; the ledger service resolves emails to accounts.
  This path must complete a real Circle USDC transfer before ledger available
  balances are updated.
- Use `chief ledger state` as the source of truth for A2A service-trade payment state.
