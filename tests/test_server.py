import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server

XML='<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"><FIToFICstmrCdtTrf><CdtTrfTxInf><PmtId><EndToEndId>E2E1</EndToEndId></PmtId><IntrBkSttlmAmt Ccy="GBP">15000</IntrBkSttlmAmt></CdtTrfTxInf></FIToFICstmrCdtTrf></Document>'
def test_parse():
    p=server.parse_iso20022(XML); assert p.message_type=="pacs.008"; assert p.currency=="GBP"
def test_govern():
    assert "DORA" in server.govern_payment(XML).frameworks
def test_validate_bad():
    assert server.validate_iso20022("not xml").valid is False
