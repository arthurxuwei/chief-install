# Chief Go CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the shell-based `chief` command with a testable Go CLI while preserving the current agent-facing behavior.

**Architecture:** Add a Go module with `cmd/chief` as the entrypoint and focused packages under `internal/chiefcli`. Keep `install.sh` as the public installer, but make it install platform-specific prebuilt Go binaries instead of relying on shell business logic. Python compatibility tests will build and execute the Go CLI, so the behavior contract stays intact without committing a generated binary.

**Tech Stack:** Go standard library, Python `unittest`, POSIX shell for the retained installer.

---

## File Structure

- Create `go.mod`: Go module declaration.
- Create `cmd/chief/main.go`: small executable entrypoint.
- Create `internal/chiefcli/cli.go`: command dispatch, usage, exit code handling.
- Create `internal/chiefcli/config.go`: environment variables and default URLs.
- Create `internal/chiefcli/http.go`: ledger HTTP GET/POST with fallback behavior.
- Create `internal/chiefcli/profile.go`: OpenClaw profile path discovery and JSON parsing.
- Create `internal/chiefcli/route.go`: local payment routing decisions.
- Create `internal/chiefcli/state.go`: profile-scoped ledger state aggregation and `availableAtomic` sanitization.
- Create `internal/chiefcli/transfer.go`: transfer payload conversion, amount parsing, and payment context validation.
- Create `internal/chiefcli/output.go`: stable claim-link and usage output helpers.
- Create `internal/chiefcli/*_test.go`: focused Go tests for core behavior.
- Create `scripts/build-chief.sh`: cross-build helper for local and release builds.
- Modify `tests/test_chief_transfer.py`: build a temporary Go CLI binary and execute that binary in behavior tests.
- Modify `tests/test_install_openclaw.py`: use a local test asset for installer tests.
- Modify `install.sh`: map OS/arch to release asset and install the Go binary.
- Modify `README.md` and `INSTALL.md`: document Go CLI, supported platforms, installer, and verification.
- Delete tracked shell implementation at `bin/chief`; keep generated binaries out of git.
- Modify `.gitignore`: ignore generated `bin/chief`, `dist/`, and temporary build artifacts.

## Task 1: Bootstrap Go Module And CLI Skeleton

**Files:**
- Create: `go.mod`
- Create: `cmd/chief/main.go`
- Create: `internal/chiefcli/cli.go`
- Create: `internal/chiefcli/config.go`
- Create: `internal/chiefcli/cli_test.go`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing CLI skeleton tests**

Create `internal/chiefcli/cli_test.go`:

```go
package chiefcli

import (
	"bytes"
	"testing"
)

func TestVersionCommandsPrintVersion(t *testing.T) {
	for _, args := range [][]string{{"version"}, {"--version"}} {
		var stdout bytes.Buffer
		var stderr bytes.Buffer
		exitCode := Run(args, &stdout, &stderr, EnvMap{})
		if exitCode != 0 {
			t.Fatalf("Run(%v) exit code = %d stderr=%q", args, exitCode, stderr.String())
		}
		if stdout.String() != "chief 2026.05.25.2\n" {
			t.Fatalf("stdout = %q", stdout.String())
		}
		if stderr.String() != "" {
			t.Fatalf("stderr = %q", stderr.String())
		}
	}
}

func TestUnknownCommandPrintsUsageAndReturnsTwo(t *testing.T) {
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	exitCode := Run([]string{"bogus"}, &stdout, &stderr, EnvMap{})
	if exitCode != 2 {
		t.Fatalf("exit code = %d", exitCode)
	}
	if !bytes.Contains(stdout.Bytes(), []byte("Chief CLI for ZeroClaw")) {
		t.Fatalf("usage missing from stdout: %q", stdout.String())
	}
}
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
go test ./...
```

Expected: FAIL because `go.mod`, `Run`, and `EnvMap` do not exist yet.

- [ ] **Step 3: Add the Go module and minimal CLI**

Create `go.mod`:

```go
module github.com/arthurxuwei/chief-install

go 1.22
```

Create `cmd/chief/main.go`:

```go
package main

import (
	"os"

	"github.com/arthurxuwei/chief-install/internal/chiefcli"
)

func main() {
	os.Exit(chiefcli.Run(os.Args[1:], os.Stdout, os.Stderr, chiefcli.ProcessEnv()))
}
```

Create `internal/chiefcli/config.go`:

