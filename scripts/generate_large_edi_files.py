"""Generate large EDI files for testing progress tracking and memory usage."""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


def generate_837_header(sender_id: str = "SENDERID", receiver_id: str = "RECEIVERID") -> str:
    """Generate ISA/GS/ST header for 837 file."""
    date_str = datetime.now().strftime("%y%m%d")
    time_str = datetime.now().strftime("%H%M")
    
    return f"""ISA*00*          *00*          *ZZ*{sender_id:<15}*ZZ*{receiver_id:<15}*{date_str}*{time_str}*^*00501*000000001*0*P*:~
GS*HC*{sender_id}*{receiver_id}*{date_str}*{time_str}*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*{date_str}*{time_str}*CH~
NM1*41*2*SAMPLE MEDICAL PRACTICE*****46*1234567890~
PER*IC*CONTACT NAME*TE*5551234567~
NM1*40*2*BLUE CROSS BLUE SHIELD*****46*BLUE_CROSS~
HL*1**20*1~
PRV*BI*PXC*207RI0001X~
NM1*85*2*DR JOHN SMITH*****XX*1234567890~
N3*123 MAIN ST~
N4*CITY*NY*10001~
REF*EI*123456789~
NM1*87*2~
N3*456 PATIENT ST~
N4*PATIENT CITY*NY*10002~"""


def generate_837_claim(claim_idx: int, patient_idx: int, service_date_offset: int = 0) -> str:
    """Generate a single 837 claim with all required segments."""
    service_date = (datetime.now() - timedelta(days=service_date_offset)).strftime("%Y%m%d")
    claim_num = f"CLAIM{claim_idx:06d}"
    patient_num = f"PATIENT{patient_idx:06d}"
    
    return f"""HL*{claim_idx}*1*22*0~
SBR*P*18*GROUP{claim_idx % 1000:03d}******CI~
NM1*IL*1*DOE*JOHN*M***MI*123456789{patient_idx % 10}~
DMG*D8*19800101*M~
NM1*PR*2*BLUE CROSS BLUE SHIELD*****PI*BLUE_CROSS~
CLM*{claim_num}*{1500.00 + (claim_idx * 10):.2f}***11:A:1*Y*A*Y*I~
DTP*431*D8*{service_date}~
DTP*484*D8*{service_date}~
REF*D9*{patient_num}~
HI*ABK:I10*E11.9~
LX*1~
SV1*HC:99213*{1500.00 + (claim_idx * 10):.2f}*UN*1***1~
DTP*472*D8*{service_date}~"""


def generate_837_footer(segment_count: int) -> str:
    """Generate SE/GE/IEA footer for 837 file."""
    return f"""SE*{segment_count}*0001~
GE*1*1~
IEA*1*000000001~"""


def generate_835_header(sender_id: str = "BCBSILPAYER", receiver_id: str = "MEDPRACTICE001") -> str:
    """Generate ISA/GS/ST header for 835 file."""
    date_str = datetime.now().strftime("%y%m%d")
    time_str = datetime.now().strftime("%H%M%S")
    
    return f"""ISA*00*          *00*          *ZZ*{sender_id:<15}*ZZ*{receiver_id:<15}*{date_str}*{time_str}*^*00501*000000001*0*P*:~
GS*HP*{sender_id}*{receiver_id}*{date_str}*{time_str}*1*X*005010X221A1~
ST*835*0001*005010X221A1~
BPR*I*28750.00*C*CHK987654321*{date_str}*123456789*01*987654321*DA*1234567890*{date_str}~
TRN*1*REM{date_str}001*987654321~
REF*EV*REM{date_str}001~
DTM*405*{date_str}~
DTM*097*{date_str}*{date_str}~
N1*PR*BLUE CROSS BLUE SHIELD OF ILLINOIS~
N3*300 EAST RANDOLPH STREET~
N4*CHICAGO*IL*60601~
PER*BL*CLAIMS DEPARTMENT*TE*8005551234*FX*8005555678~"""


def generate_835_remittance(remit_idx: int, claim_num: str, patient_num: str, service_date_offset: int = 0) -> str:
    """Generate a single 835 remittance with all required segments."""
    service_date = (datetime.now() - timedelta(days=service_date_offset)).strftime("%Y%m%d")
    claim_amount = 1500.00 + (remit_idx * 10)
    paid_amount = claim_amount * 0.8  # 80% paid
    
    return f"""LX*{remit_idx}~
CLP*{claim_num}*1*{claim_amount:.2f}*{paid_amount:.2f}*0*11*123456789{remit_idx % 10}*{service_date}*1~
CAS*PR*1*{claim_amount * 0.05:.2f}~
CAS*PR*2*{claim_amount * 0.10:.2f}~
CAS*CO*45*{claim_amount * 0.05:.2f}~
NM1*QC*1*PATIENT*JOHN*M***MI*123456789{remit_idx % 10}~
NM1*82*1*PROVIDER*JANE*M***XX*1234567890~
REF*D9*{patient_num}~
REF*1W*123456789{remit_idx % 10}~
AMT*AU*{claim_amount * 0.20:.2f}~
AMT*D*{claim_amount * 0.05:.2f}~
AMT*F5*{claim_amount * 0.10:.2f}~
SVC*HC:99213*{claim_amount:.2f}*{paid_amount:.2f}*UN*1~
DTM*472*D8*{service_date}~
CAS*CO*45*{claim_amount * 0.05:.2f}~
CAS*PR*1*{claim_amount * 0.05:.2f}~
CAS*PR*2*{claim_amount * 0.10:.2f}~"""


