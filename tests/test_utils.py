"""Utility functions and helpers for tests."""
from typing import Any, Dict

import pytest


def assert_response_structure(response_data: Dict[str, Any], expected_keys: list):
    """Assert that response contains expected keys."""
    for key in expected_keys:
        assert key in response_data, f"Missing key: {key}"


def assert_pagination_response(response_data: Dict[str, Any]):
    """Assert that response has pagination structure."""
    assert "total" in response_data
    assert "skip" in response_data
    assert "limit" in response_data
    assert "claims" in response_data or "items" in response_data


@pytest.fixture
def sample_edi_837_content() -> str:
    """Sample EDI 837 content for testing."""
    return """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *230101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20230101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*0001*20230101*1200*CH~
NM1*41*2*SENDER*****46*123456789~
PER*IC*CONTACT*TE*5551234567~
NM1*40*2*RECEIVER*****46*987654321~
HL*1**20*1~
PRV*BI*PXC*207Q00000X~
NM1*85*2*PROVIDER*****XX*1234567890~
N3*123 MAIN ST~
N4*CITY*ST*12345~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*GROUP123*ACME INSURANCE*****CI~
NM1*IL*1*DOE*JOHN****MI*123456789~
N3*456 PATIENT ST~
N4*CITY*ST*54321~
DMG*D8*19800101*M~
NM1*PR*2*ACME INSURANCE*****PI*987654321~
CLM*CLM001*1000***11:B:1*Y*A*Y*I~
DTP*431*D8*20230101~
HI*BK:E11.9~
LX*1~
SV1*HC:99213*100*UN*1***1~
DTP*472*D8*20230101~
SE*15*0001~
GE*1*1~
IEA*1*000000001~"""


@pytest.fixture
def sample_edi_835_content() -> str:
    """Sample EDI 835 content for testing."""
    return """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *230101*1200*^*00501*000000001*0*P*:~
GS*HP*SENDER*RECEIVER*20230101*1200*1*X*005010X221A1~
ST*835*0001*005010X221A1~
BPR*I*1000*C*CHK123456*20230101*123456789*01*987654321*DA*1234567890*20230101~
TRN*1*123456789*987654321~
REF*EV*REM001~
DTM*405*20230101~
N1*PR*ACME INSURANCE~
N3*789 INSURANCE ST~
N4*CITY*ST*67890~
LX*1~
CLP*CLM001*1*1000*800*200*11*1234567890~
CAS*CO*45*100~
NM1*QC*1*DOE*JOHN~
SE*12*0001~
GE*1*1~
IEA*1*000000001~"""