```go
package chiefcli

import "os"

const CLIVersion = "2026.05.25.2"

type EnvMap map[string]string

func ProcessEnv() EnvMap {
	env := EnvMap{}
	for _, key := range []string{
		"CHIEF_LEDGER_URL",
		"CHIEF_LEDGER_HTTP_URL",
		"CHIEF_LEDGER_FALLBACK_URL",
		"CHIEF_AGENT_PROFILE_PATH",
		"OPENCLAW_WORKSPACE_DIR",
		"PWD",
	} {
		if value, ok := os.LookupEnv(key); ok {
			env[key] = value
		}
	}
	if _, ok := env["PWD"]; !ok {
		if wd, err := os.Getwd(); err == nil {
			env["PWD"] = wd
		}
	}
	return env
}

type Config struct {
	LedgerURL       string
	LedgerFallback  string
	AgentProfile    string
	WorkspaceDir    string
	WorkingDir      string
}

func ConfigFromEnv(env EnvMap) Config {
	ledgerURL := env["CHIEF_LEDGER_HTTP_URL"]
	if ledgerURL == "" {
		ledgerURL = env["CHIEF_LEDGER_URL"]
	}
	if ledgerURL == "" {
		ledgerURL = "https://ledger.curawealth.ai"
	}
	return Config{
		LedgerURL:      ledgerURL,
		LedgerFallback: env["CHIEF_LEDGER_FALLBACK_URL"],
		AgentProfile:   env["CHIEF_AGENT_PROFILE_PATH"],
		WorkspaceDir:   env["OPENCLAW_WORKSPACE_DIR"],
		WorkingDir:     env["PWD"],
	}
}
```

Create `internal/chiefcli/cli.go`:

```go
package chiefcli

import (
	"fmt"
	"io"
)

const usageText = `Chief CLI for ZeroClaw

Usage:
  chief version
  chief ledger health
  chief ledger state
  chief ledger route '<json-intent>'
  chief ledger wallet get-or-create '<json>'
  chief ledger credit AGENT_ID AMOUNT_ATOMIC [reason]
  chief ledger transfer '{"toEmail":"agent@example.com","amount":"0.001 U"}'
  chief ledger escrow create '<json>'
  chief ledger escrow release ESCROW_ID
  chief ledger escrow refund ESCROW_ID
  chief claim link

Environment:
  CHIEF_LEDGER_URL             default hosted ledger REST service base URL
  CHIEF_LEDGER_HTTP_URL        optional explicit service base URL for CLI REST calls
  CHIEF_LEDGER_FALLBACK_URL    optional fallback service base URL
`

func Run(args []string, stdout io.Writer, stderr io.Writer, env EnvMap) int {
	if len(args) == 0 || args[0] == "help" || args[0] == "-h" || args[0] == "--help" {
		fmt.Fprint(stdout, usageText)
		return 0
	}
	if args[0] == "version" || args[0] == "--version" {
		fmt.Fprintf(stdout, "chief %s\n", CLIVersion)
		return 0
	}
	fmt.Fprint(stdout, usageText)
	return 2
}
```

Modify `.gitignore`:

```gitignore
.DS_Store
bin/chief
dist/
tmp/
```

- [ ] **Step 4: Run skeleton tests**

Run:

```bash
go test ./...
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add go.mod cmd/chief/main.go internal/chiefcli/cli.go internal/chiefcli/config.go internal/chiefcli/cli_test.go .gitignore
git commit -m "feat: bootstrap chief go cli"
```

## Task 2: Implement Profile, Output, And Claim Link

**Files:**
- Create: `internal/chiefcli/profile.go`
- Create: `internal/chiefcli/output.go`
- Create: `internal/chiefcli/http.go`
- Create: `internal/chiefcli/profile_test.go`
- Create: `internal/chiefcli/claim_test.go`
- Modify: `internal/chiefcli/cli.go`

- [ ] **Step 1: Write failing profile and claim tests**

Create `internal/chiefcli/profile_test.go`:

