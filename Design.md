# Unified Scholarship Interface (USI) - Design Document

## Executive Summary

This document outlines the comprehensive design and implementation approach for the Unified Scholarship Interface (USI) - a Frappe-based application for managing state government scholarship programs. The system streamlines discovery, application, verification, and disbursement of scholarships while improving coverage, efficiency, and transparency.

---

## 1. System Architecture

### 1.1 Technology Stack
- **Framework**: Frappe Framework v15+
- **Backend**: Python 3.10+
- **Database**: MariaDB/MySQL
- **Frontend**: Frappe's built-in UI + custom JavaScript
- **Website**: Frappe Website Framework with Jinja2 templates
- **Integration APIs**: REST APIs for external systems
- **Reporting**: Frappe Reports

### 1.2 Deployment Architecture
- **Primary**: On-premise deployment (state data centers)
- **Secondary**: Cloud deployment option
- **Multi-tenant**: Support for multiple states with isolated data

---

## 2. Core Modules

The system consists of 6 main modules:

1. **Scheme Management** - Create and manage scholarship schemes
2. **Application Management** - Process applications from submission to approval
3. **Disbursement Module** - Manage scholarship payments
4. **Candidate/Institute Management** - Manage student profiles and institute access
5. **Monitoring & Reporting Dashboard** - Analytics and reporting
6. **Grievance Redressal** - Unified ticketing system

---

## 3. DocTypes Design

### 3.1 Master Data DocTypes

#### Academic Year
- **Purpose**: Define academic years for schemes and applications
- **Key Fields**:
  - `academic_year` (Data, unique, e.g., "2024-25")
  - `start_date` (Date)
  - `end_date` (Date)
  - `is_active` (Check)

#### Department Master
- **Purpose**: Government departments managing schemes
- **Key Fields**:
  - `department_name` (Data)
  - `department_code` (Data, unique)
  - `is_active` (Check)

#### Institution Master
- **Purpose**: Educational institutions
- **Key Fields**:
  - `institution_name` (Data)
  - `aishe_code` (Data, unique)
  - `institution_type` (Select: Govt, Private, Aided)
  - `district` (Link to District)
  - `state` (Link to State)
  - `nodal_officer_name`, `nodal_officer_email`, `nodal_officer_phone`
  - `bank_account_number`, `bank_ifsc`, `bank_name`
  - `is_active` (Check)

### 3.2 Scheme Management DocTypes

#### Scholarship Scheme
- **Purpose**: Master table for all scholarship schemes
- **Key Fields**:
  - `scheme_name` (Data)
  - `scheme_code` (Data, unique)
  - `scheme_objective` (Text Editor)
  - `scheme_type` (Select: Central Govt / State Govt / Central-State)
  - `scheme_category` (Select: Merit-based, Income-based, Category-based, Minority, Special Groups, Special Category)
  - `start_date`, `end_date` (Date)
  - `financial_year` (Link to Academic Year)
  - `total_budget` (Currency)
  - `budget_department` (Link to Department Master)
  - `status` (Select: Draft, Under Review, Approved, Published, Closed, Disposed)
  - `is_multi_year` (Check)
  - `auto_renewal_enabled` (Check)

#### Scheme Eligibility Criteria
- **Purpose**: Store eligibility rules for each scheme
- **Key Fields**:
  - `scheme` (Link to Scholarship Scheme)
  - `eligibility_rule_json` (JSON) - Stores rule definition (auto-compiled)
  - `rule_version` (Data)
  - `is_active` (Check)

#### Scheme Quota Allocation
- **Purpose**: Manage quota distribution across dimensions
- **Key Fields**:
  - `scheme` (Link to Scholarship Scheme)
  - `allocation_dimension` (Select: Geographic, Demographic, Social Category, Economic, Special Category)
  - `allocation_basis` (Select: Single-Dimension, Multi-Dimension Hierarchical)
  - `quota_type` (Select: Percentage, Absolute Amount)
  - `quota_value` (Currency/Percent)
  - `geographic_level` (Select: State, Division, District, Block, Institution)
  - `demographic_criteria` (JSON)
  - `carry_forward_rule` (Select: Lapse, Redistribute)
  - `conflict_resolution` (Select: Priority Order, Best Benefit Rule)

