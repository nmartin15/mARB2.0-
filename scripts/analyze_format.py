#!/usr/bin/env python3
"""Analyze 837 file format and create/compare format profiles."""
import os
import sys
import json
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from app.config.database import SessionLocal
from app.services.edi.parser import EDIParser
from app.services.edi.format_detector import FormatDetector
from app.services.edi.format_profile import FormatProfileManager
from app.utils.logger import get_logger

logger = get_logger(__name__)


def analyze_file(filepath: str, practice_id: str = None) -> dict:
    """
    Analyze an 837 file and return format profile.
    
    Args:
        filepath: Path to the 837 EDI file to analyze
        practice_id: Optional practice ID for format detection
        
    Returns:
        Dictionary containing format analysis with keys:
        - version: EDI version
        - file_type: Type of EDI file
        - segment_frequency: Dictionary of segment types and their counts
        - date_formats: Dictionary of date formats found
        - diagnosis_qualifiers: Dictionary of diagnosis qualifiers
        - facility_codes: Dictionary of facility codes
        
    Raises:
        FileNotFoundError: If the file does not exist
        PermissionError: If file cannot be read
        IOError: If file reading fails
        ValueError: If EDI parsing fails
        AttributeError: If parser result has unexpected structure
        TypeError: If parser result is not a dictionary
    """
    print(f"Analyzing file: {filepath}")
    
    # Validate filepath
    if not filepath or not isinstance(filepath, str):
        logger.error("Invalid filepath provided", filepath=filepath, filepath_type=type(filepath).__name__)
        raise ValueError(f"Invalid filepath: {filepath}")
    
    # Read file with specific error handling
    try:
        if not os.path.exists(filepath):
            logger.error("File not found", filepath=filepath)
            raise FileNotFoundError(f"File not found: {filepath}")
        
        if os.path.isdir(filepath):
            logger.error("Path is a directory, not a file", filepath=filepath)
            raise IsADirectoryError(f"Path is a directory, not a file: {filepath}")
        
        if not os.access(filepath, os.R_OK):
            logger.error("Permission denied reading file", filepath=filepath)
            raise PermissionError(f"Permission denied reading file: {filepath}")
        
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        if not content or not content.strip():
            logger.error("File is empty", filepath=filepath)
            raise ValueError(f"File is empty: {filepath}")
            
    except FileNotFoundError:
        raise
    except PermissionError:
        raise
    except IsADirectoryError:
        raise
    except UnicodeDecodeError as e:
        logger.error("Unicode decode error reading file", filepath=filepath, error=str(e), encoding=e.encoding)
        raise IOError(f"Unicode decode error reading file {filepath}: {e}")
    except OSError as e:
        logger.error("OS error reading file", filepath=filepath, error=str(e), errno=e.errno)
        raise IOError(f"OS error reading file {filepath}: {e}")
    except Exception as e:
        logger.error("Unexpected error reading file", filepath=filepath, error=str(e), error_type=type(e).__name__)
        raise IOError(f"Error reading file {filepath}: {e}")
    
    # Parse file with specific error handling
    try:
        parser = EDIParser(practice_id=practice_id, auto_detect_format=True)
        result = parser.parse(content, os.path.basename(filepath))
        
        # Validate parser result structure
        if not isinstance(result, dict):
            logger.error("Parser returned non-dict result", filepath=filepath, result_type=type(result).__name__)
            raise TypeError(f"Parser returned unexpected type {type(result).__name__}, expected dict")
        
    except ValueError as e:
        logger.error("Value error parsing EDI file", filepath=filepath, error=str(e))
        raise ValueError(f"Failed to parse EDI file {filepath}: {e}")
    except KeyError as e:
        logger.error("Missing required key in EDI file", filepath=filepath, error=str(e))
        raise ValueError(f"Invalid EDI file format {filepath}: missing key {e}")
    except AttributeError as e:
        logger.error("Attribute error parsing EDI file", filepath=filepath, error=str(e))
        raise AttributeError(f"Parser error for file {filepath}: {e}")
    except TypeError as e:
        logger.error("Type error parsing EDI file", filepath=filepath, error=str(e))
        raise TypeError(f"Parser type error for file {filepath}: {e}")
    except Exception as e:
        logger.error("Unexpected error parsing EDI file", filepath=filepath, error=str(e), error_type=type(e).__name__)
        raise ValueError(f"Failed to parse EDI file {filepath}: {e}")
    
    # Get format analysis with validation
    if "format_analysis" not in result:
        logger.warning("No format_analysis in parser result, using empty dict", filepath=filepath)
        format_analysis = {}
    else:
        format_analysis = result.get("format_analysis", {})
        if not isinstance(format_analysis, dict):
            logger.warning("format_analysis is not a dict, using empty dict", filepath=filepath, format_analysis_type=type(format_analysis).__name__)
            format_analysis = {}
    
    print("\n=== FORMAT ANALYSIS ===")
    print(f"Version: {format_analysis.get('version', 'Unknown')}")
    print(f"File Type: {format_analysis.get('file_type', 'Unknown')}")
    print(f"\nSegment Frequency:")
    for seg, count in sorted(
        format_analysis.get("segment_frequency", {}).items(),
        key=lambda x: x[1],
        reverse=True,
    )[:20]:
        print(f"  {seg}: {count}")
    
    print(f"\nDate Formats:")
    for fmt, count in format_analysis.get("date_formats", {}).items():
        print(f"  {fmt}: {count}")
    
    print(f"\nDiagnosis Qualifiers:")
    for qual, count in format_analysis.get("diagnosis_qualifiers", {}).items():
        print(f"  {qual}: {count}")
    
    print(f"\nFacility Codes:")
    for code, count in format_analysis.get("facility_codes", {}).items():
        print(f"  {code}: {count}")
    
    return format_analysis