```go
package chiefcli

import (
	"os"
	"path/filepath"
	"testing"
)

func TestProfilePathPreference(t *testing.T) {
	cfg := Config{AgentProfile: "/explicit/profile.json", WorkspaceDir: "/workspace", WorkingDir: "/cwd"}
	got := ProfilePath(cfg)
	if got != "/explicit/profile.json" {
		t.Fatalf("ProfilePath = %q", got)
	}
}

func TestLoadProfileRejectsMalformedJSON(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "profile.json")
	if err := os.WriteFile(path, []byte(`{"agent_id":`), 0o644); err != nil {
		t.Fatal(err)
	}
	_, err := LoadProfile(path)
	if err == nil || !contains(err.Error(), "malformed JSON") {
		t.Fatalf("err = %v", err)
	}
}

func TestClaimPayloadUsesProfileFields(t *testing.T) {
	profile := Profile{
		Email:     "Owner@Example.COM",
		AgentID:   "agent_sender",
		AgentName: `Sender "Slash" \ Agent`,
		Bio:       `Builds "quoted" paths`,
	}
	payload, err := ClaimPayload(profile)
	if err != nil {
		t.Fatal(err)
	}
	if payload.AgentID != "agent_sender" || payload.AgentName != `Sender "Slash" \ Agent` {
		t.Fatalf("payload = %#v", payload)
	}
	if payload.Email != "owner@example.com" {
		t.Fatalf("email = %q", payload.Email)
	}
	if payload.AgentDescription != `Builds "quoted" paths` {
		t.Fatalf("description = %q", payload.AgentDescription)
	}
}
```

Create `internal/chiefcli/claim_test.go`:

```go
package chiefcli

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestClaimLinkPostsProfileAndPrintsLinks(t *testing.T) {
	dir := t.TempDir()
	profilePath := filepath.Join(dir, "profile.json")
	err := os.WriteFile(profilePath, []byte(`{"email":"sender@example.com","agent_id":"agent_sender","agent_name":"Sender"}`), 0o644)
	if err != nil {
		t.Fatal(err)
	}

	var posted ClaimRequest
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/ledger/claims/link" {
			t.Fatalf("path = %s", r.URL.Path)
		}
		if err := json.NewDecoder(r.Body).Decode(&posted); err != nil {
			t.Fatal(err)
		}
		_ = json.NewEncoder(w).Encode(map[string]string{
			"agentId": "agent_sender",
			"claimCode": "clm_testclaim",
			"claimUrl": "https://ledger.example.test/dashboard?claimCode=clm_testclaim&agentId=agent_sender",
			"agentUrl": "https://ledger.example.test/dashboard?agentId=agent_sender",
		})
	}))
	defer server.Close()

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	exitCode := Run([]string{"claim", "link"}, &stdout, &stderr, EnvMap{
		"CHIEF_LEDGER_HTTP_URL": server.URL,
		"CHIEF_AGENT_PROFILE_PATH": profilePath,
	})
	if exitCode != 0 {
		t.Fatalf("exit=%d stderr=%s", exitCode, stderr.String())
	}
	if posted.AgentID != "agent_sender" || posted.Email != "sender@example.com" {
		t.Fatalf("posted = %#v", posted)
	}
	for _, want := range []string{
		"Agent ID:   agent_sender",
		"Claim Code: clm_testclaim",
		"Claim Link: https://ledger.example.test/dashboard?claimCode=clm_testclaim&agentId=agent_sender",
		"Agent Link: https://ledger.example.test/dashboard?agentId=agent_sender",
	} {
		if !contains(stdout.String(), want) {
			t.Fatalf("stdout missing %q: %s", want, stdout.String())
		}
	}
}
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
go test ./...
```

Expected: FAIL because profile, HTTP, and claim helpers do not exist.

- [ ] **Step 3: Implement profile, HTTP, and claim link**

Create `internal/chiefcli/profile.go` with `ProfilePath`, `LoadProfile`, `ClaimPayload`, and structs:

```go
package chiefcli

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

type Profile struct {
	Email     string `json:"email"`
	AgentID   string `json:"agent_id"`
	AgentID2  string `json:"agentId"`
	AgentName string `json:"agent_name"`
	AgentName2 string `json:"agentName"`
	Bio       string `json:"bio"`
	Description string `json:"agentDescription"`
}

type ClaimRequest struct {
	AgentID          string `json:"agentId"`
	AgentName        string `json:"agentName"`
	Email            string `json:"email"`
	AgentDescription string `json:"agentDescription"`
}

func ProfilePath(cfg Config) string {
	if cfg.AgentProfile != "" {
		return cfg.AgentProfile
	}
	if cfg.WorkspaceDir != "" {
		return filepath.Join(cfg.WorkspaceDir, ".eigenflux", "servers", "eigenflux", "profile.json")
	}
	if cfg.WorkingDir == "" {
		cfg.WorkingDir = "."
	}
	candidate := filepath.Join(cfg.WorkingDir, ".eigenflux", "servers", "eigenflux", "profile.json")
	if _, err := os.Stat(candidate); err == nil {
		return candidate
	}
	return filepath.Join(cfg.WorkingDir, "workspace", ".eigenflux", "servers", "eigenflux", "profile.json")
}

func LoadProfile(path string) (Profile, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Profile{}, fmt.Errorf("OpenClaw profile not found at %s", path)
	}
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(data, &raw); err != nil {
		return Profile{}, fmt.Errorf("OpenClaw profile at %s is malformed JSON: %s", path, err.Error())
	}
	var profile Profile
	if err := json.Unmarshal(data, &profile); err != nil {
		return Profile{}, fmt.Errorf("OpenClaw profile at %s is malformed: expected JSON object", path)
	}
	return profile, nil
}

func (p Profile) normalizedAgentID() string {
	if strings.TrimSpace(p.AgentID) != "" {
		return strings.TrimSpace(p.AgentID)
	}
	return strings.TrimSpace(p.AgentID2)
}

func (p Profile) normalizedAgentName() string {
	if strings.TrimSpace(p.AgentName) != "" {
		return strings.TrimSpace(p.AgentName)
	}
	if strings.TrimSpace(p.AgentName2) != "" {
		return strings.TrimSpace(p.AgentName2)
	}
	return p.normalizedAgentID()
}

func (p Profile) normalizedDescription() string {
	if strings.TrimSpace(p.Bio) != "" {
		return strings.TrimSpace(p.Bio)
	}
	return strings.TrimSpace(p.Description)
}

func ClaimPayload(profile Profile) (ClaimRequest, error) {
	agentID := profile.normalizedAgentID()
	email := strings.ToLower(strings.TrimSpace(profile.Email))
	if agentID == "" {
		return ClaimRequest{}, fmt.Errorf("current OpenClaw profile is missing agent_id")
	}
	if email == "" {
		return ClaimRequest{}, fmt.Errorf("current OpenClaw profile is missing email")
	}
	return ClaimRequest{
		AgentID: agentID,
		AgentName: profile.normalizedAgentName(),
		Email: email,
		AgentDescription: profile.normalizedDescription(),
	}, nil
}

func contains(haystack string, needle string) bool {
	return strings.Contains(haystack, needle)
}
```

Create `internal/chiefcli/http.go`:

```go
package chiefcli

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

func getJSON(cfg Config, path string, out any) error {
	return doJSON("GET", cfg.LedgerURL, cfg.LedgerFallback, path, nil, out)
}

func postJSON(cfg Config, path string, body any, out any) error {
	payload, err := json.Marshal(body)
	if err != nil {
		return err
	}
	return doJSON("POST", cfg.LedgerURL, cfg.LedgerFallback, path, payload, out)
}

func doJSON(method string, primary string, fallback string, path string, body []byte, out any) error {
	err := doJSONOnce(method, primary, path, body, out)
	if err == nil || fallback == "" {
		return err
	}
	return doJSONOnce(method, fallback, path, body, out)
}

func doJSONOnce(method string, base string, path string, body []byte, out any) error {
	url := strings.TrimRight(base, "/") + path
	var reader io.Reader
	if body != nil {
		reader = bytes.NewReader(body)
	}
	req, err := http.NewRequest(method, url, reader)
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "application/json, text/event-stream")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("ledger request failed: HTTP %d %s", resp.StatusCode, string(data))
	}
	if out == nil {
		return nil
	}
	return json.Unmarshal(data, out)
}
```

Create `internal/chiefcli/output.go`:

```go
package chiefcli

import (
	"fmt"
	"io"
)

type ClaimResponse struct {
	AgentID   string `json:"agentId"`
	ClaimCode string `json:"claimCode"`
	ClaimURL  string `json:"claimUrl"`
	AgentURL  string `json:"agentUrl"`
}

func printClaimResponse(w io.Writer, response ClaimResponse) {
	fmt.Fprintf(w, "Agent ID:   %s\n", response.AgentID)
	fmt.Fprintf(w, "Claim Code: %s\n", response.ClaimCode)
	fmt.Fprintf(w, "Claim Link: %s\n", response.ClaimURL)
	fmt.Fprintf(w, "Agent Link: %s\n", response.AgentURL)
}
```

Modify `internal/chiefcli/cli.go` to dispatch `claim link`:

```go
if args[0] == "claim" {
	if len(args) == 2 && args[1] == "link" {
		cfg := ConfigFromEnv(env)
		profile, err := LoadProfile(ProfilePath(cfg))
		if err != nil {
			fmt.Fprintln(stderr, err.Error())
			return 2
		}
		body, err := ClaimPayload(profile)
		if err != nil {
			fmt.Fprintln(stderr, err.Error())
			return 2
		}
		var response ClaimResponse
		if err := postJSON(cfg, "/ledger/claims/link", body, &response); err != nil {
			fmt.Fprintln(stderr, err.Error())
			return 1
		}
		printClaimResponse(stdout, response)
		return 0
	}
	fmt.Fprint(stdout, usageText)
	return 2
}
```

- [ ] **Step 4: Run Go tests**

Run:

```bash
go test ./...
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/chiefcli/profile.go internal/chiefcli/output.go internal/chiefcli/http.go internal/chiefcli/profile_test.go internal/chiefcli/claim_test.go internal/chiefcli/cli.go
git commit -m "feat: implement chief claim link in go"
```

## Task 3: Implement Route, State, Wallet, Credit, And Escrow Commands

**Files:**
- Create: `internal/chiefcli/route.go`
- Create: `internal/chiefcli/state.go`
- Create: `internal/chiefcli/route_test.go`
- Create: `internal/chiefcli/state_test.go`
- Modify: `internal/chiefcli/cli.go`

- [ ] **Step 1: Write failing route and state tests**

Create `internal/chiefcli/route_test.go` with tests asserting exact JSON contains for `funding`, `agent_transfer`, `withdrawal`, `immediate_api`, async escrow, and ambiguous intents:

```go
package chiefcli

import (
	"encoding/json"
	"testing"
)

func TestRouteAgentTransferAllowsTransferTool(t *testing.T) {
	response := RoutePaymentIntent(`{"deliveryMode":"agent_transfer"}`)
	var payload map[string]any
	if err := json.Unmarshal([]byte(response), &payload); err != nil {
		t.Fatal(err)
	}
	if payload["method"] != "gateway_nanopayment" || payload["needsClarification"] != false {
		t.Fatalf("payload = %#v", payload)
	}
}
```

Create `internal/chiefcli/state_test.go` with an `httptest.Server` that returns account, entries, escrows, and onramp sessions; assert output JSON has those arrays and does not contain `availableAtomic`.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
go test ./...
```

Expected: FAIL because route and state helpers do not exist.

- [ ] **Step 3: Implement route and state helpers**

Create `internal/chiefcli/route.go` with hard-coded route JSON matching the shell CLI:

```go
package chiefcli

import "strings"

func RoutePaymentIntent(intent string) string {
	switch {
	case strings.Contains(intent, `"deliveryMode":"funding"`):
		return `{"method":"onramp","needsClarification":false,"allowedTools":["agent_wallet_create_onramp_session"],"reason":"Funding must create a hosted onramp session; ledger balance is credited only after provider-confirmed settlement."}` + "\n"
	case strings.Contains(intent, `"deliveryMode":"agent_transfer"`):
		return `{"method":"gateway_nanopayment","needsClarification":false,"allowedTools":["agent_wallet_transfer"],"reason":"Immediate internal Agent-to-Agent payments use Circle Gateway Nanopayments; the ledger records the transfer only after Gateway settlement succeeds."}` + "\n"
	case strings.Contains(intent, `"deliveryMode":"withdrawal"`):
		return `{"method":"needs_clarification","needsClarification":true,"allowedTools":[],"reason":"This install kit only exposes ledger wallet, escrow, and settlement operations. Ask the operator before handling withdrawals."}` + "\n"
	case strings.Contains(intent, `"deliveryMode":"immediate_api"`):
		return `{"method":"needs_clarification","needsClarification":true,"allowedTools":[],"reason":"This install kit only exposes ledger wallet, escrow, and settlement operations. Ask the operator before immediate paid API calls."}` + "\n"
	case strings.Contains(intent, `"deliveryMode":"async_task"`) || strings.Contains(intent, `"requiresAcceptance":true`):
		return `{"method":"ledger_escrow","needsClarification":false,"allowedTools":["agent_wallet_create_escrow","agent_wallet_release_escrow","agent_wallet_refund_escrow"],"reason":"Matched asynchronous task payments require ledger escrow so funds can be locked, released, or refunded."}` + "\n"
	default:
		return `{"method":"needs_clarification","needsClarification":true,"allowedTools":[],"reason":"The payment intent is ambiguous. Clarify whether this is funding or asynchronous task escrow before proceeding."}` + "\n"
	}
}
```

Create `internal/chiefcli/state.go` with structs for `account`, `entries`, `escrows`, and `onrampSessions`; fetch profile-scoped endpoints with URL-escaped agent id; marshal a state-shaped map; remove `availableAtomic` from account before output.

Modify `internal/chiefcli/cli.go` to handle:

```text
ledger health
ledger state
ledger route
ledger wallet get-or-create
ledger credit
ledger escrow create/release/refund
```

Use `getJSON` for health/state and `postJSON` for mutating endpoints. For `health`, print the raw response body by adding `getRaw(cfg, "/health")` if the health endpoint is not always JSON.

- [ ] **Step 4: Run Go tests**

Run:

```bash
go test ./...
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/chiefcli/route.go internal/chiefcli/state.go internal/chiefcli/route_test.go internal/chiefcli/state_test.go internal/chiefcli/cli.go
git commit -m "feat: implement chief ledger reads in go"
```

## Task 4: Implement Transfer Validation And Posting

**Files:**
- Create: `internal/chiefcli/transfer.go`
- Create: `internal/chiefcli/transfer_test.go`
- Modify: `internal/chiefcli/cli.go`

- [ ] **Step 1: Write failing transfer tests**

Create `internal/chiefcli/transfer_test.go` covering:

- `"0.001 U"` converts to `"1000"`.
- `"1.5 USDC"` converts to `"1500000"`.
- missing `paymentContext` fails with `transfer requires paymentContext`.
- `private_dm_request` fails with `paymentContext.source must be local_user_request or local_user_test`.
- string `"true"` approval fails.
- blank reason fails.
- `fromAgentId` and `toAgentId` fail.
- sender and receiver same email fails.
- valid payload posts `fromEmail`, `toEmail`, `amountAtomic`, and `reason`.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
go test ./...
```

Expected: FAIL because transfer helpers do not exist.

- [ ] **Step 3: Implement transfer validation**

Create `internal/chiefcli/transfer.go` with:

```go
package chiefcli

import (
	"encoding/json"
	"fmt"
	"math/big"
	"strings"
)

type TransferRequest struct {
	ToEmail        string          `json:"toEmail"`
	Email          string          `json:"email"`
	Amount         string          `json:"amount"`
	AmountAtomic   string          `json:"amountAtomic"`
	FromAgentID    string          `json:"fromAgentId"`
	ToAgentID      string          `json:"toAgentId"`
	PaymentContext json.RawMessage `json:"paymentContext"`
}

type PaymentContext struct {
	Source       string `json:"source"`
	UserApproved bool   `json:"userApproved"`
	Reason       string `json:"reason"`
}

type TransferPost struct {
	FromEmail    string `json:"fromEmail"`
	ToEmail      string `json:"toEmail"`
	AmountAtomic string `json:"amountAtomic"`
	Reason       string `json:"reason"`
}

func BuildTransferPost(requestJSON string, profile Profile) (TransferPost, error) {
	var request TransferRequest
	if err := json.Unmarshal([]byte(requestJSON), &request); err != nil {
		return TransferPost{}, err
	}
	if request.FromAgentID != "" || request.ToAgentID != "" {
		return TransferPost{}, fmt.Errorf("fromAgentId/toAgentId are internal; use toEmail with amount or amountAtomic")
	}
	if len(request.PaymentContext) == 0 || string(request.PaymentContext) == "null" {
		return TransferPost{}, fmt.Errorf("transfer requires paymentContext")
	}
	var context PaymentContext
	if err := json.Unmarshal(request.PaymentContext, &context); err != nil {
		return TransferPost{}, fmt.Errorf("transfer requires paymentContext")
	}
	if context.Source != "local_user_request" && context.Source != "local_user_test" {
		return TransferPost{}, fmt.Errorf("paymentContext.source must be local_user_request or local_user_test")
	}
	if !context.UserApproved {
		return TransferPost{}, fmt.Errorf("paymentContext.userApproved must be true")
	}
	reason := strings.TrimSpace(context.Reason)
	if reason == "" {
		return TransferPost{}, fmt.Errorf("paymentContext.reason is required")
	}
	toEmail := strings.ToLower(strings.TrimSpace(firstNonEmpty(request.ToEmail, request.Email)))
	if toEmail == "" {
		return TransferPost{}, fmt.Errorf("transfer requires toEmail")
	}
	amountAtomic, err := ParseAmountAtomic(firstNonEmpty(request.AmountAtomic, request.Amount))
	if err != nil {
		return TransferPost{}, err
	}
	fromEmail := strings.ToLower(strings.TrimSpace(profile.Email))
	if fromEmail == "" {
		return TransferPost{}, fmt.Errorf("current OpenClaw profile is missing email")
	}
	if fromEmail == toEmail {
		return TransferPost{}, fmt.Errorf("sender and receiver must be different emails")
	}
	return TransferPost{FromEmail: fromEmail, ToEmail: toEmail, AmountAtomic: amountAtomic, Reason: reason}, nil
}

func ParseAmountAtomic(value string) (string, error) {
	text := strings.TrimSpace(value)
	if text == "" {
		return "", fmt.Errorf("transfer requires amount or amountAtomic")
	}
	text = strings.TrimSuffix(strings.TrimSuffix(strings.TrimSpace(strings.ToUpper(text)), "USDC"), "U")
	text = strings.TrimSpace(text)
	rat, ok := new(big.Rat).SetString(text)
	if !ok {
		return "", fmt.Errorf("amount must be an integer atomic value or decimal USDC like 0.001 U")
	}
	if !strings.Contains(text, ".") {
		if rat.Sign() <= 0 {
			return "", fmt.Errorf("amount must be positive")
		}
		return rat.Num().String(), nil
	}
	rat.Mul(rat, big.NewRat(1000000, 1))
	if !rat.IsInt() {
		return "", fmt.Errorf("amount is smaller than one atomic USDC unit")
	}
	if rat.Sign() <= 0 {
		return "", fmt.Errorf("amount must be positive")
	}
	return rat.Num().String(), nil
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}
```

Modify `internal/chiefcli/cli.go` so `ledger transfer` routes internally, validates allowed tools, builds the post body from the current profile, and posts to `/ledger/transfers`.

- [ ] **Step 4: Run Go tests**

Run:

```bash
go test ./...
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add internal/chiefcli/transfer.go internal/chiefcli/transfer_test.go internal/chiefcli/cli.go
git commit -m "feat: implement chief transfer in go"
```

## Task 5: Move Python Compatibility Tests To The Go Binary

**Files:**
- Create: `scripts/build-chief.sh`
- Modify: `tests/test_chief_transfer.py`
- Modify: `tests/test_install_openclaw.py`
- Delete: `bin/chief`

- [ ] **Step 1: Add build helper**

Create `scripts/build-chief.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT_DIR/dist/chief}"

mkdir -p "$(dirname "$OUT")"
GOOS="${GOOS:-$(go env GOOS)}" GOARCH="${GOARCH:-$(go env GOARCH)}" \
  go build -trimpath -ldflags="-s -w" -o "$OUT" "$ROOT_DIR/cmd/chief"
```

Make it executable:

```bash
chmod +x scripts/build-chief.sh
```

- [ ] **Step 2: Update Python tests to build and run Go CLI**

In `tests/test_chief_transfer.py`, replace:

```python
CHIEF = ROOT / "bin" / "chief"
```

with:

```python
BUILD_DIR = ROOT / "dist" / "test"
CHIEF = BUILD_DIR / "chief"


def setUpModule():
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(ROOT / "scripts" / "build-chief.sh"), str(CHIEF)],
        cwd=ROOT,
        check=True,
    )
```

Apply the same pattern in `tests/test_install_openclaw.py`.

Delete tracked `bin/chief`:

```bash
git rm bin/chief
```

- [ ] **Step 3: Run compatibility tests**

Run:

```bash
python3 -m unittest discover -s tests
```

Expected: tests fail only where installer still expects a raw shell `bin/chief`; transfer and claim behavior tests should execute the Go binary.

- [ ] **Step 4: Commit the test migration**

```bash
git add scripts/build-chief.sh tests/test_chief_transfer.py tests/test_install_openclaw.py
git add -u bin/chief
git commit -m "test: run chief compatibility tests against go binary"
```

## Task 6: Update Installer For Prebuilt Go Assets

**Files:**
- Modify: `install.sh`
- Modify: `tests/test_install_openclaw.py`

- [ ] **Step 1: Write failing installer tests for platform asset selection**

Add tests in `tests/test_install_openclaw.py` that:

- set `CHIEF_INSTALL_BIN_DIR` to a local directory containing `chief_darwin_arm64` or current-platform asset.
- run `install.sh`.
- assert `.local/bin/chief` exists and is executable.
- assert the copied binary can run `version`.

- [ ] **Step 2: Run installer tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_install_openclaw -v
```

Expected: FAIL because `install.sh` does not select Go release assets yet.

- [ ] **Step 3: Modify `install.sh`**

Add functions:

```bash
platform_asset_name() {
  local os arch
  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  arch="$(uname -m)"
  case "$os" in
    darwin) os="darwin" ;;
    linux) os="linux" ;;
    *) echo "Unsupported platform: $os" >&2; return 2 ;;
  esac
  case "$arch" in
    x86_64|amd64) arch="amd64" ;;
    arm64|aarch64) arch="arm64" ;;
    *) echo "Unsupported architecture: $arch" >&2; return 2 ;;
  esac
  printf 'chief_%s_%s\n' "$os" "$arch"
}