#### Scheme Document Requirements
- **Purpose**: Define mandatory/optional documents per scheme
- **Key Fields**:
  - `scheme` (Link to Scholarship Scheme)
  - `document_type` (Select: Income Certificate, Caste Certificate, Marksheet, etc.)
  - `is_mandatory` (Check)
  - `is_conditional` (Check)
  - `condition_description` (Small Text)
  - `auto_verification_enabled` (Check)
  - `verification_source` (Select: DigiLocker, Jan Aadhaar, Manual)
  - `max_file_size_mb` (Int)
  - `allowed_file_formats` (Small Text)

### 3.3 Candidate Management DocTypes

#### Applicant
- **Purpose**: Student/candidate profile
- **Key Fields**:
  - `applicant_name` (Data)
  - `date_of_birth` (Date)
  - `gender` (Select: Male, Female, Transgender)
  - `aadhaar_number` (Data, encrypted)
  - `jan_aadhaar_id` (Data, encrypted)
  - `mobile_number` (Data)
  - `email` (Data)
  - `caste_category` (Select: General, SC, ST, OBC, MBC, SPC)
  - `income_group` (Select: Less than 5000, 5000-20000, 20000-50000, 50000-1Lac, 1Lac-2Lacs, 2Lacs-4.50Lacs)
  - `nsfa_status` (Select: BPL, State BPL, APL, Antyodaya)
  - `disability_status` (Select: Yes, No)
  - `disability_type` (Select: Physical, Visual, Hearing, Intellectual, Multiple)
  - `disability_percentage` (Percent)
  - `permanent_address`, `temporary_address` (Small Text)
  - `bank_account_number` (Data, encrypted)
  - `bank_ifsc`, `bank_name`, `account_holder_name` (Data)
  - `is_profile_verified` (Check)
  - `profile_verified_by` (Link to User)
  - `profile_verified_on` (Datetime)

### 3.4 Application Management DocTypes

#### Scholarship Application
- **Purpose**: Main application record
- **Key Fields**:
  - `application_number` (Data, unique, auto-generated: `APP-.YYYY.-`)
  - `applicant` (Link to Applicant)
  - `scheme` (Link to Scholarship Scheme)
  - `academic_year` (Link to Academic Year)
  - `institution` (Link to Institution Master)
  - `application_status` (Select: Draft, Submitted, Under Verification, Sent Back, Approved, Rejected, Disbursed)
  - `submitted_on` (Datetime)
  - `eligibility_status` (Select: Eligible, Ineligible, Pending Clarification)
  - `eligibility_score` (Float) - Proximity score from Eligibility Engine
  - `eligibility_remarks` (Text)
  - `applied_amount` (Currency)
  - `sanctioned_amount` (Currency)
  - `current_assignee` (Link to User)
  - `institute_verified`, `district_verified`, `state_verified` (Check)
  - `institute_verified_by`, `district_verified_by`, `state_verified_by` (Link to User)
  - `rejection_reason` (Text)
  - `query_raised`, `query_details`, `query_resolved` (Check/Text)
  - `version_number` (Int) - For tracking resubmissions

### 3.5 Disbursement DocTypes

#### Disbursement Batch
- **Purpose**: Group applications for disbursement
- **Key Fields**:
  - `batch_number` (Data, unique, auto-generated: `DBATCH-.YYYY.-`)
  - `scheme` (Link to Scholarship Scheme)
  - `academic_year` (Link to Academic Year)
  - `batch_date` (Date)
  - `total_applications` (Int)
  - `total_amount` (Currency)
  - `status` (Select: Draft, Generated, Sent to Finance, Approved by Finance, Uploaded to PFMS, Completed, Failed)
  - `generated_by`, `generated_on` (Link to User, Datetime)
  - `finance_approved_by`, `finance_approved_on` (Link to User, Datetime)
  - `pfms_uploaded_on` (Datetime)
  - `pfms_batch_id` (Data)