def compare_files(file1: str, file2: str) -> None:
    """
    Compare two 837 files and show differences.
    
    Args:
        file1: Path to first 837 EDI file
        file2: Path to second 837 EDI file
        
    Returns:
        None (prints comparison results to stdout)
        
    Raises:
        FileNotFoundError: If either file does not exist
        IOError: If files cannot be read
    """
    print(f"Comparing files:")
    print(f"  File 1: {file1}")
    print(f"  File 2: {file2}\n")
    
    detector = FormatDetector()
    
    # Analyze both files
    with open(file1, "r", encoding="utf-8", errors="ignore") as f:
        content1 = f.read()
    parser1 = EDIParser(auto_detect_format=True)
    segments1 = parser1._split_segments(content1)
    profile1 = detector.analyze_file(segments1)
    
    with open(file2, "r", encoding="utf-8", errors="ignore") as f:
        content2 = f.read()
    parser2 = EDIParser(auto_detect_format=True)
    segments2 = parser2._split_segments(content2)
    profile2 = detector.analyze_file(segments2)
    
    # Compare
    differences = detector.compare_profiles(profile1, profile2)
    
    print("=== COMPARISON RESULTS ===\n")
    
    print("Segment Differences:")
    seg_diff = differences.get("segment_differences", {})
    if seg_diff.get("only_in_1"):
        print(f"  Only in File 1: {seg_diff['only_in_1']}")
    if seg_diff.get("only_in_2"):
        print(f"  Only in File 2: {seg_diff['only_in_2']}")
    if not seg_diff.get("only_in_1") and not seg_diff.get("only_in_2"):
        print("  No segment differences")
    
    print("\nDate Format Differences:")
    date_diff = differences.get("date_format_differences", {})
    if date_diff.get("only_in_1"):
        print(f"  Only in File 1: {date_diff['only_in_1']}")
    if date_diff.get("only_in_2"):
        print(f"  Only in File 2: {date_diff['only_in_2']}")
    if not date_diff.get("only_in_1") and not date_diff.get("only_in_2"):
        print("  No date format differences")
    
    print("\nDiagnosis Qualifier Differences:")
    diag_diff = differences.get("diagnosis_qualifier_differences", {})
    if diag_diff.get("only_in_1"):
        print(f"  Only in File 1: {diag_diff['only_in_1']}")
    if diag_diff.get("only_in_2"):
        print(f"  Only in File 2: {diag_diff['only_in_2']}")
    if not diag_diff.get("only_in_1") and not diag_diff.get("only_in_2"):
        print("  No diagnosis qualifier differences")
    
    print("\nFacility Code Differences:")
    fac_diff = differences.get("facility_code_differences", {})
    if fac_diff.get("only_in_1"):
        print(f"  Only in File 1: {fac_diff['only_in_1']}")
    if fac_diff.get("only_in_2"):
        print(f"  Only in File 2: {fac_diff['only_in_2']}")
    if not fac_diff.get("only_in_1") and not fac_diff.get("only_in_2"):
        print("  No facility code differences")


def save_profile(filepath: str, practice_id: str, format_name: str) -> None:
    """
    Analyze file and save format profile to database.
    
    Args:
        filepath: Path to the 837 EDI file to analyze
        practice_id: Practice ID for the format profile
        format_name: Name to assign to the format profile
        
    Returns:
        None (prints status messages to stdout)
        
    Raises:
        FileNotFoundError: If the file does not exist
        IOError: If file cannot be read
        ValueError: If EDI parsing fails
        DatabaseError: If database operation fails
    """
    print(f"Creating format profile for: {format_name}")
    
    db = SessionLocal()
    try:
        # Analyze file
        format_analysis = analyze_file(filepath, practice_id)
        
        # Create and save profile
        manager = FormatProfileManager(db)
        profile = manager.create_profile_from_analysis(
            practice_id, format_name, format_analysis
        )
        
        print(f"\n✓ Format profile saved for practice: {practice_id}")
        print(f"  Format name: {format_name}")
        
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Analyze and compare 837 file formats")
    parser.add_argument("command", choices=["analyze", "compare", "save"], help="Command to run")
    parser.add_argument("file1", help="First 837 file path")
    parser.add_argument("file2", nargs="?", help="Second 837 file path (for compare)")
    parser.add_argument("--practice-id", help="Practice ID (for save command)")
    parser.add_argument("--format-name", help="Format name (for save command)")
    
    args = parser.parse_args()
    
    if args.command == "analyze":
        analyze_file(args.file1)
    elif args.command == "compare":
        if not args.file2:
            print("Error: compare command requires two files")
            sys.exit(1)
        compare_files(args.file1, args.file2)
    elif args.command == "save":
        if not args.practice_id or not args.format_name:
            print("Error: save command requires --practice-id and --format-name")
            sys.exit(1)
        save_profile(args.file1, args.practice_id, args.format_name)


if __name__ == "__main__":
    main()

