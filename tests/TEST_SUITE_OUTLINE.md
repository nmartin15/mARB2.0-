# Comprehensive Test Suite Outline

## Overview

This document outlines a comprehensive test suite for mARB 2.0 that covers EDI parsing, plan design rules, risk scoring, episode linking, and HIPAA compliance.

## Test Categories

### 1. EDI Parser Tests (`test_edi_parser.py`)

#### 1.1 837 Claim File Parsing
- [ ] **Basic 837 Parsing**
  - Parse simple 837 file with single claim
  - Parse 837 file with multiple claims
  - Verify all required segments are extracted
  - Verify claim control numbers are unique

- [ ] **Segment Extraction**
  - Extract ISA/GS/ST envelope segments
  - Extract CLM (claim) segments
  - Extract SBR (subscriber) segments
  - Extract NM1 (name) segments for patient/provider/payer
  - Extract HI (diagnosis) segments
  - Extract SV1/SV2 (service line) segments
  - Extract DTP (date) segments
  - Extract REF (reference) segments

- [ ] **Missing Segment Handling**
  - Handle missing optional segments gracefully
  - Log warnings for missing important segments
  - Continue parsing when non-critical segments missing
  - Mark claims as incomplete when critical segments missing

- [ ] **Data Validation**
  - Validate date formats (D8, D6, etc.)
  - Validate numeric amounts
  - Validate diagnosis code formats (ICD-10)
  - Validate CPT code formats
  - Validate NPI formats

- [ ] **Edge Cases**
  - Empty file
  - File with only envelope segments
  - File with malformed segments
  - File with invalid delimiters
  - File with special characters
  - Very large files (1000+ claims)
  - Files with duplicate claim control numbers

#### 1.2 835 Remittance File Parsing
- [ ] **Basic 835 Parsing**
  - Parse simple 835 file with single remittance
  - Parse 835 file with multiple remittances
  - Verify all required segments are extracted
  - Verify remittance control numbers

- [ ] **Segment Extraction**
  - Extract BPR (financial information) segment
  - Extract TRN (trace number) segment
  - Extract CLP (claim payment) segments
  - Extract CAS (claim adjustment) segments
  - Extract SVC (service payment) segments
  - Extract NM1 segments for patient/provider
  - Extract AMT (amount) segments
  - Extract DTM segments

- [ ] **Payment Scenarios**
  - Fully paid claims
  - Partially paid claims
  - Denied claims (status code 4)
  - Zero payment claims
  - Claims with multiple service lines
  - Claims with multiple adjustment codes

- [ ] **Adjustment Code Parsing**
  - Parse CO (contractual obligation) codes
  - Parse PR (patient responsibility) codes
  - Parse OA (other adjustment) codes
  - Parse multiple adjustment codes per claim
  - Parse adjustment codes at claim and service line level

- [ ] **Denial Reason Extraction**
  - Extract denial reasons from CAS segments
  - Map adjustment codes to denial reasons
  - Extract denial reason descriptions
  - Handle multiple denial reasons

- [ ] **Edge Cases**
  - Empty remittance file
  - File with no payments
  - File with all denials
  - File with malformed amounts
  - File with invalid adjustment codes

#### 1.3 Format Detection
- [ ] **Auto-Detection**
  - Detect 837 vs 835 files
  - Detect X12 version (005010X222A1, 005010X221A1)
  - Detect segment delimiters
  - Detect element delimiters

- [ ] **Format Variations**
  - Handle different X12 versions
  - Handle different segment orderings
  - Handle payer-specific variations
  - Handle practice-specific variations

#### 1.4 Error Handling
- [ ] **Invalid Files**
  - Files with invalid ISA segments
  - Files with missing IEA segments
  - Files with segment count mismatches
  - Files with invalid control numbers

- [ ] **Recovery**
  - Continue parsing after errors
  - Log all parsing errors
  - Return partial results when possible
  - Mark incomplete claims appropriately

### 2. Plan Design Rule Tests (`test_plan_design.py`)

#### 2.1 Plan Loading and Validation
- [ ] **Plan Loading**
  - Load plan design from JSON
  - Validate JSON structure
  - Store plan in database
  - Retrieve plan by payer/plan name

