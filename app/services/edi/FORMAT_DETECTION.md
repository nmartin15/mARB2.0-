# Dynamic Format Detection System

## Overview

The dynamic format detection system allows the EDI parser to automatically adapt to different 837 file formats from various ASCs (Ambulatory Surgical Centers) and practices without hardcoding format-specific logic.

## Key Components

### 1. FormatDetector (`format_detector.py`)
Automatically analyzes 837 files and identifies:
- **Segment patterns**: Which segments are present and how frequently
- **Element counts**: How many elements each segment type typically has
- **Date formats**: What date format qualifiers are used (D8, RD8, TM, DT)
- **Diagnosis qualifiers**: Which diagnosis code qualifiers are used (ABK, APR, ABF, etc.)
- **Facility codes**: What facility type codes appear in the data
- **Version detection**: EDI version/release number

### 2. FormatProfile (`format_profile.py`)
Stores and manages format profiles for different practices:
- **Practice-specific profiles**: Each practice can have its own format profile
- **Database storage**: Profiles stored in `PracticeConfig.segment_expectations`
- **Auto-creation**: Profiles can be automatically created from file analysis

### 3. Adaptive Parser (`parser.py`)
The parser now:
- **Auto-detects format** on each file (enabled by default)
- **Adapts configuration** based on detected format
- **Returns format analysis** in parse results
- **Learns from each file** to improve parsing

## Usage

### Automatic Format Detection (Default)

```python
from app.services.edi.parser import EDIParser

# Parser automatically detects format
parser = EDIParser(practice_id="PRACTICE001", auto_detect_format=True)
result = parser.parse(file_content, "claim_file.txt")

# Format analysis included in result
format_info = result.get("format_analysis", {})
print(f"Version: {format_info.get('version')}")
print(f"Segments found: {format_info.get('segment_frequency')}")
```

### Manual Format Analysis

```python
from app.services.edi.format_detector import FormatDetector

detector = FormatDetector()
segments = parser._split_segments(file_content)
profile = detector.analyze_file(segments)

print(profile)
```

### Compare Two Files

```bash
python scripts/analyze_format.py compare file1.txt file2.txt
```

### Save Format Profile

```bash
python scripts/analyze_format.py save file.txt \
  --practice-id PRACTICE001 \
  --format-name "Rural Hospital Format"
```

## How It Works

1. **File Analysis**: When a file is parsed, the `FormatDetector` analyzes:
   - All segments and their frequency
   - Element counts per segment type
   - Date format patterns
   - Diagnosis code patterns
   - Facility code patterns

2. **Configuration Adaptation**: The parser adapts its configuration:
   - Updates segment expectations based on detected segments
   - Adjusts validation rules for detected patterns
   - Maintains flexibility for missing optional segments

3. **Profile Storage**: Format profiles can be saved:
   - Stored in `PracticeConfig` table
   - Linked to practice_id
   - Used for future files from same practice

4. **Comparison**: Compare formats:
   - Identify differences between two files
   - Detect new patterns or variations
   - Validate consistency

## Benefits

✅ **No Hardcoding**: Don't need to code for each client's format  
✅ **Automatic Adaptation**: Parser learns from each file  
✅ **Format Comparison**: Easily compare different formats  
✅ **Practice-Specific**: Each practice can have its own profile  
✅ **Resilient**: Handles variations and missing segments gracefully  
✅ **Documentation**: Format analysis provides insights into file structure  

## Example Output

```
=== FORMAT ANALYSIS ===
Version: 005010X222A1
File Type: 837

Segment Frequency:
  CLM: 48
  NM1: 192
  DTP: 144
  HI: 48
  SBR: 48
  ...

Date Formats:
  D8: 120
  RD8: 44
  TM: 5

Diagnosis Qualifiers:
  ABK: 48
  APR: 35
  ABF: 12

Facility Codes:
  13: 30
  85: 13
  11: 4
```

## Future Enhancements

- **Machine Learning**: Use ML to predict format based on file characteristics
- **Format Clustering**: Group similar formats automatically
- **Validation Rules**: Auto-generate validation rules from format profiles
- **Format Migration**: Detect when a practice changes format
- **Quality Metrics**: Track parsing success rates per format