#### Disbursement Record
- **Purpose**: Individual disbursement record
- **Key Fields**:
  - `application` (Link to Scholarship Application)
  - `disbursement_batch` (Link to Disbursement Batch)
  - `applicant` (Link to Applicant)
  - `scheme` (Link to Scholarship Scheme)
  - `sanction_order_number` (Data, unique)
  - `disbursement_amount` (Currency)
  - `disbursement_status` (Select: Pending, Processed, Failed, Reversed)
  - `disbursement_date` (Date)
  - `transaction_reference` (Data) - From PFMS/DBT
  - `bank_account_number`, `bank_ifsc` (Data)
  - `failure_reason` (Text)
  - `pfms_status` (Select: Pending, Success, Failed)
  - `reconciliation_status` (Select: Pending, Matched, Unmatched)

### 3.6 Grievance DocTypes

#### Grievance Ticket
- **Purpose**: Track grievances
- **Key Fields**:
  - `ticket_number` (Data, unique, auto-generated: `GRV-.YYYY.-`)
  - `applicant` (Link to Applicant)
  - `institution` (Link to Institution Master) - Optional
  - `scheme` (Link to Scholarship Scheme) - Optional
  - `application` (Link to Scholarship Application) - Optional
  - `grievance_category` (Select: Application Issue, Disbursement Issue, Document Verification, Eligibility Dispute, Technical Error, Other)
  - `priority` (Select: Normal, Urgent, High)
  - `subject` (Data)
  - `description` (Text Editor)
  - `ticket_status` (Select: Open, In Progress, Resolved, Closed, Escalated)
  - `current_level` (Select: Level 1 - Institute/District, Level 2 - State Nodal, Level 3 - Department Secretary)
  - `current_assignee` (Link to User)
  - `created_by`, `created_on` (Link to User, Datetime)
  - `resolved_on` (Datetime)
  - `resolution_remarks` (Text)
  - `sla_deadline` (Datetime)
  - `sla_breached` (Check)
  - `source` (Select: Portal, WhatsApp, Chatbot, IVR)

### 3.7 Rules Engine DocTypes

#### Eligibility Rule Definition
- **Purpose**: Master table for reusable rule templates
- **Key Fields**:
  - `rule_code` (Data, unique, auto-generated: `ELIG-RULE-.YYYY.-`)
  - `rule_name` (Data)
  - `rule_type` (Select: Field Check, Document Check, Academic Check, Geographic Check, Composite)
  - `field_name` (Data - field path like "applicant.date_of_birth")
  - `operator` (Select: equals, not_equals, greater_than, less_than, between, in, not_in, contains, regex, age_between, age_greater_than, age_less_than)
  - `value_type` (Select: Static Value, Dynamic Field, Formula Expression)
  - `value` (Text/JSON)
  - `error_message_template` (Text)
  - `is_active` (Check)

#### Scheme Rule Configuration
- **Purpose**: Link rules to schemes with specific values
- **Key Fields**:
  - `scheme` (Link to Scholarship Scheme)
  - `rule` (Link to Eligibility Rule Definition)
  - `rule_priority` (Select: Critical, Optional)
  - `rule_order` (Int)
  - `operator` (Select - can override from rule definition)
  - `value` (Text/JSON - scheme-specific value)
  - `value_from`, `value_to` (Currency/Int - for "between" operator)
  - `value_list` (Table: Value List Item - for "in" operator)
  - `error_message` (Text - can override)
  - `score_weight` (Float - for optional rules)
  - `is_active` (Check)
  - `effective_from`, `effective_to` (Date)