- [ ] **Plan Validation**
  - Validate required fields
  - Validate numeric ranges (deductibles, OOP maxes)
  - Validate date ranges (effective/termination dates)
  - Validate CPT code rules structure
  - Validate denial reason code mappings

#### 2.2 Deductible Calculation
- [ ] **Individual Deductibles**
  - Apply in-network deductible
  - Apply out-of-network deductible
  - Track deductible accumulation
  - Reset deductible at plan year

- [ ] **Family Deductibles**
  - Apply family deductible
  - Track embedded vs aggregate deductibles
  - Handle family member accumulation

- [ ] **Deductible Application**
  - Apply to correct service types
  - Skip preventive care
  - Apply after copay or before

#### 2.3 Copay Calculation
- [ ] **Service Type Copays**
  - Primary care visit copay
  - Specialist visit copay
  - Urgent care copay
  - Emergency room copay
  - Pharmacy tier copays

- [ ] **Network Copays**
  - In-network copay amounts
  - Out-of-network copay amounts
  - Apply copay after deductible or before

#### 2.4 Coinsurance Calculation
- [ ] **Coinsurance Application**
  - Calculate in-network coinsurance (20%)
  - Calculate out-of-network coinsurance (40%)
  - Apply after deductible
  - Apply to allowed amounts

- [ ] **Coinsurance Scenarios**
  - Before deductible met
  - After deductible met
  - After OOP max reached

#### 2.5 Out-of-Pocket Maximum
- [ ] **OOP Max Tracking**
  - Track individual OOP max
  - Track family OOP max
  - Include deductible, copay, coinsurance
  - Reset at plan year

- [ ] **OOP Max Application**
  - Stop patient responsibility at OOP max
  - Continue tracking after OOP max
  - Handle embedded vs aggregate OOP max

#### 2.6 Prior Authorization Rules
- [ ] **PA Requirement Detection**
  - Detect services requiring PA
  - Check CPT code PA requirements
  - Check service type PA requirements
  - Check visit count PA requirements

- [ ] **PA Validation**
  - Verify PA exists for service
  - Check PA expiration dates
  - Validate PA for specific provider
  - Handle retroactive PA

#### 2.7 Benefit Limits
- [ ] **Annual Limits**
  - Track physical therapy visit limits
  - Track mental health visit limits
  - Track chiropractic visit limits
  - Enforce limits with warnings

- [ ] **Lifetime Limits**
  - Track organ transplant limits
  - Track bariatric surgery limits
  - Prevent services exceeding limits

#### 2.8 CPT Code Rules
- [ ] **Allowed Amounts**
  - Apply in-network allowed amounts
  - Apply out-of-network allowed amounts
  - Handle missing CPT code rules
  - Use default rules when needed

- [ ] **Frequency Limits**
  - Enforce per-year frequency limits
  - Track service frequency
  - Warn when approaching limits

#### 2.9 Denial Reason Code Mapping
- [ ] **Code Mapping**
  - Map CAS codes to denial reasons
  - Retrieve denial reason descriptions
  - Determine if denial is appealable
  - Determine required actions

- [ ] **Code Categories**
  - Contractual obligation codes
  - Patient responsibility codes
  - Other adjustment codes
  - Eligibility codes

#### 2.10 Network Rules
- [ ] **In-Network Rules**
  - Apply in-network discounts
  - Apply in-network coinsurance
  - Apply in-network deductibles

- [ ] **Out-of-Network Rules**
  - Apply out-of-network rules
  - Handle balance billing
  - Apply UCR (usual, customary, reasonable)

- [ ] **Emergency Services**
  - Treat emergency as in-network
  - Apply emergency copay rules
  - Handle emergency admission waivers

### 3. Risk Scoring Tests (`test_risk_scoring.py`)

#### 3.1 Risk Score Calculation
- [ ] **Overall Risk Score**
  - Calculate overall risk score (0-100)
  - Weight component scores appropriately
  - Handle missing component data

- [ ] **Component Scores**
  - Coding risk score
  - Documentation risk score
  - Payer risk score
  - Historical risk score

