# USI - Quick Start Guide

This guide walks you through the setup steps required in Frappe after installing the USI app to get the system running.

---

## Prerequisites

- Frappe Framework v15+ installed
- USI app installed via `bench install-app usi`
- Bench migrated via `bench migrate`

---

## Step 1: Migrate DocTypes

After installing the app, migrate all DocTypes to the database:

```bash
cd /home/ubuntu/frappe-bench
bench migrate
bench clear-cache
bench restart
```

This will create all DocTypes in the database and set up all fields and relationships.

---

## Step 2: Verify DocTypes

1. Login to Frappe Desk
2. Go to **DocType List** (search for it in the search bar)
3. Verify these DocTypes appear:

**Master Data:**
- Academic Year
- Department Master
- Institution Master

**Scheme Management:**
- Scholarship Scheme
- Scheme Eligibility Criteria
- Scheme Quota Allocation
- Scheme Document Requirements

**Application Management:**
- Applicant
- Scholarship Application

**Disbursement:**
- Disbursement Batch
- Disbursement Record

**Grievance:**
- Grievance Ticket

**Rules Engine:**
- Eligibility Rule Definition
- Scheme Rule Configuration
- Composite Rule
- Eligibility Evaluation Result

---

## Step 3: Configure Naming Series

Naming series will auto-create on first use, but you can configure them manually:

1. Go to **Naming Series** (search in Frappe)
2. Configure for:
   - **Applicant**: `APPL-.YYYY.-`
   - **Scholarship Application**: `APP-.YYYY.-`
   - **Disbursement Batch**: `DBATCH-.YYYY.-`
   - **Grievance Ticket**: `GRV-.YYYY.-`
   - **Eligibility Rule Definition**: `ELIG-RULE-.YYYY.-`

**Note**: They will auto-configure on first document creation if not set manually.

---

## Step 4: Create Master Data

### 4.1 Create Academic Year

1. Go to **Academic Year** → New
2. Fill in:
   - **Academic Year**: `2024-25` (or your current year)
   - **Start Date**: `2024-04-01` (or your academic year start)
   - **End Date**: `2025-03-31` (or your academic year end)
   - **Is Active**: ✓ (checked)
3. Click **Save**

### 4.2 Create Department Master

1. Go to **Department Master** → New
2. Fill in:
   - **Department Name**: `Education Department` (or your department name)
   - **Department Code**: `EDU001` (or your code)
   - **Is Active**: ✓ (checked)
3. Click **Save**

### 4.3 Create Institution Master

1. Go to **Institution Master** → New
2. Fill in:
   - **Institution Name**: `Test College` (or your institution name)
   - **AISHE Code**: `TEST001` (or your AISHE code)
   - **Institution Type**: `Govt` (or Private/Aided)
   - **District**: Enter district name
   - **State**: Enter state name
   - **Is Active**: ✓ (checked)
3. Fill in optional fields:
   - **Nodal Officer Name**, **Email**, **Phone**
   - **Bank Account Number**, **IFSC**, **Bank Name**
4. Click **Save**

---

## Step 5: Create Scholarship Scheme

1. Go to **Scholarship Scheme** → New
2. Fill in basic information:
   - **Scheme Name**: `Post-Matric Scholarship` (or your scheme name)
   - **Scheme Code**: `PMS-2024` (or your code)
   - **Scheme Type**: `State Govt` (or Central Govt/Central-State)
   - **Scheme Category**: `Category-based` (or your category)
   - **Financial Year**: Select the Academic Year created in Step 4.1
   - **Start Date**: `2024-04-01` (or your scheme start date)
   - **End Date**: `2025-03-31` (or your scheme end date)
   - **Total Budget**: `10000000` (₹1 Crore or your budget)
   - **Budget Department**: Select Department created in Step 4.2
   - **Status**: `Published` (important: must be Published to show on website)
3. Fill in optional fields:
   - **Scheme Objective**: Description of the scheme
   - **Is Multi Year**: ✓ if applicable
   - **Auto Renewal Enabled**: ✓ if applicable
4. Click **Save**

**Important**: Set status to **"Published"** for the scheme to appear on the public website.

---

## Step 6: Configure Website Settings

1. Go to **Website Settings** in Frappe Desk
2. Set **Home Page** to: `index`
3. Set **Website Title** and **Brand Name** as needed
4. Click **Save**

---

## Step 7: Test Public Website

### 7.1 Test Home Page

1. Visit: `http://your-site:8000/index`
2. Should show:
   - Hero section
   - Statistics (Total Schemes: 1 if you created one)
   - Features section
   - Navigation

### 7.2 Test Schemes List

1. Visit: `http://your-site:8000/schemes`
2. Should show:
   - The scheme you created (if status is "Published")
   - Search and filter options
   - Pagination

### 7.3 Test Scheme Detail

1. Click on a scheme from the list
2. Should show:
   - Complete scheme details
   - Eligibility criteria
   - Required documents
   - Apply button

### 7.4 Test Application Form

1. Visit: `http://your-site:8000/apply`
2. Fill out the form:
   - Step 1: Personal Details
   - Step 2: Academic Details (select scheme and institution)
   - Step 3: Document Upload
   - Step 4: Review & Submit
3. Submit the form
4. Should create:
   - Applicant record
   - Scholarship Application record
   - Redirect to tracking page

### 7.5 Test Application Tracking

1. Visit: `http://your-site:8000/track`
2. Enter application number (from Step 7.4)
3. Should show:
   - Application status
   - Status timeline
   - Application details