#### Composite Rule
- **Purpose**: Define complex rules with AND/OR logic
- **Key Fields**:
  - `composite_rule_name` (Data)
  - `scheme` (Link to Scholarship Scheme)
  - `logic_operator` (Select: AND, OR)
  - `child_rules` (Table: Child Rule)
  - `is_critical` (Check)
  - `is_active` (Check)
  - `rule_order` (Int)

#### Eligibility Evaluation Result
- **Purpose**: Store evaluation results for applications
- **Key Fields**:
  - `application` (Link to Scholarship Application)
  - `scheme` (Link to Scholarship Scheme)
  - `rule_version` (Data)
  - `evaluation_date` (Datetime)
  - `overall_eligible` (Check)
  - `critical_rules_passed` (Int)
  - `critical_rules_total` (Int)
  - `optional_score` (Float)
  - `max_optional_score` (Float)
  - `proximity_score` (Float)
  - `evaluation_details` (JSON)
  - `failed_critical_rules` (JSON)
  - `passed_optional_rules` (JSON)
  - `evaluation_log` (Text)

---

## 4. API Endpoints

### 4.1 Public APIs (`usi/api/public.py`)

#### `get_schemes()`
- **Method**: GET
- **Purpose**: List all published scholarship schemes
- **Parameters**: 
  - `search` (optional) - Search term
  - `category` (optional) - Filter by category
  - `page` (optional) - Page number for pagination
  - `page_size` (optional) - Items per page
- **Returns**: List of schemes with basic information

#### `get_scheme_detail()`
- **Method**: GET
- **Purpose**: Get detailed information about a specific scheme
- **Parameters**: 
  - `scheme` (required) - Scheme name or code
- **Returns**: Complete scheme details including eligibility criteria, documents, and quota information

#### `get_public_stats()`
- **Method**: GET
- **Purpose**: Get public statistics for homepage
- **Returns**: 
  - Total schemes
  - Total beneficiaries
  - Total funds disbursed
  - Districts covered

#### `check_application_status()`
- **Method**: GET
- **Purpose**: Track application status without login
- **Parameters**: 
  - `application_number` (optional) - Application number
  - `aadhaar_number` (optional) - Aadhaar number
- **Returns**: Application status with timeline

### 4.2 Application APIs (`usi/api/application.py`)

#### `submit_application()`
- **Method**: POST
- **Purpose**: Submit a new scholarship application
- **Parameters**: Application data (JSON)
- **Returns**: Application number and status

#### `get_user_applications()`
- **Method**: GET
- **Purpose**: Get all applications for logged-in user
- **Returns**: List of user's applications with status

### 4.3 Eligibility APIs (`usi/api/eligibility.py`)

#### `evaluate_eligibility()`
- **Method**: POST
- **Purpose**: Evaluate eligibility for an application or applicant data
- **Parameters**: 
  - `application_name` (optional) - Application name
  - OR `scheme_name` + `applicant_data` (JSON)
- **Returns**: Evaluation result with eligible status, scores, failed rules

#### `get_eligibility_rules()`
- **Method**: GET
- **Purpose**: Get all rules for a scheme (for display)
- **Parameters**: `scheme_name`
- **Returns**: List of rules and composite rules

#### `test_rule()`
- **Method**: POST
- **Purpose**: Test a rule against sample data
- **Parameters**: `rule_name`, `test_data` (JSON)
- **Returns**: Rule evaluation result

---

## 5. Website Pages

### 5.1 Public Pages

#### Home Page (`/index`)
- **Purpose**: Main landing page
- **Features**:
  - Hero section with call-to-action
  - Statistics dashboard (schemes, beneficiaries, funds, districts)
  - Features section (Discover, Apply, Track)
  - Announcements/Notifications banner
  - Responsive design
- **Template**: `templates/pages/index.html`

#### Schemes List (`/schemes`)
- **Purpose**: Display all available scholarship schemes
- **Features**:
  - Search functionality
  - Category filtering
  - Pagination
  - Scheme cards with key information
  - Responsive grid layout