- [ ] **Risk Level Assignment**
  - Assign LOW risk (0-30)
  - Assign MEDIUM risk (31-60)
  - Assign HIGH risk (61-80)
  - Assign CRITICAL risk (81-100)

#### 3.2 Coding Risk
- [ ] **Coding Validation**
  - Validate diagnosis code accuracy
  - Validate procedure code accuracy
  - Check for coding mismatches
  - Check for unsupported code combinations

- [ ] **Coding Patterns**
  - Detect upcoding patterns
  - Detect unbundling patterns
  - Detect duplicate coding
  - Detect missing modifiers

#### 3.3 Documentation Risk
- [ ] **Documentation Checks**
  - Verify required documentation exists
  - Check documentation completeness
  - Validate documentation dates
  - Check for missing signatures

- [ ] **Documentation Patterns**
  - Detect missing progress notes
  - Detect incomplete documentation
  - Detect documentation gaps

#### 3.4 Payer Risk
- [ ] **Payer-Specific Rules**
  - Apply payer denial patterns
  - Check payer-specific requirements
  - Apply payer risk multipliers
  - Check payer network status

- [ ] **Historical Payer Data**
  - Use historical denial rates
  - Use historical payment patterns
  - Apply payer-specific adjustments

#### 3.5 Historical Risk
- [ ] **Historical Patterns**
  - Analyze similar past claims
  - Detect recurring denial patterns
  - Use episode linking data
  - Apply pattern learning results

#### 3.6 Risk Factors and Recommendations
- [ ] **Risk Factor Identification**
  - Identify specific risk factors
  - Prioritize risk factors
  - Group related risk factors

- [ ] **Recommendation Generation**
  - Generate actionable recommendations
  - Prioritize recommendations
  - Link recommendations to risk factors

### 4. Episode Linking Tests (`test_episode_linking.py`)

#### 4.1 Claim-Remittance Linking
- [ ] **Basic Linking**
  - Link claim to remittance by claim control number
  - Handle exact matches
  - Handle partial matches
  - Handle multiple remittances per claim

- [ ] **Linking Algorithms**
  - Match by claim control number
  - Match by patient control number
  - Match by service dates
  - Match by amounts (fuzzy matching)

- [ ] **Linking Scenarios**
  - Single claim, single remittance
  - Single claim, multiple remittances (partial payments)
  - Multiple claims, single remittance (bundled payments)
  - Unlinked claims
  - Unlinked remittances

#### 4.2 Episode Status Tracking
- [ ] **Status Transitions**
  - PENDING → LINKED
  - LINKED → COMPLETE
  - Handle status updates
  - Prevent invalid transitions

- [ ] **Status Validation**
  - Verify claim exists
  - Verify remittance exists
  - Verify payment amounts match
  - Verify dates are consistent

#### 4.3 Payment Reconciliation
- [ ] **Payment Matching**
  - Match claim amount to payment amount
  - Handle partial payments
  - Handle overpayments
  - Handle underpayments

- [ ] **Adjustment Reconciliation**
  - Match adjustment codes
  - Reconcile denial reasons
  - Track patient responsibility
  - Track write-offs

#### 4.4 Episode Analytics
- [ ] **Episode Metrics**
  - Calculate time to payment
  - Calculate denial rate
  - Calculate payment rate
  - Calculate average payment amount

- [ ] **Pattern Detection**
  - Detect payment patterns
  - Detect denial patterns
  - Detect payer patterns
  - Detect provider patterns

### 5. Integration Tests (`test_integration.py`)

#### 5.1 End-to-End Claim Processing
- [ ] **Full Claim Lifecycle**
  - Upload 837 file
  - Parse and store claims
  - Calculate risk scores
  - Upload 835 file
  - Link episodes
  - Verify final status

- [ ] **Multi-Step Workflows**
  - Claim submission → Risk scoring → Remittance → Episode linking
  - Multiple claims in single file
  - Multiple remittances for single claim

#### 5.2 API Integration
- [ ] **Claims API Flow**
  - POST /claims/upload → GET /claims → GET /claims/{id}
  - Verify data consistency
  - Verify relationships