---

## Step 8: Configure Rules Engine (Optional)

### 8.1 Create Eligibility Rule Definition

1. Go to **Eligibility Rule Definition** → New
2. Fill in:
   - **Rule Name**: `Age Between 18-25` (or your rule name)
   - **Rule Type**: `Field Check`
   - **Field Name**: `applicant.date_of_birth`
   - **Operator**: `age_between`
   - **Value**: `[18, 25]` (JSON array format)
   - **Error Message Template**: `Applicant age must be between 18 and 25 years`
   - **Is Active**: ✓ (checked)
3. Click **Save**

### 8.2 Create Scheme Rule Configuration

1. Go to **Scheme Rule Configuration** → New
2. Fill in:
   - **Scheme**: Select the scheme created in Step 5
   - **Is Active**: ✓ (checked)
3. In the **Rules** table, click **Add Row**:
   - **Rule**: Select the Eligibility Rule Definition created in Step 8.1
   - **Priority**: `Critical` (must pass) or `Optional` (scoring)
   - **Order**: `1` (evaluation order)
   - **Active**: ✓ (checked)
4. Click **Save**

### 8.3 Test Eligibility Check

1. Create a **Scholarship Application** (via website or admin)
2. Click **"Check Eligibility"** button
3. View eligibility results:
   - Eligibility Status
   - Eligibility Score
   - Eligibility Remarks
4. Check **Eligibility Evaluation Result** record for detailed results

---

## Step 9: Configure Permissions (Optional)

Default permissions are set to:
- **System Manager**: Full access
- **All**: Read access (for public)

You may want to configure role-based permissions:

1. Go to **Role Permissions Manager**
2. Configure permissions for:
   - **Scheme Creator**: Can create/modify schemes
   - **Scheme Reviewer**: Can review schemes
   - **Institute Verifier**: Can verify applications
   - **District Officer**: District-level verification
   - **State Officer**: State-level approval
   - **Finance Officer**: Disbursement management
   - **Grievance Officer**: Handle grievances

---

## Step 10: Create Sample Data (For Testing)

### 10.1 Create Multiple Schemes

Create 2-3 more schemes with different categories to test filtering on the website.

### 10.2 Create Multiple Institutions

Create 5-10 institutions in different districts to populate the application form dropdown.

### 10.3 Create Test Applications

1. Submit applications via the website (`/apply`)
2. Or create directly in Frappe Desk
3. Test different statuses:
   - Draft
   - Submitted
   - Under Verification
   - Approved
   - Rejected

---

## Troubleshooting

### Issue: DocTypes not appearing after migration

**Solution**:
```bash
bench clear-cache
bench restart
```

### Issue: Naming series errors

**Solution**: 
- Create naming series manually (Step 3)
- Or let them auto-create on first document save

### Issue: Website not showing schemes

**Solution**:
1. Make sure schemes have status = "Published"
2. Check Website Settings (Step 6)
3. Clear browser cache
4. Check browser console for errors

### Issue: API endpoints returning errors

**Solution**:
1. Check if DocTypes are migrated
2. Check Frappe logs: `bench logs`
3. Verify DocType names match exactly (case-sensitive)

### Issue: Application form not submitting

**Solution**:
1. Check if Applicant and Scholarship Application DocTypes exist
2. Verify all required fields are filled
3. Check browser console for JavaScript errors
4. Check Frappe logs for server errors

---

## Next Steps

After completing the quick start:

1. **Create Workflows** (optional):
   - Scheme approval workflow
   - Application verification workflow
   - Disbursement workflow

2. **Build Admin Dashboards** (optional):
   - Scheme management dashboard
   - Application review dashboard
   - Disbursement dashboard

3. **Add Advanced Features** (optional):
   - Eligibility Engine integration (if using external engine)
   - Auto-renewal
   - Bulk operations
   - Reports
   - Document upload handling
   - OTP authentication

4. **Configure Integrations** (optional):
   - Jan Aadhaar API
   - DigiLocker API
   - PFMS integration
   - SMS/Email gateway

---

## Quick Reference

### Essential URLs

- **Frappe Desk**: `http://your-site:8000`
- **Public Website**: `http://your-site:8000/index`
- **Schemes List**: `http://your-site:8000/schemes`
- **Application Form**: `http://your-site:8000/apply`
- **Track Application**: `http://your-site:8000/track`

### Essential Commands

```bash
# Migrate DocTypes
bench migrate

# Clear cache
bench clear-cache

# Restart bench
bench restart

# Build assets
bench build --app usi

# View logs
bench logs
```

### Essential DocTypes to Create First

1. Academic Year
2. Department Master
3. Institution Master
4. Scholarship Scheme (with status "Published")

---

## Summary Checklist

- [ ] Run `bench migrate`
- [ ] Verify all DocTypes appear
- [ ] Configure naming series (or let auto-create)
- [ ] Create Academic Year
- [ ] Create Department Master
- [ ] Create Institution Master
- [ ] Create Scholarship Scheme (status: Published)
- [ ] Configure Website Settings (home page: index)
- [ ] Test public website pages
- [ ] Test application submission
- [ ] Test application tracking
- [ ] (Optional) Configure Rules Engine
- [ ] (Optional) Configure permissions
- [ ] (Optional) Create sample data

---

**You're all set!** The system is now ready to use. Start by creating schemes and testing the public website.

**For detailed design information, see `Design.md`**