def generate_835_footer(segment_count: int) -> str:
    """Generate SE/GE/IEA footer for 835 file."""
    return f"""SE*{segment_count}*0001~
GE*1*1~
IEA*1*000000001~"""


def generate_837_file(num_claims: int, output_path: Path, sender_id: Optional[str] = None, receiver_id: Optional[str] = None) -> None:
    """Generate a large 837 EDI file with the specified number of claims."""
    print(f"Generating 837 file with {num_claims:,} claims...")
    
    header = generate_837_header(
        sender_id or "SENDERID",
        receiver_id or "RECEIVERID"
    )
    
    # Count header segments (approximate)
    header_segments = len(header.split("~")) - 1  # Exclude empty last segment
    
    claims = []
    for i in range(2, num_claims + 2):  # Start at 2 because HL*1 is in header
        claim = generate_837_claim(i, i % 1000, i % 30)
        claims.append(claim)
    
    claims_content = "".join(claims)
    
    # Calculate total segment count
    # Each claim has approximately 12 segments
    claim_segments = num_claims * 12
    total_segments = header_segments + claim_segments + 3  # +3 for SE/GE/IEA
    
    footer = generate_837_footer(total_segments)
    
    full_content = header + claims_content + footer
    
    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_content)
    
    file_size_mb = len(full_content.encode("utf-8")) / (1024 * 1024)
    print(f"✓ Generated {output_path}")
    print(f"  Size: {file_size_mb:.2f} MB")
    print(f"  Claims: {num_claims:,}")
    print(f"  Segments: ~{total_segments:,}")


def generate_835_file(num_remittances: int, output_path: Path, sender_id: Optional[str] = None, receiver_id: Optional[str] = None) -> None:
    """Generate a large 835 EDI file with the specified number of remittances."""
    print(f"Generating 835 file with {num_remittances:,} remittances...")
    
    header = generate_835_header(
        sender_id or "BCBSILPAYER",
        receiver_id or "MEDPRACTICE001"
    )
    
    # Count header segments
    header_segments = len(header.split("~")) - 1
    
    remittances = []
    for i in range(1, num_remittances + 1):
        claim_num = f"CLAIM{i:06d}"
        patient_num = f"PATIENT{i % 1000:06d}"
        remittance = generate_835_remittance(i, claim_num, patient_num, i % 30)
        remittances.append(remittance)
    
    remittances_content = "".join(remittances)
    
    # Calculate total segment count
    # Each remittance has approximately 15 segments
    remit_segments = num_remittances * 15
    total_segments = header_segments + remit_segments + 3  # +3 for SE/GE/IEA
    
    footer = generate_835_footer(total_segments)
    
    full_content = header + remittances_content + footer
    
    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_content)
    
    file_size_mb = len(full_content.encode("utf-8")) / (1024 * 1024)
    print(f"✓ Generated {output_path}")
    print(f"  Size: {file_size_mb:.2f} MB")
    print(f"  Remittances: {num_remittances:,}")
    print(f"  Segments: ~{total_segments:,}")


def main():
    """Main entry point for EDI file generator."""
    parser = argparse.ArgumentParser(
        description="Generate large EDI files for testing progress tracking and memory usage"
    )
    parser.add_argument(
        "--type",
        choices=["837", "835", "both"],
        default="both",
        help="Type of EDI file to generate (default: both)",
    )
    parser.add_argument(
        "--claims",
        type=int,
        default=1000,
        help="Number of claims for 837 file (default: 1000)",
    )
    parser.add_argument(
        "--remittances",
        type=int,
        default=1000,
        help="Number of remittances for 835 file (default: 1000)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("samples/large"),
        help="Output directory for generated files (default: samples/large)",
    )
    parser.add_argument(
        "--sender-id",
        type=str,
        help="Sender ID for EDI files (optional)",
    )
    parser.add_argument(
        "--receiver-id",
        type=str,
        help="Receiver ID for EDI files (optional)",
    )
    
    args = parser.parse_args()
    
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if args.type in ["837", "both"]:
        output_path = output_dir / f"large_837_{args.claims}claims.edi"
        generate_837_file(
            args.claims,
            output_path,
            args.sender_id,
            args.receiver_id,
        )
    
    if args.type in ["835", "both"]:
        output_path = output_dir / f"large_835_{args.remittances}remits.edi"
        generate_835_file(
            args.remittances,
            output_path,
            args.sender_id,
            args.receiver_id,
        )
    
    print("\n✓ File generation complete!")
    print(f"\nGenerated files are in: {output_dir.absolute()}")
    print("\nTo test with these files:")
    print("  python -m pytest tests/test_progress_tracking.py -v")
    print("  python -m pytest tests/test_memory_usage.py -v")


if __name__ == "__main__":
    main()