- [ ] **Remittances API Flow**
  - POST /remits/upload → GET /remits → GET /remits/{id}
  - Verify episode linking
  - Verify payment data

- [ ] **Risk API Flow**
  - POST /risk/{id}/calculate → GET /risk/{id}
  - Verify risk scores
  - Verify recommendations

#### 5.3 Database Integration
- [ ] **Data Persistence**
  - Verify claims are stored correctly
  - Verify remittances are stored correctly
  - Verify episodes are created
  - Verify relationships are maintained

- [ ] **Transaction Handling**
  - Test rollback on errors
  - Test commit on success
  - Test concurrent access
  - Test data integrity

#### 5.4 Celery Task Integration
- [ ] **Async Processing**
  - Test EDI file processing tasks
  - Test episode linking tasks
  - Test task retries
  - Test task failures

- [ ] **Task Status**
  - Verify task queuing
  - Verify task execution
  - Verify task completion
  - Verify error handling

### 6. Security and HIPAA Tests (`test_security.py`)

#### 6.1 Access Control
- [ ] **Authentication**
  - Require authentication for PHI access
  - Validate JWT tokens
  - Handle expired tokens
  - Handle invalid tokens

- [ ] **Authorization**
  - Verify role-based access
  - Restrict provider access to own patients
  - Restrict billing staff access
  - Verify admin access

#### 6.2 Audit Logging
- [ ] **PHI Access Logging**
  - Log all claim access
  - Log all remittance access
  - Log all patient data access
  - Include user, timestamp, IP address

- [ ] **Audit Log Validation**
  - Verify logs are created
  - Verify log completeness
  - Verify log immutability
  - Verify log retention

#### 6.3 Data Encryption
- [ ] **Encryption at Rest**
  - Verify sensitive fields are encrypted
  - Verify encryption keys are secure
  - Verify decryption works correctly

- [ ] **Encryption in Transit**
  - Require HTTPS for API calls
  - Verify TLS configuration
  - Verify certificate validation

#### 6.4 Data Masking
- [ ] **PHI Masking**
  - Mask PHI in logs
  - Mask PHI in error messages
  - Mask PHI in API responses (when appropriate)
  - Preserve PHI for authorized users

#### 6.5 Input Validation
- [ ] **SQL Injection Prevention**
  - Verify parameterized queries
  - Test SQL injection attempts
  - Verify no raw SQL with user input

- [ ] **XSS Prevention**
  - Sanitize user input
  - Escape output
  - Verify no script injection

- [ ] **File Upload Security**
  - Validate file types
  - Validate file sizes
  - Scan for malware
  - Restrict file access

### 7. Performance Tests (`test_performance.py`)

#### 7.1 Parser Performance
- [ ] **Large File Processing**
  - Process 1000+ claim file
  - Process 1000+ remittance file
  - Measure parsing time
  - Measure memory usage

- [ ] **Concurrent Processing**
  - Process multiple files simultaneously
  - Test thread safety
  - Test resource limits

#### 7.2 Database Performance
- [ ] **Query Performance**
  - Test claim queries with filters
  - Test remittance queries
  - Test episode queries
  - Verify index usage

- [ ] **Bulk Operations**
  - Test bulk claim insertion
  - Test bulk remittance insertion
  - Test bulk episode linking

#### 7.3 API Performance
- [ ] **Response Times**
  - Test endpoint response times
  - Test pagination performance
  - Test search performance
  - Set performance benchmarks

- [ ] **Load Testing**
  - Test concurrent API requests
  - Test rate limiting
  - Test system under load

### 8. Edge Cases and Error Handling (`test_edge_cases.py`)

#### 8.1 Invalid Data
- [ ] **Malformed EDI Files**
  - Missing segments
  - Invalid segment structure
  - Invalid data types
  - Invalid date formats

- [ ] **Invalid Plan Designs**
  - Missing required fields
  - Invalid numeric values
  - Invalid date ranges
  - Invalid CPT code rules

#### 8.2 Boundary Conditions
- [ ] **Numeric Boundaries**
  - Zero amounts
  - Negative amounts
  - Very large amounts
  - Decimal precision

