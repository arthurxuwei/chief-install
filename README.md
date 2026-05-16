# chief-install

Install kit for exposing OntologyAgent ledger and Circle capabilities to a
ZeroClaw-style agent runtime.

This repository intentionally contains only the distribution artifacts an agent
needs:

- `bin/ontology`: local CLI entrypoint used by agents
- `skills/ontology-ledger`: ledger and escrow workflow skill
- `skills/ontology-circle`: Circle Agent Wallet workflow skill
- `skills/ontology-a2a-service-trade`: A2A service-trade settlement skill
- `INSTALL.md`: copy-and-mount install steps

See [INSTALL.md](INSTALL.md) for installation.
