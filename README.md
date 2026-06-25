# ISO 20022 / SWIFT Bridge MCP

mcp-name: io.github.CSOAI-ORG/iso20022-bridge-mcp

Part of the **CSOAI Layer-0 legacy-bridge family** (sibling of `cobol-bridge-mcp`). Bridges the financial-messaging legacy world — ISO 20022 (`pacs`/`pain`/`camt`) and SWIFT MT — to ONE OS / CSOAI, and **governs every payment**.

## Tools
- `parse_iso20022(xml)` — message type + key payment fields (amount, currency, debtor/creditor, agents, EndToEndId).
- `validate_iso20022(xml)` — well-formedness + required-field checks.
- `map_to_modern(xml)` — flat modern JSON for downstream systems.
- `govern_payment(xml)` — AML/sanctions surface, large-value thresholds, frameworks (ISO 20022 · DORA · NIS2 · FATF · PSD2); attestable on the CSOAI ledger.

## Run
```bash
pip install -e .
python server.py        # stdio MCP server
```

The win: legacy payment message → CSOAI governance/attestation → ONE OS, without disruption. Pairs with `dora-compliance-mcp` + `dora-nis2-crosswalk-mcp`.
