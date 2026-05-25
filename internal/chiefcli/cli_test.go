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
