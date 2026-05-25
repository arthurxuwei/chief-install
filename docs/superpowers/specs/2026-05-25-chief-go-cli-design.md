# Chief Go CLI Migration Design

Date: 2026-05-25

## Goal

Replace the current shell-based `chief` command with a Go implementation while
keeping the existing agent-facing command surface stable.

The migration should make JSON parsing, profile handling, transfer validation,
ledger requests, and install behavior easier to test and maintain. Existing
OpenClaw users should continue to install and run Chief with the same high-level
flow.

## Scope

In scope:

- Implement the `chief` CLI in Go.
- Preserve the current command names, arguments, output shape, and exit-code
  behavior where tests already define it.
- Preserve the existing `install.sh` entrypoint for now.
- Keep `install.sh` thin: workspace discovery, platform asset selection,
  binary installation, skill installation, and post-install `chief claim link`.
- Produce prebuilt binaries for macOS and Linux on `amd64` and `arm64`.
- Keep Windows out of the initial release matrix.
- Update tests and documentation for the Go CLI.

Out of scope:

- Replacing `install.sh` with `chief install`.
- Changing ledger backend APIs.
- Adding Windows installer support.
- Changing Chief skill product behavior beyond what is needed to point at the
  Go CLI.

## CLI Compatibility

The Go CLI must support these commands:

```text
chief version
chief claim link
chief ledger health
chief ledger state
chief ledger route '<json-intent>'
chief ledger wallet get-or-create '<json>'
chief ledger credit AGENT_ID AMOUNT_ATOMIC [reason]
chief ledger transfer '<json>'
chief ledger escrow create '<json>'
chief ledger escrow release ESCROW_ID
chief ledger escrow refund ESCROW_ID
```

The Go implementation should keep the current environment variables:

- `CHIEF_LEDGER_URL`
- `CHIEF_LEDGER_HTTP_URL`
- `CHIEF_LEDGER_FALLBACK_URL`
- `CHIEF_AGENT_PROFILE_PATH`
- `OPENCLAW_WORKSPACE_DIR`

It should also keep these behavior contracts:

- Profile discovery checks `CHIEF_AGENT_PROFILE_PATH`, then
  `OPENCLAW_WORKSPACE_DIR`, then the current workspace paths used by the shell
  CLI.
- `claim link` posts the current OpenClaw profile to `/ledger/claims/link` and
  prints `Agent ID`, `Claim Code`, `Claim Link`, and `Agent Link`.
- `ledger state` reads the profile-scoped account, entries, escrows, and onramp
  sessions domain endpoints, then returns a single state-shaped JSON payload.
- `ledger state` omits `availableAtomic` from the output.
- `ledger transfer` accepts recipient email plus amount, rejects direct
  `fromAgentId` or `toAgentId`, and requires explicit local-user payment
  context.
- Direct transfer only accepts `paymentContext.source` values
  `local_user_request` and `local_user_test`, with boolean
  `userApproved: true` and a non-empty reason.

## Architecture

Recommended source layout:

```text
cmd/chief/main.go
internal/chiefcli/cli.go
internal/chiefcli/config.go
internal/chiefcli/http.go
internal/chiefcli/profile.go
internal/chiefcli/route.go
internal/chiefcli/state.go
internal/chiefcli/transfer.go
internal/chiefcli/output.go
```

Responsibilities:

- `cmd/chief/main.go`: process entrypoint.
- `internal/chiefcli/cli.go`: command dispatch and usage.
- `internal/chiefcli/config.go`: environment and default URL handling.
- `internal/chiefcli/http.go`: ledger GET/POST helpers and fallback behavior.
- `internal/chiefcli/profile.go`: OpenClaw profile path discovery and parsing.
- `internal/chiefcli/route.go`: local payment routing decisions.
- `internal/chiefcli/state.go`: domain endpoint aggregation and state
  sanitization.
- `internal/chiefcli/transfer.go`: amount parsing, recipient validation, and
  anti-fraud payment context validation.
- `internal/chiefcli/output.go`: stable human-readable output formatting.

## Install And Release

Keep `install.sh` as the public installation entrypoint for now. It should stay
small and avoid reimplementing business logic already present in the Go CLI.

Release assets:

```text
chief_darwin_amd64
chief_darwin_arm64
chief_linux_amd64
chief_linux_arm64
```

The installer should map `uname -s` and `uname -m` to one of those assets, place
it at `workspace/.local/bin/chief`, mark it executable, install the two Chief
skills, and run `chief claim link`. Unsupported platforms should fail with a
clear error.

For local development, tests may build a local Go binary and install it without
requiring published release assets.

## Error Handling

The Go CLI should return:

- `0` for successful commands.
- `2` for usage errors, malformed profiles, invalid transfer payloads, missing
  required fields, and unsupported platforms.
- The underlying non-zero error behavior for failed HTTP calls, while preserving
  readable stderr messages.

Validation errors should remain specific enough for agents and tests to act on,
especially around transfer safety.

## Testing

Keep the existing Python behavior tests that execute `bin/chief`. They are the
compatibility contract for the migration.

Add focused Go tests for:

- Profile path discovery and malformed profile handling.
- Amount parsing.
- Payment context validation.
- Route decisions.
- Ledger state aggregation and `availableAtomic` removal.
- Claim-link payload construction and output formatting.

Verification commands:

```bash
go test ./...
python3 -m unittest discover -s tests
```

## Documentation

Update `README.md` and `INSTALL.md` to describe:

- The Go CLI implementation.
- The supported release platforms.
- The retained `install.sh` installation path.
- Verification commands.

The docs should not ask users to install Go for normal use.