- [ ] **Date Boundaries**
  - Past dates
  - Future dates
  - Invalid dates
  - Timezone handling

#### 8.3 Data Consistency
- [ ] **Referential Integrity**
  - Missing payer references
  - Missing provider references
  - Orphaned claims
  - Orphaned remittances

- [ ] **Data Validation**
  - Duplicate claim control numbers
  - Duplicate remittance control numbers
  - Invalid relationships
  - Data type mismatches

#### 8.4 Error Recovery
- [ ] **Partial Failures**
  - Continue processing after errors
  - Log all errors
  - Return partial results
  - Mark incomplete data

- [ ] **Retry Logic**
  - Retry failed operations
  - Exponential backoff
  - Max retry limits
  - Failure notifications

### 9. Sample File Tests (`test_sample_files.py`)

#### 9.1 835 Sample File Tests
- [ ] **File Validation**
  - Validate sample_835.txt structure
  - Verify all segments are valid
  - Verify claim count matches
  - Verify payment scenarios

- [ ] **Parsing Tests**
  - Parse sample_835.txt successfully
  - Extract all claims
  - Extract all adjustments
  - Extract all denial reasons

- [ ] **Data Verification**
  - Verify payment amounts
  - Verify adjustment codes
  - Verify patient information
  - Verify provider information

#### 9.2 Plan Design Sample Tests
- [ ] **JSON Validation**
  - Validate sample_plan_design.json structure
  - Verify all required fields
  - Verify data types
  - Verify value ranges

- [ ] **Rule Testing**
  - Test deductible calculations
  - Test copay calculations
  - Test coinsurance calculations
  - Test prior authorization rules
  - Test benefit limits
  - Test CPT code rules
  - Test denial reason mappings

- [ ] **Integration with Claims**
  - Apply plan rules to sample claims
  - Verify benefit calculations
  - Verify denial predictions
  - Verify risk scoring

## Test Implementation Priority

### Phase 1: Core Functionality (High Priority)
1. Basic 837 parsing
2. Basic 835 parsing
3. Plan design rule loading
4. Basic risk scoring
5. Basic episode linking

### Phase 2: Advanced Features (Medium Priority)
1. Format detection
2. Advanced plan rules
3. Complex risk scoring
4. Advanced episode linking
5. Integration tests

### Phase 3: Security & Performance (High Priority)
1. Security tests
2. HIPAA compliance tests
3. Performance tests
4. Load tests

### Phase 4: Edge Cases (Medium Priority)
1. Error handling
2. Boundary conditions
3. Data validation
4. Error recovery

## Test Execution Strategy

### Unit Tests
- Run on every commit
- Fast execution (< 1 second per test)
- Isolated from external dependencies
- High code coverage target (80%+)

### Integration Tests
- Run on pull requests
- May take longer (< 10 seconds per test)
- Use test database
- Mock external services

### Performance Tests
- Run nightly or on demand
- May take minutes
- Use production-like data volumes
- Set performance benchmarks

### Security Tests
- Run on every deployment
- Comprehensive coverage
- Include penetration testing
- Verify compliance

## Test Data Management

### Synthetic Data
- Use Faker for generating test data
- Use factories for database objects
- Use sample files for EDI testing
- Never use real PHI/PII

### Test Fixtures
- Create reusable test fixtures
- Use pytest fixtures for setup/teardown
- Use factories for data generation
- Clean up after tests

### Test Isolation
- Each test should be independent
- Use database transactions for isolation
- Reset state between tests
- Avoid shared state

## Coverage Goals

- **Overall Coverage**: 80%+
- **Critical Paths**: 95%+
- **EDI Parsing**: 90%+
- **Risk Scoring**: 85%+
- **Episode Linking**: 85%+
- **API Endpoints**: 90%+
- **Security**: 95%+

## Continuous Integration

### Pre-commit Hooks
- Run linters
- Run unit tests
- Check code coverage

### Pull Request Checks
- Run full test suite
- Check coverage thresholds
- Run security scans

### Deployment Checks
- Run integration tests
- Run performance tests
- Run security tests
- Verify HIPAA compliance

---

**Last Updated**: 2024-12-20
**Version**: 1.0