- **Template**: `templates/pages/schemes.html`

#### Scheme Detail (`/scheme_detail`)
- **Purpose**: Detailed information about a specific scheme
- **Features**:
  - Complete scheme description
  - Eligibility criteria section
  - Required documents list
  - Application process steps
  - Important dates
  - FAQ section
  - Apply Now button
- **Template**: `templates/pages/scheme_detail.html`

#### Application Form (`/apply`)
- **Purpose**: Online application submission
- **Features**:
  - Multi-step form (Personal Details → Academic Details → Documents → Review)
  - Auto-fill from Jan Aadhaar/DigiLocker (if logged in)
  - Document upload with progress indicator
  - Real-time eligibility check
  - Save as Draft functionality
  - Form validation
  - Application preview before submission
- **Template**: `templates/pages/apply.html`

#### Application Status Tracking (`/track`)
- **Purpose**: Track application progress
- **Features**:
  - Search by Application Number or Aadhaar/Jan Aadhaar
  - Visual timeline showing current status
  - Status details (Submitted, Under Verification, Approved, etc.)
  - Document verification status
  - Query/Correction requests (if any)
  - Download acknowledgment
- **Template**: `templates/pages/track_application.html`

#### Login Page (`/login`)
- **Purpose**: User authentication
- **Features**:
  - Aadhaar-based Biometric Login
  - Jan Aadhaar ID + OTP
  - Mobile Number + OTP
  - Email + OTP
  - New user registration flow
- **Template**: `templates/pages/login.html`

#### User Dashboard (`/profile`)
- **Purpose**: Personal dashboard for logged-in users
- **Features**:
  - Profile overview
  - All applications list with status
  - Renewal eligibility alerts
  - Disbursement history
  - Active grievances
  - Document library
  - Quick actions (Apply New, Track Application, Raise Grievance)
- **Template**: `templates/pages/profile.html`
- **Access**: Requires login

#### Grievance Portal (`/grievance`)
- **Purpose**: Raise and track grievances
- **Features**:
  - Grievance submission form
  - Category selection
  - Link to application (if applicable)
  - File upload for supporting documents
  - Ticket tracking (by ticket number)
  - Response history
  - Status updates
- **Template**: `templates/pages/grievance.html`

#### About Page (`/about`)
- **Purpose**: Portal information and help
- **Features**:
  - About the Portal
  - How to Apply (step-by-step guide)
  - Eligibility Guidelines
  - Document Requirements
  - FAQ Section
  - Contact Us
  - Help & Support
- **Template**: `templates/pages/about.html`

### 5.2 Website Components

#### Navbar (`templates/includes/navbar.html`)
- Responsive navigation
- Login/Logout toggle
- All page links
- Mobile-friendly hamburger menu

#### Footer (`templates/includes/footer.html`)
- Quick links
- Support links
- Contact information
- Copyright notice

### 5.3 Website Assets

