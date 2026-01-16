"""Generate production-quality synthetic training data for ML models.

This creates clearinghouse-quality 837 (claims) and 835 (remittances) EDI files
with realistic denial patterns, payment scenarios, and diverse claim types.
"""
import argparse
import sys
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import json
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils.logger import get_logger

logger = get_logger(__name__)

# ============================================================================
# LOAD CPT AND DIAGNOSIS CODES FROM EXTERNAL FILES
# ============================================================================


def load_cpt_codes(data_dir: Path = None) -> Tuple[Dict, Dict]:
    """
    Load CPT codes from external JSON file.
    
    Args:
        data_dir: Directory containing data files (default: ml/training/data)
        
    Returns:
        Tuple of (cpt_by_specialty dict, specialty_weights dict)
    """
    if data_dir is None:
        data_dir = Path(__file__).parent / "data"
    
    cpt_file = data_dir / "cpt_codes.json"
    
    try:
        with open(cpt_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Convert lists to tuples for immutability
        cpt_by_specialty = {}
        for specialty, codes in data.get("cpt_by_specialty", {}).items():
            cpt_by_specialty[specialty] = [tuple(code) for code in codes]
        
        specialty_weights = data.get("specialty_weights", {})
        
        logger.info("Loaded CPT codes from external file", file=str(cpt_file), specialties=len(cpt_by_specialty))
        return cpt_by_specialty, specialty_weights
    except FileNotFoundError:
        logger.warning("CPT codes file not found, using fallback", file=str(cpt_file))
        return _get_fallback_cpt_codes()
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Error loading CPT codes file", file=str(cpt_file), error=str(e))
        raise ValueError(f"Invalid CPT codes file format: {e}")


def load_diagnosis_codes(data_dir: Path = None) -> Tuple[Dict, List[float]]:
    """
    Load diagnosis codes from external JSON file.
    
    Args:
        data_dir: Directory containing data files (default: ml/training/data)
        
    Returns:
        Tuple of (diagnosis_by_category dict, category_weights list)
    """
    if data_dir is None:
        data_dir = Path(__file__).parent / "data"
    
    diagnosis_file = data_dir / "diagnosis_codes.json"
    
    try:
        with open(diagnosis_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        diagnosis_by_category = data.get("diagnosis_by_category", {})
        category_weights = data.get("category_weights", [])
        
        logger.info("Loaded diagnosis codes from external file", file=str(diagnosis_file), categories=len(diagnosis_by_category))
        return diagnosis_by_category, category_weights
    except FileNotFoundError:
        logger.warning("Diagnosis codes file not found, using fallback", file=str(diagnosis_file))
        return _get_fallback_diagnosis_codes()
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Error loading diagnosis codes file", file=str(diagnosis_file), error=str(e))
        raise ValueError(f"Invalid diagnosis codes file format: {e}")


def _get_fallback_cpt_codes() -> Tuple[Dict, Dict]:
    """Fallback CPT codes if external file is not available."""
    cpt_by_specialty = {
    "primary_care": [
        # Office visits
        ("99211", "Office visit, level 1", 50.0, 80.0, 0.15),
        ("99212", "Office visit, level 2", 80.0, 120.0, 0.20),
        ("99213", "Office visit, level 3", 120.0, 180.0, 0.35),
        ("99214", "Office visit, level 4", 180.0, 280.0, 0.20),
        ("99215", "Office visit, level 5", 280.0, 400.0, 0.10),
        # New patient visits
        ("99201", "New patient, level 1", 80.0, 120.0, 0.05),
        ("99202", "New patient, level 2", 120.0, 180.0, 0.10),
        ("99203", "New patient, level 3", 180.0, 280.0, 0.15),
        ("99204", "New patient, level 4", 280.0, 400.0, 0.08),
        ("99205", "New patient, level 5", 400.0, 600.0, 0.02),
        # Preventive care
        ("99391", "Preventive visit, 18-39", 150.0, 250.0, 0.10),
        ("99392", "Preventive visit, 40-64", 200.0, 300.0, 0.12),
        ("99393", "Preventive visit, 65+", 250.0, 350.0, 0.08),
        # Labs
        ("80053", "Comprehensive metabolic panel", 40.0, 80.0, 0.25),
        ("85025", "Complete blood count", 25.0, 50.0, 0.30),
        ("80061", "Lipid panel", 30.0, 60.0, 0.20),
        ("81001", "Urinalysis", 15.0, 30.0, 0.15),
        ("36415", "Venipuncture", 10.0, 20.0, 0.40),
        # Procedures
        ("93000", "ECG", 40.0, 80.0, 0.15),
        ("71020", "Chest X-ray", 80.0, 150.0, 0.10),
        ("76700", "Abdominal ultrasound", 200.0, 400.0, 0.05),
    ],
    "cardiology": [
        ("99213", "Office visit", 150.0, 250.0, 0.20),
        ("99214", "Office visit", 200.0, 350.0, 0.30),
        ("99215", "Office visit", 300.0, 500.0, 0.15),
        ("93000", "ECG", 50.0, 100.0, 0.40),
        ("93010", "ECG with interpretation", 80.0, 150.0, 0.25),
        ("93306", "Echocardiogram", 400.0, 800.0, 0.30),
        ("93307", "Echo with doppler", 500.0, 1000.0, 0.20),
        ("93015", "Stress test", 300.0, 600.0, 0.15),
        ("78452", "Nuclear stress test", 800.0, 1500.0, 0.10),
        ("92920", "Angioplasty", 2000.0, 5000.0, 0.05),
        ("92928", "Stent placement", 3000.0, 8000.0, 0.03),
    ],
    "orthopedics": [
        ("99213", "Office visit", 150.0, 250.0, 0.25),
        ("99214", "Office visit", 200.0, 350.0, 0.30),
        ("99215", "Office visit", 300.0, 500.0, 0.15),
        ("73060", "Knee X-ray", 80.0, 150.0, 0.20),
        ("73070", "Hip X-ray", 80.0, 150.0, 0.15),
        ("72040", "Spine X-ray", 100.0, 200.0, 0.20),
        ("72141", "MRI spine", 800.0, 1500.0, 0.25),
        ("73721", "MRI knee", 600.0, 1200.0, 0.20),
        ("29881", "Knee arthroscopy", 2000.0, 5000.0, 0.10),
        ("27447", "Knee replacement", 15000.0, 30000.0, 0.05),
        ("27130", "Hip replacement", 20000.0, 40000.0, 0.03),
    ],
    "gastroenterology": [
        ("99213", "Office visit", 150.0, 250.0, 0.20),
        ("99214", "Office visit", 200.0, 350.0, 0.30),
        ("45378", "Colonoscopy", 800.0, 2000.0, 0.40),
        ("43239", "Upper endoscopy", 600.0, 1500.0, 0.30),
        ("43235", "EGD with biopsy", 700.0, 1800.0, 0.25),
        ("76700", "Abdominal ultrasound", 200.0, 400.0, 0.15),
        ("74177", "CT abdomen", 400.0, 800.0, 0.20),
    ],
    "dermatology": [
        ("99213", "Office visit", 120.0, 200.0, 0.25),
        ("99214", "Office visit", 180.0, 300.0, 0.35),
        ("11300", "Shave removal", 100.0, 200.0, 0.20),
        ("11400", "Excision benign", 200.0, 400.0, 0.15),
        ("17000", "Destruction lesion", 150.0, 300.0, 0.20),
        ("17003", "Destruction multiple", 300.0, 600.0, 0.10),
        ("11104", "Punch biopsy", 200.0, 400.0, 0.15),
    ],
    "urology": [
        ("99213", "Office visit", 150.0, 250.0, 0.20),
        ("99214", "Office visit", 200.0, 350.0, 0.30),
        ("52000", "Cystoscopy", 500.0, 1000.0, 0.25),
        ("76770", "Prostate ultrasound", 300.0, 600.0, 0.20),
        ("55866", "Prostate biopsy", 800.0, 1500.0, 0.15),
        ("52601", "TURP", 3000.0, 6000.0, 0.10),
    ],
    "oncology": [
        ("99214", "Office visit", 250.0, 400.0, 0.30),
        ("99215", "Office visit", 350.0, 600.0, 0.25),
        ("96413", "Chemotherapy", 500.0, 1500.0, 0.40),
        ("77334", "Radiation therapy", 1000.0, 3000.0, 0.30),
        ("88104", "Cytopathology", 200.0, 400.0, 0.20),
        ("88305", "Surgical pathology", 150.0, 300.0, 0.25),
    ],
    "emergency": [
        ("99281", "ER level 1", 200.0, 400.0, 0.05),
        ("99282", "ER level 2", 300.0, 600.0, 0.10),
        ("99283", "ER level 3", 500.0, 1000.0, 0.30),
        ("99284", "ER level 4", 800.0, 1500.0, 0.35),
        ("99285", "ER level 5", 1200.0, 2500.0, 0.20),
        ("36415", "IV placement", 50.0, 100.0, 0.40),
        ("71020", "Chest X-ray", 100.0, 200.0, 0.30),
        ("70450", "CT head", 400.0, 800.0, 0.25),
    ],
    }
    specialty_weights = {
        "primary_care": 0.35,
        "cardiology": 0.12,
        "orthopedics": 0.10,
        "gastroenterology": 0.08,
        "dermatology": 0.08,
        "urology": 0.07,
        "oncology": 0.05,
        "emergency": 0.15,
    }
    # Convert lists to tuples
    cpt_by_specialty_tuples = {}
    for specialty, codes in cpt_by_specialty.items():
        cpt_by_specialty_tuples[specialty] = [tuple(code) for code in codes]
    return cpt_by_specialty_tuples, specialty_weights


def _get_fallback_diagnosis_codes() -> Tuple[Dict, List[float]]:
    """Fallback diagnosis codes if external file is not available."""
    return {
        "diabetes": ["E11.9", "E11.65", "E11.21", "E11.22", "E11.29", "E10.9", "E10.65"],
        "hypertension": ["I10", "I11.9", "I12.9", "I13.9", "I16.9"],
        "cardiac": ["I25.10", "I50.9", "I21.9", "I48.91", "I10"],
        "respiratory": ["J06.9", "J44.1", "J18.9", "J45.909", "J44.0"],
        "musculoskeletal": ["M54.5", "M79.3", "M25.561", "M25.562", "S72.001A"],
        "gastrointestinal": ["K21.9", "K59.00", "K92.2", "K63.5", "K25.9"],
        "mental_health": ["F41.1", "F32.9", "F33.9", "F41.9", "F43.10"],
        "preventive": ["Z00.00", "Z00.121", "Z13.9", "Z51.11"],
        "infectious": ["B34.9", "A49.9", "J11.1", "J00"],
        "dermatology": ["L70.9", "L81.9", "L98.9", "C44.9"],
        "urology": ["N40.1", "N18.6", "N39.0", "N20.0"],
        "oncology": ["C50.9", "C61", "C34.10", "C25.9"],
    }, [0.20, 0.15, 0.12, 0.10, 0.10, 0.08, 0.08, 0.05, 0.05, 0.04, 0.02, 0.01]


# Load CPT and Diagnosis codes (with fallback to hardcoded values)
CPT_BY_SPECIALTY, SPECIALTY_WEIGHTS = load_cpt_codes()
DIAGNOSIS_BY_CATEGORY, CATEGORY_WEIGHTS = load_diagnosis_codes()

# Flatten and weight by specialty distribution
ALL_CPT_CODES = []
for specialty, codes in CPT_BY_SPECIALTY.items():
    specialty_weight = SPECIALTY_WEIGHTS.get(specialty, 0.0)
    for code_tuple in codes:
        code, desc, min_charge, max_charge, freq = code_tuple
        ALL_CPT_CODES.append((code, desc, min_charge, max_charge, specialty, freq * specialty_weight))

ALL_DIAGNOSIS_CODES = []
for codes in DIAGNOSIS_BY_CATEGORY.values():
    ALL_DIAGNOSIS_CODES.extend(codes)

# ============================================================================
# DENIAL REASON CODES (Comprehensive)
# ============================================================================

DENIAL_CODES = {
    "CO": {
        "16": "Claim/service lacks information which is needed for adjudication",
        "18": "Exact duplicate claim/service",
        "19": "This is a work-related injury/illness",
        "20": "This injury/illness is covered by another payer",
        "22": "This care may be covered by another payer per coordination of benefits",
        "23": "The impact of prior payer(s) adjudication including payments and/or adjustments",
        "29": "The time limit for filing has expired",
        "31": "Patient cannot be identified as our insured",
        "45": "Charge exceeds fee schedule/maximum allowable or contracted/legislated fee arrangement",
        "50": "These are non-covered services because this is not deemed a 'medical necessity'",
        "51": "These are non-covered because this is a pre-existing condition",
        "96": "Non-covered charge(s)",
        "97": "The benefit for this service is included in the payment/allowance for another service",
        "100": "Payment made to patient/insured",
        "101": "Predetermination: anticipated payment upon completion of services",
        "109": "Not covered by this payer/contractor",
        "110": "Billing date predates service date",
        "114": "Procedure/product not approved by the Food and Drug Administration",
        "115": "Procedure postponed, cancelled, or delayed",
        "116": "Prior authorization/pre-certification/notification missing",
        "149": "Lifetime benefit maximum has been reached",
        "151": "Payment adjusted because the payer deems the information submitted does not support this many/frequency of services",
        "152": "Payment adjusted because the payer deems the information submitted does not support this level of service",
        "153": "Payment adjusted because the payer deems the information submitted does not support this length of service",
        "154": "Payment adjusted because the payer deems the information submitted does not support this dosage",
        "155": "Payment adjusted because the payer deems the information submitted does not support this day's supply",
        "253": "Claim/service denied because the patient cannot be identified as eligible",
        "A6": "Prior hospitalization or 30 day transfer requirement not met",
    },
    "OA": {
        "23": "The impact of a prior payer's payment cannot be determined",
        "36": "Authorization exceeded",
        "97": "The benefit for this service is included in the payment/allowance for another service",
        "109": "Claim not covered by this payer/contractor",
        "110": "Billing date predates service date",
    },
    "PR": {
        "1": "Deductible Amount",
        "2": "Coinsurance Amount",
        "3": "Copayment Amount",
        "96": "Non-covered charge(s)",
    },
    "CR": {
        "97": "The benefit for this service is included in the payment/allowance for another service",
        "209": "Claim/service not covered by this payer/contractor",
    },
}

# ============================================================================
# PAYER CONFIGURATIONS
# ============================================================================

PAYERS = [
    {
        "id": "MEDICARE",
        "name": "Medicare",
        "denial_rate": 0.15,
        "payment_rate": 0.80,
        "common_denials": ["CO50", "CO96", "CO116"],
        "typical_adjustments": ["CO45", "PR1", "PR2"],
    },
    {
        "id": "MEDICAID",
        "name": "Medicaid",
        "denial_rate": 0.20,
        "payment_rate": 0.75,
        "common_denials": ["CO50", "CO253", "CO116"],
        "typical_adjustments": ["CO45", "PR1", "PR2"],
    },
    {
        "id": "BLUE_CROSS",
        "name": "Blue Cross Blue Shield",
        "denial_rate": 0.18,
        "payment_rate": 0.82,
        "common_denials": ["CO50", "CO96", "CO116", "OA23"],
        "typical_adjustments": ["CO45", "PR1", "PR2"],
    },
    {
        "id": "AETNA",
        "name": "Aetna",
        "denial_rate": 0.22,
        "payment_rate": 0.78,
        "common_denials": ["CO50", "CO96", "CO116"],
        "typical_adjustments": ["CO45", "PR1", "PR2"],
    },
    {
        "id": "CIGNA",
        "name": "Cigna",
        "denial_rate": 0.20,
        "payment_rate": 0.80,
        "common_denials": ["CO50", "CO96", "OA23"],
        "typical_adjustments": ["CO45", "PR1", "PR2"],
    },
    {
        "id": "UNITED",
        "name": "UnitedHealthcare",
        "denial_rate": 0.25,
        "payment_rate": 0.75,
        "common_denials": ["CO50", "CO96", "CO116", "CO97"],
        "typical_adjustments": ["CO45", "PR1", "PR2"],
    },
]

# ============================================================================
# PROVIDER DATA
# ============================================================================

PROVIDER_SPECIALTIES = [
    ("207RI0001X", "Internal Medicine", "primary_care"),
    ("207RC0000X", "Cardiology", "cardiology"),
    ("207X00000X", "Orthopedic Surgery", "orthopedics"),
    ("207RG0100X", "Gastroenterology", "gastroenterology"),
    ("207N00000X", "Dermatology", "dermatology"),
    ("208800000X", "Urology", "urology"),
    ("207RX0202X", "Medical Oncology", "oncology"),
    ("207P00000X", "Emergency Medicine", "emergency"),
]

PROVIDER_NPIS = [f"{random.randint(1000000000, 9999999999)}" for _ in range(50)]

# ============================================================================
# FACILITY TYPES
# ============================================================================

FACILITY_TYPES = [
    ("11", "Office", 0.60),
    ("22", "Outpatient Hospital", 0.20),
    ("23", "Emergency Room", 0.10),
    ("24", "Ambulatory Surgical Center", 0.05),
    ("21", "Inpatient Hospital", 0.03),
    ("13", "Critical Access Hospital", 0.02),
]

# ============================================================================
# MODIFIERS
# ============================================================================

MODIFIERS = [
    ("25", "Significant, separately identifiable evaluation and management service", 0.15),
    ("59", "Distinct procedural service", 0.10),
    ("26", "Professional component", 0.08),
    ("TC", "Technical component", 0.05),
    ("LT", "Left side", 0.05),
    ("RT", "Right side", 0.05),
    ("50", "Bilateral procedure", 0.03),
    ("51", "Multiple procedures", 0.08),
    ("52", "Reduced services", 0.02),
    ("76", "Repeat procedure by same physician", 0.03),
    ("77", "Repeat procedure by another physician", 0.02),
]

# ============================================================================
# REVENUE CODES
# ============================================================================

REVENUE_CODES = [
    ("0250", "Pharmacy", 0.05),
    ("0270", "Medical/Surgical Supplies", 0.08),
    ("0300", "Laboratory", 0.15),
    ("0320", "Laboratory - Pathology", 0.10),
    ("0400", "Radiology - Diagnostic", 0.20),
    ("0420", "Radiology - Therapeutic", 0.05),
    ("0450", "CT Scan", 0.15),
    ("0470", "MRI", 0.10),
    ("0510", "Emergency Room", 0.12),
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_business_day(date: datetime, days_back: int = 0) -> datetime:
    """
    Get a business day (Monday-Friday).
    
    Args:
        date: Starting date
        days_back: Number of business days to go back (default: 0)
        
    Returns:
        A datetime object representing a business day
    """
    target = date - timedelta(days=days_back)
    while target.weekday() >= 5:  # Saturday = 5, Sunday = 6
        target -= timedelta(days=1)
    return target


def weighted_choice(choices: List[Tuple], weights: Optional[List[float]] = None) -> Tuple:
    """
    Select from choices based on weights.
    
    Args:
        choices: List of tuples to choose from
        weights: Optional list of weights corresponding to choices. If None, uniform random selection is used.
        
    Returns:
        A randomly selected tuple from choices, weighted by weights if provided
    """
    if weights is None:
        return random.choice(choices)
    return random.choices(choices, weights=weights, k=1)[0]


def select_cpt_by_specialty(specialty: str) -> Tuple:
    """
    Select CPT code appropriate for specialty.
    
    Args:
        specialty: Medical specialty name (e.g., "primary_care", "cardiology")
        
    Returns:
        Tuple of (cpt_code, description, min_charge, max_charge)
        
    Raises:
        KeyError: If specialty not found and no fallback available
    """
    specialty_codes = CPT_BY_SPECIALTY.get(specialty)
    if specialty_codes is None:
        # Fallback to primary_care, but handle KeyError if it doesn't exist
        specialty_codes = CPT_BY_SPECIALTY.get("primary_care")
        if specialty_codes is None:
            # Last resort: use first available specialty
            if not CPT_BY_SPECIALTY:
                raise KeyError("No CPT codes available in CPT_BY_SPECIALTY")
            specialty_codes = next(iter(CPT_BY_SPECIALTY.values()))
            logger.warning(
                "Specialty not found, using fallback",
                requested_specialty=specialty,
                fallback_specialty="first_available",
            )
        else:
            logger.warning(
                "Specialty not found, using primary_care",
                requested_specialty=specialty,
            )
    
    if not specialty_codes:
        raise ValueError(f"No CPT codes available for specialty: {specialty}")
    
    code, desc, min_charge, max_charge, freq = weighted_choice(specialty_codes, [c[4] for c in specialty_codes])
    return code, desc, min_charge, max_charge


def select_diagnosis_by_category(category: Optional[str] = None) -> str:
    """
    Select diagnosis code from a category or weighted random selection.
    
    Args:
        category: Optional diagnosis category name. If None, selects from weighted distribution.
        
    Returns:
        ICD-10 diagnosis code string
        
    Raises:
        KeyError: If category not found and no fallback available
        ValueError: If no diagnosis codes available
    """
    if category:
        diagnosis_codes = DIAGNOSIS_BY_CATEGORY.get(category)
        if diagnosis_codes is None:
            logger.warning(
                "Diagnosis category not found, using all codes",
                requested_category=category,
            )
            diagnosis_codes = ALL_DIAGNOSIS_CODES
        if not diagnosis_codes:
            raise ValueError(f"No diagnosis codes available for category: {category}")
        return random.choice(diagnosis_codes)
    
    # Weight by category frequency
    categories = list(DIAGNOSIS_BY_CATEGORY.keys())
    if not categories:
        if not ALL_DIAGNOSIS_CODES:
            raise ValueError("No diagnosis codes available")
        return random.choice(ALL_DIAGNOSIS_CODES)
    
    category_weights = [0.20, 0.15, 0.12, 0.10, 0.10, 0.08, 0.08, 0.05, 0.05, 0.04, 0.02, 0.01]
    # Adjust weights to match number of categories
    if len(category_weights) > len(categories):
        category_weights = category_weights[:len(categories)]
    elif len(category_weights) < len(categories):
        # Extend with uniform weights
        remaining = len(categories) - len(category_weights)
        category_weights.extend([0.01] * remaining)
    
    selected_category = weighted_choice(
        [(cat, w) for cat, w in zip(categories, category_weights)],
        category_weights
    )
    selected_category_name = selected_category[0]
    
    diagnosis_codes = DIAGNOSIS_BY_CATEGORY.get(selected_category_name)
    if diagnosis_codes is None or not diagnosis_codes:
        # Fallback to all codes
        logger.warning(
            "Selected category has no codes, using all codes",
            selected_category=selected_category_name,
        )
        if not ALL_DIAGNOSIS_CODES:
            raise ValueError("No diagnosis codes available")
        return random.choice(ALL_DIAGNOSIS_CODES)
    
    return random.choice(diagnosis_codes)


def generate_patient_demographics(patient_idx: int) -> Dict:
    """Generate realistic patient demographics."""
    first_names = [
        "JOHN", "MARY", "ROBERT", "SARAH", "MICHAEL", "JENNIFER", "DAVID", "LISA",
        "JAMES", "PATRICIA", "WILLIAM", "LINDA", "RICHARD", "BARBARA", "JOSEPH", "ELIZABETH",
        "THOMAS", "SUSAN", "CHARLES", "JESSICA", "CHRISTOPHER", "KAREN", "DANIEL", "NANCY",
        "MATTHEW", "BETTY", "ANTHONY", "MARGARET", "MARK", "SANDRA", "DONALD", "ASHLEY",
    ]
    last_names = [
        "SMITH", "JOHNSON", "WILLIAMS", "BROWN", "JONES", "GARCIA", "MILLER", "DAVIS",
        "RODRIGUEZ", "MARTINEZ", "HERNANDEZ", "LOPEZ", "WILSON", "ANDERSON", "THOMAS", "TAYLOR",
        "MOORE", "JACKSON", "MARTIN", "LEE", "THOMPSON", "WHITE", "HARRIS", "SANCHEZ",
        "CLARK", "RAMIREZ", "LEWIS", "ROBINSON", "WALKER", "YOUNG", "ALLEN", "KING",
    ]
    
    first_name = random.choice(first_names)
    last_name = random.choice(last_names)
    middle_initial = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    gender = random.choice(["M", "F"])
    
    # Age distribution: more middle-aged and elderly
    age_weights = [(20, 0.05), (30, 0.15), (40, 0.20), (50, 0.25), (60, 0.20), (70, 0.10), (80, 0.05)]
    age_tuple = weighted_choice(age_weights, [w for _, w in age_weights])
    age = age_tuple[0]  # Extract age from tuple (age, weight)
    birth_year = datetime.now().year - age
    birth_date = f"{birth_year}0101"
    
    return {
        "first_name": first_name,
        "last_name": last_name,
        "middle_initial": middle_initial,
        "gender": gender,
        "birth_date": birth_date,
        "patient_num": f"PAT{patient_idx:06d}",
    }


def generate_837_header(
    sender_id: str = "MEDPRACTICE001",
    receiver_id: str = "CLEARINGHOUSE",
    transaction_date: datetime = None,
) -> str:
    """Generate ISA/GS/ST header for 837 file."""
    if transaction_date is None:
        transaction_date = datetime.now()
    
    date_str = transaction_date.strftime("%y%m%d")
    time_str = transaction_date.strftime("%H%M")
    full_date = transaction_date.strftime("%Y%m%d")
    
    return f"""ISA*00*          *00*          *ZZ*{sender_id:<15}*ZZ*{receiver_id:<15}*{date_str}*{time_str}*^*00501*000000001*0*P*:~
GS*HC*{sender_id}*{receiver_id}*{date_str}*{time_str}*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*{random.randint(1000000000, 9999999999)}*{date_str}*{time_str}*CH~
NM1*41*2*SAMPLE MEDICAL PRACTICE*****46*1234567890~
PER*IC*CONTACT NAME*TE*5551234567~
NM1*40*2*BLUE CROSS BLUE SHIELD*****46*BLUE_CROSS~
HL*1**20*1~
PRV*BI*PXC*207RI0001X~
NM1*85*2*DR JOHN SMITH*****XX*{random.choice(PROVIDER_NPIS)}~
N3*123 MAIN ST~
N4*CITY*NY*10001~
REF*EI*123456789~
NM1*87*2~
N3*456 PATIENT ST~
N4*PATIENT CITY*NY*10002~"""


def generate_837_claim(
    claim_idx: int,
    patient_idx: int,
    service_date: datetime,
    payer_config: Dict,
    specialty: str = "primary_care",
) -> Tuple[str, Dict]:
    """Generate a realistic 837 claim with multiple service lines."""
    claim_num = f"CLAIM{claim_idx:06d}"
    
    # Generate patient demographics
    patient = generate_patient_demographics(patient_idx)
    
    # Select facility type
    facility_code, facility_name, _ = weighted_choice(FACILITY_TYPES, [w for _, _, w in FACILITY_TYPES])
    
    # Determine number of service lines (1-5, weighted toward 1-3)
    num_lines = random.choices([1, 2, 3, 4, 5], weights=[0.40, 0.30, 0.15, 0.10, 0.05], k=1)[0]
    
    # Generate service lines
    service_lines = []
    total_charge = 0.0
    cpt_codes_used = []
    diagnoses_used = []
    
    # Primary diagnosis
    primary_diagnosis = select_diagnosis_by_category()
    diagnoses_used.append(primary_diagnosis)
    
    # Additional diagnoses (0-3)
    num_additional_dx = random.choices([0, 1, 2, 3], weights=[0.50, 0.30, 0.15, 0.05], k=1)[0]
    for _ in range(num_additional_dx):
        diagnoses_used.append(select_diagnosis_by_category())
    
    for line_num in range(1, num_lines + 1):
        # Select CPT code
        cpt_code, cpt_desc, min_charge, max_charge = select_cpt_by_specialty(specialty)
        charge_amount = random.uniform(min_charge, max_charge)
        total_charge += charge_amount
        cpt_codes_used.append(cpt_code)
        
        # Add modifier (30% chance)
        modifier = None
        if random.random() < 0.30:
            mod_code, mod_desc, mod_freq = weighted_choice(MODIFIERS, [m[2] for m in MODIFIERS])
            modifier = mod_code
        
        # Add revenue code for hospital-based services (20% chance)
        revenue_code = None
        if facility_code in ["22", "23", "24", "21"] and random.random() < 0.20:
            rev_code, rev_desc, rev_freq = weighted_choice(REVENUE_CODES, [r[2] for r in REVENUE_CODES])
            revenue_code = rev_code
        
        service_date_str = service_date.strftime("%Y%m%d")
        
        # Build service line
        sv1_line = f"SV1*HC:{cpt_code}"
        if modifier:
            sv1_line += f":{modifier}"
        sv1_line += f"*{charge_amount:.2f}*UN*1"
        if revenue_code:
            sv1_line += f"*{revenue_code}"
        sv1_line += "**1~"
        
        service_lines.append({
            "line_num": line_num,
            "cpt_code": cpt_code,
            "modifier": modifier,
            "charge_amount": charge_amount,
            "revenue_code": revenue_code,
            "sv1_segment": sv1_line,
        })
    
    # Build claim segments
    service_date_str = service_date.strftime("%Y%m%d")
    statement_date = service_date  # Usually same as service date for professional claims
    
    # Safely get payer information with defaults
    payer_name = payer_config.get("name", "UNKNOWN PAYER")
    payer_id = payer_config.get("id", "UNKNOWN")
    
    claim_content = f"""HL*{claim_idx}*1*22*0~
SBR*P*18*GROUP{random.randint(100, 999):03d}******CI~
NM1*IL*1*{patient['last_name']}*{patient['first_name']}*{patient['middle_initial']}***MI*{patient['patient_num']}~
DMG*D8*{patient['birth_date']}*{patient['gender']}~
NM1*PR*2*{payer_name}*****PI*{payer_id}~
CLM*{claim_num}*{total_charge:.2f}***11:A:1*Y*A*Y*I~
DTP*431*D8*{statement_date.strftime('%Y%m%d')}~
DTP*484*D8*{statement_date.strftime('%Y%m%d')}~
REF*D9*{patient['patient_num']}~"""
    
    # Add diagnosis codes
    hi_parts = [f"HI*ABK:I10*{primary_diagnosis}"]
    hi_parts.extend(f"*ABF:I10*{dx}" for dx in diagnoses_used[1:])
    hi_segment = "".join(hi_parts) + "~"
    claim_content += hi_segment
    
    # Add service lines
    service_line_parts = ["LX*1~"]
    for line in service_lines:
        service_line_parts.append(line["sv1_segment"])
        service_line_parts.append(f"\nDTM*472*D8*{service_date_str}~")
    claim_content += "".join(service_line_parts)
    
    metadata = {
        "claim_num": claim_num,
        "patient_num": patient.get("patient_num", ""),
        "total_charge": total_charge,
        "cpt_codes": cpt_codes_used,
        "diagnoses": diagnoses_used,
        "primary_diagnosis": primary_diagnosis,
        "payer_id": payer_config.get("id", ""),
        "payer_name": payer_config.get("name", ""),
        "service_date": service_date_str,
        "facility_code": facility_code,
        "num_service_lines": num_lines,
        "service_lines": service_lines,
    }
    
    return claim_content, metadata


def generate_835_header(
    sender_id: str = "BCBSILPAYER",
    receiver_id: str = "MEDPRACTICE001",
    payment_date: datetime = None,
    total_amount: float = None,
) -> str:
    """Generate ISA/GS/ST header for 835 file."""
    if payment_date is None:
        payment_date = datetime.now()
    if total_amount is None:
        total_amount = random.uniform(10000.0, 100000.0)
    
    date_str = payment_date.strftime("%y%m%d")
    time_str = payment_date.strftime("%H%M%S")
    full_date = payment_date.strftime("%Y%m%d")
    
    check_num = f"CHK{random.randint(100000, 999999)}"
    trace_num = random.randint(100000000, 999999999)
    ref_num = random.randint(100000000, 999999999)
    
    return f"""ISA*00*          *00*          *ZZ*{sender_id:<15}*ZZ*{receiver_id:<15}*{date_str}*{time_str}*^*00501*000000001*0*P*:~
GS*HP*{sender_id}*{receiver_id}*{date_str}*{time_str}*1*X*005010X221A1~
ST*835*0001*005010X221A1~
BPR*I*{total_amount:.2f}*C*{check_num}*{full_date}*{trace_num}*01*{ref_num}*DA*{random.randint(1000000000, 9999999999)}*{full_date}~
TRN*1*REM{date_str}001*{trace_num}~
REF*EV*REM{date_str}001~
DTM*405*{full_date}~
DTM*097*{full_date}*{full_date}~
N1*PR*BLUE CROSS BLUE SHIELD OF ILLINOIS~
N3*300 EAST RANDOLPH STREET~
N4*CHICAGO*IL*60601~
PER*BL*CLAIMS DEPARTMENT*TE*8005551234*FX*8005555678~"""


def generate_835_remittance(
    remit_idx: int,
    claim_metadata: Dict,
    payment_date: datetime,
    payer_config: Dict,
    outcome: str = "paid",
) -> Tuple[str, Dict]:
    """Generate a realistic 835 remittance with proper denial codes and adjustments."""
    # Validate required keys in claim_metadata
    required_keys = ["claim_num", "patient_num", "total_charge", "service_date", "service_lines"]
    for key in required_keys:
        if key not in claim_metadata:
            raise KeyError(f"Missing required key '{key}' in claim_metadata")
    
    claim_num = claim_metadata["claim_num"]
    patient_num = claim_metadata["patient_num"]
    total_charge = claim_metadata["total_charge"]
    service_date_str = claim_metadata["service_date"]
    service_lines = claim_metadata["service_lines"]
    
    payment_date_str = payment_date.strftime("%Y%m%d")
    
    # Determine payment scenario based on outcome and payer
    # Validate and get required keys from payer_config with defaults
    common_denials = payer_config.get("common_denials", ["CO50", "CO96"])
    payment_rate_default = payer_config.get("payment_rate", 0.80)
    
    if outcome == "denied":
        claim_status = "4"  # Denied
        paid_amount = 0.0
        patient_responsibility = 0.0
        if not common_denials:
            # Fallback to default denial codes
            common_denials = ["CO50", "CO96"]
        denial_reasons = [random.choice(common_denials)] if common_denials else ["CO50"]
        adjustments = []
        
        # Add full denial adjustment
        denial_code = denial_reasons[0]
        if len(denial_code) < 4:
            logger.warning(
                "Invalid denial code format, using default",
                denial_code=denial_code,
            )
            group_code = "CO"
            reason_code = "50"
        else:
            group_code = denial_code[:2]
            reason_code = denial_code[2:]
        adjustments.append({
            "group_code": group_code,
            "reason_code": reason_code,
            "amount": -total_charge,
        })
        
    elif outcome == "partial":
        claim_status = "1"  # Processed
        # Partial payment (30-70% of charge)
        payment_rate = random.uniform(0.30, 0.70)
        paid_amount = total_charge * payment_rate
        patient_responsibility = total_charge - paid_amount
        denial_reasons = []
        adjustments = []
        
        # Contractual adjustment
        co_amount = total_charge * random.uniform(0.10, 0.25)
        adjustments.append({
            "group_code": "CO",
            "reason_code": "45",
            "amount": -co_amount,
        })
        
        # Patient responsibility
        deductible = patient_responsibility * random.uniform(0.30, 0.50)
        coinsurance = patient_responsibility - deductible
        if deductible > 0:
            adjustments.append({
                "group_code": "PR",
                "reason_code": "1",
                "amount": -deductible,
            })
        if coinsurance > 0:
            adjustments.append({
                "group_code": "PR",
                "reason_code": "2",
                "amount": -coinsurance,
            })
        
    elif outcome == "adjusted":
        claim_status = "1"  # Processed
        # Adjusted payment (70-90% of charge)
        payment_rate = random.uniform(0.70, 0.90)
        paid_amount = total_charge * payment_rate
        patient_responsibility = total_charge - paid_amount
        denial_reasons = []
        adjustments = []
        
        # Multiple adjustments
        adjustments.append({
            "group_code": "CO",
            "reason_code": "45",
            "amount": -total_charge * 0.10,
        })
        adjustments.append({
            "group_code": "PR",
            "reason_code": "1",
            "amount": -total_charge * 0.05,
        })
        adjustments.append({
            "group_code": "PR",
            "reason_code": "2",
            "amount": -total_charge * 0.10,
        })
        
        # Sometimes add OA adjustment
        if random.random() < 0.20:
            adjustments.append({
                "group_code": "OA",
                "reason_code": "23",
                "amount": -total_charge * random.uniform(0.02, 0.05),
            })
        
    else:  # paid
        claim_status = "1"  # Processed
        # Full or near-full payment (80-95% of charge)
        payment_rate = random.uniform(payment_rate_default - 0.05, payment_rate_default + 0.05)
        paid_amount = total_charge * payment_rate
        patient_responsibility = total_charge - paid_amount
        denial_reasons = []
        adjustments = []
        
        # Standard patient responsibility
        if patient_responsibility > 0:
            deductible = patient_responsibility * random.uniform(0.40, 0.60)
            coinsurance = patient_responsibility - deductible
            if deductible > 0:
                adjustments.append({
                    "group_code": "PR",
                    "reason_code": "1",
                    "amount": -deductible,
                })
            if coinsurance > 0:
                adjustments.append({
                    "group_code": "PR",
                    "reason_code": "2",
                    "amount": -coinsurance,
                })
        
        # Small contractual adjustment
        if random.random() < 0.30:
            adjustments.append({
                "group_code": "CO",
                "reason_code": "45",
                "amount": -total_charge * random.uniform(0.02, 0.08),
            })
    
    # Generate remittance content
    remit_content = f"""LX*{remit_idx}~
CLP*{claim_num}*{claim_status}*{total_charge:.2f}*{paid_amount:.2f}*{patient_responsibility:.2f}*11*{patient_num}*{service_date_str}*1~"""
    
    # Add claim-level adjustments (CAS segments)
    for adj in adjustments:
        remit_content += f"""
CAS*{adj['group_code']}*{adj['reason_code']}*{abs(adj['amount']):.2f}~"""
    
    # Add patient and provider info
    remit_content += f"""
NM1*QC*1*PATIENT*JOHN*M***MI*{patient_num}~
NM1*82*1*PROVIDER*JANE*M***XX*{random.choice(PROVIDER_NPIS)}~
REF*D9*{patient_num}~
REF*1W*{patient_num}~"""
    
    # Add amounts
    if patient_responsibility > 0:
        remit_content += f"""
AMT*AU*{patient_responsibility:.2f}~
AMT*D*{patient_responsibility * 0.3:.2f}~
AMT*F5*{patient_responsibility * 0.7:.2f}~"""
    
    # Add service lines with line-level adjustments
    for line_idx, line in enumerate(service_lines, 1):
        # Safely get line values with defaults
        line_charge = line.get("charge_amount", 0.0)
        line_cpt_code = line.get("cpt_code", "UNKNOWN")
        if not line_charge or not line_cpt_code:
            logger.warning(
                "Missing required line data, skipping line",
                line_index=line_idx,
                line_keys=list(line.keys()),
            )
            continue
        
        line_paid = (paid_amount / total_charge) * line_charge if total_charge > 0 else 0.0
        
        remit_content += f"""
SVC*HC:{line_cpt_code}*{line_charge:.2f}*{line_paid:.2f}*UN*1~
DTM*472*D8*{service_date_str}~"""
        
        # Add line-level adjustments (subset of claim adjustments)
        for adj in adjustments[:min(2, len(adjustments))]:
            # Safely get adjustment values
            adj_amount = adj.get("amount", 0.0)
            adj_group_code = adj.get("group_code", "CO")
            adj_reason_code = adj.get("reason_code", "50")
            
            line_adj_amount = abs(adj_amount) * (line_charge / total_charge) if total_charge > 0 else 0.0
            if line_adj_amount > 0.01:
                remit_content += f"""
CAS*{adj_group_code}*{adj_reason_code}*{line_adj_amount:.2f}~"""
    
    metadata = {
        "claim_num": claim_num,
        "paid_amount": paid_amount,
        "denial_reasons": denial_reasons,
        "adjustments": adjustments,
        "outcome": outcome,
        "payment_rate": paid_amount / total_charge if total_charge > 0 else 0.0,
    }
    
    return remit_content, metadata


def generate_training_dataset(
    num_episodes: int = 500,
    output_dir: Path = Path("samples/training"),
    start_date: datetime = None,
    denial_rate: float = 0.25,
    claims_filename: str = "training_837_claims.edi",
    remittances_filename: str = "training_835_remittances.edi",
    metadata_filename: str = "training_metadata.json",
) -> None:
    """
    Generate a complete training dataset with linked 837 and 835 files.
    
    Args:
        num_episodes: Number of claim/remittance pairs to generate
        output_dir: Output directory for generated files
        start_date: Start date for claims (default: 6 months ago)
        denial_rate: Percentage of claims that should be denied (0.0-1.0)
        claims_filename: Filename for 837 claims file
        remittances_filename: Filename for 835 remittances file
        metadata_filename: Filename for metadata JSON file
    """
    if start_date is None:
        start_date = datetime.now() - timedelta(days=180)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(
        "Generating training dataset",
        num_episodes=num_episodes,
        output_dir=str(output_dir),
        denial_rate=denial_rate,
    )
    
    # Determine outcomes for each episode
    outcomes = []
    num_denied = int(num_episodes * denial_rate)
    num_partial = int(num_episodes * 0.15)
    num_adjusted = int(num_episodes * 0.10)
    num_paid = num_episodes - num_denied - num_partial - num_adjusted
    
    outcomes.extend(["denied"] * num_denied)
    outcomes.extend(["partial"] * num_partial)
    outcomes.extend(["adjusted"] * num_adjusted)
    outcomes.extend(["paid"] * num_paid)
    random.shuffle(outcomes)
    
    # Generate 837 file
    logger.info("Generating 837 claims file...")
    transaction_date = get_business_day(datetime.now())
    claims_content = generate_837_header(transaction_date=transaction_date)
    claims_segments = len(claims_content.split("~")) - 1
    
    claims_metadata = []
    specialties_used = defaultdict(int)
    
    for i in range(num_episodes):
        # Vary service dates over 6 months (business days preferred)
        days_offset = random.randint(0, 180)
        service_date = get_business_day(start_date + timedelta(days=days_offset), days_back=random.randint(0, 5))
        
        # Select payer (weighted)
        payer_config = random.choice(PAYERS)
        
        # Select specialty (weighted)
        specialties = list(SPECIALTY_WEIGHTS.keys())
        weights = list(SPECIALTY_WEIGHTS.values())
        specialty = weighted_choice(
            [(s, w) for s, w in zip(specialties, weights)],
            weights
        )[0]
        specialties_used[specialty] += 1
        
        claim_content, claim_meta = generate_837_claim(
            i + 2,  # Start at 2 (HL*1 is in header)
            i % 10000,  # Cycle through patients
            service_date,
            payer_config,
            specialty,
        )
        
        claims_content += claim_content
        claims_metadata.append(claim_meta)
        claims_segments += len(claim_content.split("~")) - 1
    
    # Add footer
    claims_segments += 3  # SE/GE/IEA
    claims_footer = f"""SE*{claims_segments}*0001~
GE*1*1~
IEA*1*000000001~"""
    claims_content += claims_footer
    
    # Write 837 file (use configurable path)
    claims_file = output_dir / claims_filename
    try:
        with open(claims_file, "w", encoding="utf-8") as f:
            f.write(claims_content)
        logger.info(f"Generated 837 file: {claims_file} ({num_episodes} claims)")
    except (IOError, OSError) as e:
        logger.error("Failed to write 837 file", file=str(claims_file), error=str(e))
        raise
    
    # Generate 835 file
    logger.info("Generating 835 remittances file...")
    payment_date = get_business_day(datetime.now() - timedelta(days=30))
    
    # Calculate total payment amount
    total_payment = sum(
        claim_meta.get("total_charge", 0.0) * random.uniform(0.7, 0.9)
        for claim_meta in claims_metadata
    )
    
    remittances_content = generate_835_header(payment_date=payment_date, total_amount=total_payment)
    remittances_segments = len(remittances_content.split("~")) - 1
    
    remittances_metadata = []
    
    for i, (claim_meta, outcome) in enumerate(zip(claims_metadata, outcomes)):
        # Validate and get required keys from claim_meta with defaults
        service_date_str = claim_meta.get("service_date")
        if not service_date_str:
            logger.error(
                "Missing service_date in claim metadata",
                claim_index=i,
                available_keys=list(claim_meta.keys()),
            )
            raise KeyError(f"Missing required key 'service_date' in claim_meta at index {i}")
        
        # Payment date is typically 30-60 days after service
        try:
            service_date = datetime.strptime(service_date_str, "%Y%m%d")
        except ValueError as e:
            logger.error(
                "Invalid service_date format in claim metadata",
                claim_index=i,
                service_date=service_date_str,
                error=str(e),
            )
            raise ValueError(f"Invalid service_date format '{service_date_str}' in claim_meta at index {i}: {e}")
        
        payment_date_episode = get_business_day(
            service_date + timedelta(days=random.randint(30, 60)),
            days_back=random.randint(0, 3)
        )
        
        # Get payer config for this claim
        payer_id = claim_meta.get("payer_id")
        if not payer_id:
            logger.warning("Missing payer_id in claim metadata, using default", claim_index=i)
            if not PAYERS:
                raise ValueError("No payers available in PAYERS configuration")
            payer_config = PAYERS[0]
        else:
            if not PAYERS:
                raise ValueError("No payers available in PAYERS configuration")
            payer_config = next((p for p in PAYERS if p.get("id") == payer_id), PAYERS[0])
        
        remit_content, remit_meta = generate_835_remittance(
            i + 1,
            claim_meta,
            payment_date_episode,
            payer_config,
            outcome,
        )
        
        remittances_content += remit_content
        remittances_metadata.append(remit_meta)
        remittances_segments += len(remit_content.split("~")) - 1
    
    # Add footer
    remittances_segments += 3  # SE/GE/IEA
    remittances_footer = f"""SE*{remittances_segments}*0001~
GE*1*1~
IEA*1*000000001~"""
    remittances_content += remittances_footer
    
    # Write 835 file (use configurable path)
    remittances_file = output_dir / remittances_filename
    try:
        with open(remittances_file, "w", encoding="utf-8") as f:
            f.write(remittances_content)
        logger.info(f"Generated 835 file: {remittances_file} ({num_episodes} remittances)")
    except (IOError, OSError) as e:
        logger.error("Failed to write 835 file", file=str(remittances_file), error=str(e))
        raise
    
    # Generate metadata file (use configurable path)
    metadata_file = output_dir / metadata_filename
    metadata = {
        "num_episodes": num_episodes,
        "denial_rate": denial_rate,
        "outcomes": {
            "denied": num_denied,
            "partial": num_partial,
            "adjusted": num_adjusted,
            "paid": num_paid,
        },
        "specialties": dict(specialties_used),
        "claims_file": str(claims_file),
        "remittances_file": str(remittances_file),
        "generated_at": datetime.now().isoformat(),
    }
    
    try:
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Generated metadata file: {metadata_file}")
    except (IOError, OSError) as e:
        logger.error("Failed to write metadata file", file=str(metadata_file), error=str(e))
        raise
    
    # Print summary
    print("\n" + "=" * 70)
    print("TRAINING DATA GENERATION COMPLETE")
    print("=" * 70)
    print(f"\nGenerated Files:")
    print(f"  837 Claims:      {claims_file}")
    print(f"  835 Remittances: {remittances_file}")
    print(f"  Metadata:       {metadata_file}")
    print(f"\nDataset Statistics:")
    print(f"  Total Episodes: {num_episodes}")
    print(f"  Denied:         {num_denied} ({num_denied/num_episodes*100:.1f}%)")
    print(f"  Partial:        {num_partial} ({num_partial/num_episodes*100:.1f}%)")
    print(f"  Adjusted:       {num_adjusted} ({num_adjusted/num_episodes*100:.1f}%)")
    print(f"  Paid:           {num_paid} ({num_paid/num_episodes*100:.1f}%)")
    print(f"\nSpecialty Distribution:")
    for specialty, count in sorted(specialties_used.items(), key=lambda x: x[1], reverse=True):
        print(f"  {specialty:20s}: {count:4d} ({count/num_episodes*100:5.1f}%)")
    print(f"\nNext Steps:")
    print(f"  1. Upload 837: curl -X POST http://localhost:8000/api/v1/claims/upload -F 'file=@{claims_file}'")
    print(f"  2. Upload 835: curl -X POST http://localhost:8000/api/v1/remits/upload -F 'file=@{remittances_file}'")
    print(f"  3. Check data: python ml/training/check_historical_data.py")
    print(f"  4. Train model: python ml/training/train_models.py")
    print("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate production-quality synthetic training data for ML models"
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=500,
        help="Number of claim/remittance pairs to generate (default: 500)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("samples/training"),
        help="Output directory (default: samples/training)",
    )
    parser.add_argument(
        "--denial-rate",
        type=float,
        default=0.25,
        help="Percentage of claims that should be denied (0.0-1.0, default: 0.25)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date for claims (YYYY-MM-DD, default: 6 months ago)",
    )
    parser.add_argument(
        "--claims-filename",
        type=str,
        default="training_837_claims.edi",
        help="Filename for 837 claims file (default: training_837_claims.edi)",
    )
    parser.add_argument(
        "--remittances-filename",
        type=str,
        default="training_835_remittances.edi",
        help="Filename for 835 remittances file (default: training_835_remittances.edi)",
    )
    parser.add_argument(
        "--metadata-filename",
        type=str,
        default="training_metadata.json",
        help="Filename for metadata JSON file (default: training_metadata.json)",
    )
    
    args = parser.parse_args()
    
    # Validate denial-rate argument
    if not isinstance(args.denial_rate, (int, float)):
        parser.error(f"--denial-rate must be a number, got: {type(args.denial_rate).__name__}")
    if args.denial_rate < 0.0 or args.denial_rate > 1.0:
        parser.error(f"--denial-rate must be between 0.0 and 1.0, got: {args.denial_rate}")
    
    # Validate episodes argument
    if not isinstance(args.episodes, int):
        parser.error(f"--episodes must be an integer, got: {type(args.episodes).__name__}")
    if args.episodes < 1:
        parser.error(f"--episodes must be at least 1, got: {args.episodes}")
    if args.episodes > 1000000:
        parser.error(f"--episodes must be at most 1,000,000, got: {args.episodes}")
    
    # Validate output directory
    if args.output_dir.exists() and not args.output_dir.is_dir():
        parser.error(f"--output-dir must be a directory, got: {args.output_dir}")
    
    # Validate filenames
    if not args.claims_filename or not args.claims_filename.strip():
        parser.error("--claims-filename cannot be empty")
    if not args.remittances_filename or not args.remittances_filename.strip():
        parser.error("--remittances-filename cannot be empty")
    if not args.metadata_filename or not args.metadata_filename.strip():
        parser.error("--metadata-filename cannot be empty")
    
    # Validate filename characters (basic sanitization)
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
    for filename in [args.claims_filename, args.remittances_filename, args.metadata_filename]:
        if any(char in filename for char in invalid_chars):
            parser.error(f"Filename contains invalid characters: {filename}")
    
    start_date = None
    if args.start_date:
        try:
            start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
        except ValueError as e:
            parser.error(f"--start-date must be in YYYY-MM-DD format, got: {args.start_date} (error: {e})")
    
    generate_training_dataset(
        num_episodes=args.episodes,
        output_dir=args.output_dir,
        start_date=start_date,
        denial_rate=args.denial_rate,
        claims_filename=args.claims_filename,
        remittances_filename=args.remittances_filename,
        metadata_filename=args.metadata_filename,
    )


if __name__ == "__main__":
    main()