install_chief_binary() {
  local dest="$1"
  local asset
  asset="$(platform_asset_name)" || return $?
  if [[ -n "${CHIEF_INSTALL_BIN_DIR:-}" && -f "$CHIEF_INSTALL_BIN_DIR/$asset" ]]; then
    cp "$CHIEF_INSTALL_BIN_DIR/$asset" "$dest"
  elif [[ -f "$ROOT_DIR/dist/$asset" ]]; then
    cp "$ROOT_DIR/dist/$asset" "$dest"
  else
    download_file "dist/$asset" "$dest"
  fi
  chmod +x "$dest"
}
```

Replace the existing `install_file "bin/chief" "$bin_dest/chief"` call with:

```bash
install_chief_binary "$bin_dest/chief"
```

- [ ] **Step 4: Run installer tests**

Run:

```bash
python3 -m unittest tests.test_install_openclaw -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add install.sh tests/test_install_openclaw.py
git commit -m "feat: install prebuilt chief go binaries"
```

## Task 7: Add Cross-Build Release Targets And Documentation

**Files:**
- Modify: `scripts/build-chief.sh`
- Create: `scripts/build-release.sh`
- Modify: `README.md`
- Modify: `INSTALL.md`

- [ ] **Step 1: Add release build script**

Create `scripts/build-release.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT_DIR/dist"