#### CSS (`www/css/website.css`)
- Modern, clean design
- Mobile-responsive
- Consistent color scheme (#667eea primary)
- Professional government portal aesthetic

#### JavaScript (`www/js/website.js`)
- Form validation
- Multi-step form navigation
- API calls
- Real-time eligibility checking
- Status tracking updates

---

## 6. Rules Engine Design

### 6.1 Architecture

The rules engine uses a **DocType-based approach** leveraging Frappe's native features:

- **No JSON editing required** - Users configure rules through Frappe Desk UI
- **Leverages Frappe's built-in features** - Uses DocTypes, Custom Scripts, and Expression Evaluation
- **Similar to ERPNext Pricing Rules** - Proven pattern in Frappe ecosystem
- **User-friendly** - Non-technical users can manage rules
- **Audit trail** - Full version history and change tracking

### 6.2 Rule Evaluation Flow

```
1. Load active rules for scheme from Scheme Rule Configuration
2. Separate critical and optional rules
3. Evaluate critical rules first (must all pass)
4. If critical rules pass, evaluate optional rules (for scoring)
5. Calculate proximity score (0-1 scale)
6. Store results in Eligibility Evaluation Result
7. Update application eligibility status
```

### 6.3 Supported Operators

- `equals` - Field equals value
- `not_equals` - Field not equals value
- `greater_than` - Field > value
- `less_than` - Field < value
- `between` - Field between [min, max]
- `in` - Field in list
- `not_in` - Field not in list
- `contains` - Field contains value
- `regex` - Field matches regex pattern
- `age_between` - Age between [min, max]
- `age_greater_than` - Age > value
- `age_less_than` - Age < value

### 6.4 Rule Types

1. **Field Check** - Check applicant/application fields
2. **Document Check** - Verify document presence (future)
3. **Academic Check** - Check academic performance
4. **Geographic Check** - Check location-based eligibility
5. **Composite** - Combine multiple rules with AND/OR logic

### 6.5 Rules Engine Core

**Location**: `usi/engine/rules_engine.py`

**Key Methods**:
- `load_rules()` - Loads active rules for a scheme
- `evaluate()` - Evaluates applicant against all rules
- `evaluate_rule()` - Evaluates a single rule
- `evaluate_composite_rule()` - Evaluates composite rules
- `apply_operator()` - Applies operators (equals, greater_than, between, etc.)
- `calculate_age()` - Calculates age from date of birth
- `calculate_proximity()` - Calculates proximity score

---

## 7. Data Model & Relationships

### 7.1 Key Relationships

```
Scholarship Scheme (1) ──→ (N) Scholarship Application
Applicant (1) ──→ (N) Scholarship Application
Institution Master (1) ──→ (N) Scholarship Application
Scholarship Application (1) ──→ (1) Disbursement Record
Applicant (1) ──→ (N) Applicant Documents
Scholarship Scheme (1) ──→ (N) Scheme Eligibility Criteria
Scholarship Scheme (1) ──→ (N) Scheme Quota Allocation
Scholarship Scheme (1) ──→ (N) Scheme Rule Configuration
Applicant (1) ──→ (N) Grievance Ticket
```

### 7.2 DocType Summary

| Module | DocTypes | Key DocTypes |
|--------|----------|--------------|
| Master Data | 3 | Academic Year, Department Master, Institution Master |
| Scheme Management | 4 | Scholarship Scheme, Scheme Eligibility Criteria, Scheme Quota Allocation, Scheme Document Requirements |
| Candidate Management | 1 | Applicant |
| Application Management | 1 | Scholarship Application |
| Disbursement | 2 | Disbursement Batch, Disbursement Record |
| Grievance | 1 | Grievance Ticket |
| Rules Engine | 4 | Eligibility Rule Definition, Scheme Rule Configuration, Composite Rule, Eligibility Evaluation Result |
| **Total** | **16** | |

---

## 8. Integration Architecture

### 8.1 External System Integrations

1. **Jan Aadhaar / Aadhaar**
   - **Purpose**: Identity verification, demographic data
   - **Method**: REST API
   - **Data**: Name, DOB, Address, Caste, Income

2. **DigiLocker**
   - **Purpose**: Document verification
   - **Method**: REST API
   - **Data**: Certificates, Marksheets

3. **AISHE (All India Survey on Higher Education)**
   - **Purpose**: Institution verification
   - **Method**: REST API / Master Data Upload
   - **Data**: Institution details, courses

4. **PFMS (Public Financial Management System)**
   - **Purpose**: Disbursement
   - **Method**: File Upload / API
   - **Data**: Sanction files, transaction status

5. **State DBT Portal**
   - **Purpose**: Alternative disbursement channel
   - **Method**: API Integration
   - **Data**: Beneficiary data, payment status

6. **SMS/Email Gateway**
   - **Purpose**: Notifications
   - **Method**: API
   - **Data**: OTPs, status updates

7. **WhatsApp API**
   - **Purpose**: Grievance intake, notifications
   - **Method**: API
   - **Data**: Messages, media

### 8.2 Integration Patterns

- **Synchronous**: Eligibility checks, OTP verification
- **Asynchronous**: Document sync, disbursement uploads
- **Scheduled Jobs**: Daily sync with external systems
- **Webhooks**: Receive status updates from PFMS

---

## 9. Security & Compliance

### 9.1 Data Security

- **Encryption**: Sensitive fields (Aadhaar, bank details) encrypted at rest
- **Access Control**: Role-based permissions
- **Audit Trail**: All actions logged
- **Data Masking**: PII masked in reports
- **Session Management**: Secure session handling

### 9.2 Compliance

- **Data Privacy**: GDPR-compliant data handling
- **Audit Logs**: Comprehensive logging for compliance
- **Data Retention**: Configurable retention policies
- **Backup & Recovery**: Regular backups

---

## 10. Project Structure

```
usi/
├── usi/
│   ├── unified_scholarship_interface/
│   │   ├── doctype/          # All DocTypes
│   │   │   ├── academic_year/
│   │   │   ├── department_master/
│   │   │   ├── scholarship_scheme/
│   │   │   ├── institution_master/
│   │   │   ├── applicant/
│   │   │   ├── scholarship_application/
│   │   │   ├── scheme_eligibility_criteria/
│   │   │   ├── scheme_quota_allocation/
│   │   │   ├── scheme_document_requirements/
│   │   │   ├── disbursement_batch/
│   │   │   ├── disbursement_record/
│   │   │   ├── grievance_ticket/
│   │   │   ├── eligibility_rule_definition/
│   │   │   ├── scheme_rule_configuration/
│   │   │   ├── composite_rule/
│   │   │   └── eligibility_evaluation_result/
│   │   ├── api/              # API endpoints
│   │   │   ├── public.py
│   │   │   ├── application.py
│   │   │   └── eligibility.py
│   │   ├── engine/           # Rules engine
│   │   │   └── rules_engine.py
│   │   └── templates/        # Website pages
│   │       ├── pages/
│   │       │   ├── index.html
│   │       │   ├── schemes.html
│   │       │   ├── scheme_detail.html
│   │       │   ├── apply.html
│   │       │   ├── track_application.html
│   │       │   ├── login.html
│   │       │   ├── profile.html
│   │       │   ├── grievance.html
│   │       │   └── about.html
│   │       └── includes/
│   │           ├── navbar.html
│   │           └── footer.html
│   ├── www/                  # Static assets
│   │   ├── css/
│   │   │   └── website.css
│   │   └── js/
│   │       └── website.js
│   └── hooks.py             # App configuration
├── Design.md                # This file
├── Quickstart.md            # Setup guide
└── README.md                # Project overview
```

---

## 11. Key Design Decisions

1. **DocType-Based Rules Engine**: No JSON editing required, user-friendly UI
2. **Multi-level Verification**: Institute → District → State workflow
3. **Auto-Renewal**: Automatic renewal based on academic performance
4. **Quota Management**: Multi-dimensional quota allocation
5. **Document Verification**: Hybrid approach (auto + manual)
6. **Public Website First**: Built public-facing portal before admin module
7. **Frappe Native Features**: Leverages Frappe's built-in capabilities wherever possible

---

## 12. Implementation Status

### ✅ Completed Components

- **Public Website**: 9 pages fully implemented
- **Core DocTypes**: 16 DocTypes created
- **API Endpoints**: 9 endpoints implemented
- **Rules Engine**: Complete with DocType-based configuration
- **Form Integration**: Application and grievance forms functional

### 🔮 Future Enhancements

- Workflows for approvals
- Advanced dashboards
- Reports
- Bulk operations
- Document upload handling
- OTP authentication implementation
- Advanced integrations (Jan Aadhaar, DigiLocker, PFMS)

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-15  
**Status**: Production Ready

