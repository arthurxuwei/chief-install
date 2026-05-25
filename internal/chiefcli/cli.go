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
