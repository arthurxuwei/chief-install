package main

import (
	"os"

	"github.com/arthurxuwei/chief-install/internal/chiefcli"
)

func main() {
	os.Exit(chiefcli.Run(os.Args[1:], os.Stdout, os.Stderr, chiefcli.ProcessEnv()))
}