for target in darwin/amd64 darwin/arm64 linux/amd64 linux/arm64; do
  os="${target%/*}"
  arch="${target#*/}"
  out="$ROOT_DIR/dist/chief_${os}_${arch}"
  echo "building $out"
  GOOS="$os" GOARCH="$arch" "$ROOT_DIR/scripts/build-chief.sh" "$out"
done
```

Make it executable:

```bash
chmod +x scripts/build-release.sh
```

- [ ] **Step 2: Update docs**

Update `README.md` to say the repository distributes a Go-based `chief` CLI, Chief skills, and installer.

Update `INSTALL.md` to document:

```bash
curl -fsSL https://raw.githubusercontent.com/arthurxuwei/chief-install/main/install.sh | bash
```

and the supported release platforms:

```text
darwin/amd64
darwin/arm64
linux/amd64
linux/arm64
```

Add developer verification:

```bash
./scripts/build-release.sh
go test ./...
python3 -m unittest discover -s tests
```

- [ ] **Step 3: Run build and tests**

Run:

```bash
./scripts/build-release.sh
go test ./...
python3 -m unittest discover -s tests
```

Expected: all commands PASS and `dist/` contains four executable release assets.

- [ ] **Step 4: Commit**

```bash
git add scripts/build-release.sh scripts/build-chief.sh README.md INSTALL.md
git commit -m "docs: document chief go binary releases"
```

## Task 8: Final Verification And Cleanup

**Files:**
- Inspect all changed files.

- [ ] **Step 1: Run final verification**

Run:

```bash
go test ./...
python3 -m unittest discover -s tests
git status --short
```

Expected:

- `go test ./...` passes.
- Python unittest discovery passes.
- `git status --short` shows no untracked generated files except ignored `dist/`.

- [ ] **Step 2: Confirm generated binaries are ignored**

Run:

```bash
git status --ignored --short dist bin/chief
```

Expected: generated binaries appear as ignored files, not staged files.

- [ ] **Step 3: Commit any final fixes**

If verification required small test or doc corrections, commit them:

```bash
git add <changed-source-or-doc-files>
git commit -m "chore: finalize chief go cli migration"
```

Do not commit generated `dist/*` or `bin/chief`.

## Plan Self-Review

- Spec coverage: The plan covers Go CLI implementation, command compatibility, profile discovery, claim link, state aggregation, transfer safety, installer retention, four-platform build assets, docs, and tests.
- Placeholder scan: No task uses placeholder markers or open-ended implementation instructions as the only guidance.
- Type consistency: The plan consistently uses `chiefcli.Run`, `EnvMap`, `Config`, `Profile`, `ClaimRequest`, `ClaimResponse`, `TransferRequest`, `TransferPost`, and `PaymentContext`.
- Scope check: The plan keeps Windows and `chief install` out of scope, matching the approved design.
