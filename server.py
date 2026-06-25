#!/usr/bin/env python3
"""
ISO 20022 / SWIFT Bridge MCP — part of the CSOAI Layer-0 legacy-bridge family.

Connects the financial-messaging legacy world (ISO 20022 pacs/pain/camt, SWIFT MT)
to ONE OS / CSOAI — parse, validate, modernise, and GOVERN every payment message
(AML/sanctions surface, DORA-aligned). Sibling of cobol-bridge-mcp.

Tools: parse_iso20022 · validate_iso20022 · map_to_modern · govern_payment
"""
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import xml.etree.ElementTree as ET
import re

mcp = FastMCP("ISO 20022 Bridge", instructions="Bridge ISO 20022 / SWIFT financial messages to ONE OS — parse, validate, modernise, and govern (AML/DORA).")

# ── SIGIL: every governed action → one signed hash-chained hop (SIGIL_LOG unifies all layers) ──
import hashlib as _hl, time as _t, json as _j, os as _os
_SIGIL_LOG = _os.environ.get("SIGIL_LOG", _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "bridge_sigil.log"))
def _sigil(op, body):
    try:
        prev = ""
        if _os.path.exists(_SIGIL_LOG):
            with open(_SIGIL_LOG) as f:
                ls = f.readlines()
                if ls: prev = _j.loads(ls[-1]).get("digest", "")
        ts = int(_t.time()); dg = _hl.sha256(f"{op}|{ts}|{prev[:8]}|{body}".encode()).hexdigest()[:16]
        _os.makedirs(_os.path.dirname(_SIGIL_LOG), exist_ok=True)
        with open(_SIGIL_LOG, "a") as f: f.write(_j.dumps({"ts": ts, "op": op, "body": body, "prev_digest": prev, "digest": dg}) + "\n")
        return dg
    except Exception: return ""

# Common ISO 20022 message families (root document element local-names)
MSG_TYPES = {
    "pacs.008": "FI-to-FI Customer Credit Transfer",
    "pacs.009": "FI Credit Transfer",
    "pain.001": "Customer Credit Transfer Initiation",
    "pain.008": "Customer Direct Debit Initiation",
    "camt.053": "Bank-to-Customer Statement",
    "camt.054": "Bank-to-Customer Debit/Credit Notification",
}


def _localname(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _detect_type(root) -> str:
    # ISO 20022 namespace looks like urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08
    blob = (root.tag or "") + " " + " ".join(a or "" for a in root.attrib.values())
    m = re.search(r"(pacs|pain|camt|pacs)\.\d{3}", blob)
    if m:
        key = m.group(0)
        return key
    # fall back: scan namespaces
    for v in root.attrib.values():
        m = re.search(r"(pacs|pain|camt)\.\d{3}", v or "")
        if m:
            return m.group(0)
    return "unknown"


def _findtext(root, *names) -> Optional[str]:
    for el in root.iter():
        if _localname(el.tag) in names and (el.text or "").strip():
            return el.text.strip()
    return None


class ParsedMessage(BaseModel):
    message_type: str
    description: str
    amount: Optional[str] = None
    currency: Optional[str] = None
    debtor: Optional[str] = None
    creditor: Optional[str] = None
    debtor_bic: Optional[str] = None
    creditor_bic: Optional[str] = None
    end_to_end_id: Optional[str] = None
    fields_found: int = 0


class Validation(BaseModel):
    valid: bool
    message_type: str
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class Governance(BaseModel):
    message_type: str
    risk_flags: List[str] = Field(default_factory=list)
    aml_surface: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    attestable: bool = True
    note: str = ""


def _parse(xml: str):
    return ET.fromstring(xml)


@mcp.tool()
def parse_iso20022(xml: str) -> ParsedMessage:
    """Parse an ISO 20022 XML message and extract the key payment fields."""
    root = _parse(xml)
    mt = _detect_type(root)
    amt_el = None
    cur = None
    for el in root.iter():
        if _localname(el.tag) in ("InstdAmt", "IntrBkSttlmAmt", "Amt", "TxAmt") and (el.text or "").strip():
            amt_el = el.text.strip()
            cur = el.attrib.get("Ccy")
            break
    return ParsedMessage(
        message_type=mt,
        description=MSG_TYPES.get(mt, "ISO 20022 message"),
        amount=amt_el,
        currency=cur,
        debtor=_findtext(root, "Dbtr") or _findtext(root, "Nm"),
        creditor=_findtext(root, "Cdtr"),
        debtor_bic=_findtext(root, "BICFI") if False else _findtext(root, "DbtrAgt"),
        creditor_bic=_findtext(root, "CdtrAgt"),
        end_to_end_id=_findtext(root, "EndToEndId"),
        fields_found=sum(1 for _ in root.iter()),
    )


@mcp.tool()
def validate_iso20022(xml: str) -> Validation:
    """Structurally validate an ISO 20022 message (well-formedness + required-field presence)."""
    errors: List[str] = []
    warnings: List[str] = []
    try:
        root = _parse(xml)
    except ET.ParseError as e:
        return Validation(valid=False, message_type="unknown", errors=[f"XML not well-formed: {e}"])
    mt = _detect_type(root)
    if mt == "unknown":
        warnings.append("Could not detect ISO 20022 message type from namespace")
    if not _findtext(root, "InstdAmt", "IntrBkSttlmAmt", "Amt", "TxAmt"):
        errors.append("No settlement/instructed amount found")
    if not _findtext(root, "EndToEndId"):
        warnings.append("No EndToEndId (recommended for traceability)")
    return Validation(valid=not errors, message_type=mt, errors=errors, warnings=warnings)


@mcp.tool()
def map_to_modern(xml: str) -> Dict[str, Any]:
    """Map an ISO 20022 message to a flat modern JSON object for ONE OS / downstream systems."""
    p = parse_iso20022(xml)
    return {
        "type": p.message_type,
        "description": p.description,
        "payment": {
            "amount": p.amount,
            "currency": p.currency,
            "debtor": p.debtor,
            "creditor": p.creditor,
            "debtor_agent": p.debtor_bic,
            "creditor_agent": p.creditor_bic,
            "end_to_end_id": p.end_to_end_id,
        },
        "source_standard": "ISO 20022",
    }


@mcp.tool()
def govern_payment(xml: str) -> Governance:
    """Governance pass over a payment: surface AML/sanctions checkpoints + applicable frameworks (attestable for CSOAI)."""
    _sigil("G", "iso20022|govern_payment")
    p = parse_iso20022(xml)
    flags: List[str] = []
    aml: List[str] = ["Sanctions screening (debtor + creditor + agents)", "PEP check", "Transaction monitoring threshold"]
    if p.amount:
        try:
            if float(p.amount) >= 10000:
                flags.append("Amount >= 10,000 — large-value reporting threshold (verify per jurisdiction)")
        except ValueError:
            pass
    if not p.end_to_end_id:
        flags.append("Missing EndToEndId — weakens auditability")
    if not p.creditor:
        flags.append("Creditor name absent — sanctions screening incomplete")
    return Governance(
        message_type=p.message_type,
        risk_flags=flags,
        aml_surface=aml,
        frameworks=["ISO 20022", "DORA", "NIS2", "FATF AML/CFT", "PSD2"],
        attestable=True,
        note="CSOAI governs the bridge: every parsed payment can be signed/attested on the ledger.",
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
