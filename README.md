# Unified Scholarship Interface (USI)

A comprehensive Frappe-based application for managing state government scholarship programs. The system streamlines discovery, application, verification, and disbursement of scholarships while improving coverage, efficiency, and transparency.

---

## 🎯 Features

### Public Website
- **Scheme Discovery**: Browse and search available scholarship schemes
- **Online Application**: Multi-step application form with document upload
- **Application Tracking**: Real-time status tracking with visual timeline
- **Grievance Portal**: Submit and track grievances
- **User Dashboard**: Personal dashboard for applicants
- **Responsive Design**: Mobile-first, works on all devices

### Admin Module
- **Scheme Management**: Create and manage scholarship schemes
- **Application Management**: Review, verify, and approve applications
- **Disbursement Management**: Process payments and track disbursements
- **Grievance Management**: Handle and resolve grievances
- **Reporting**: Comprehensive dashboards and reports

---

## 📋 Requirements

- Frappe Framework v15+
- Python 3.10+
- MariaDB/MySQL
- Bench CLI

---

## 🚀 Installation

### 1. Install the App
```bash
cd /path/to/your/bench
bench get-app https://github.com/your-repo/usi --branch develop
bench install-app usi
```

### 2. Migrate DocTypes
```bash
bench migrate
bench clear-cache
bench restart
```

### 3. Create Sample Data
1. Create Academic Year (e.g., "2024-25")
2. Create Department Master
3. Create Institution Master
4. Create Scholarship Scheme with status "Published"

### 4. Access the Website
- Public Website: `http://your-site:8000/index`
- Frappe Desk: `http://your-site:8000`

---

## 📁 Project Structure

```
usi/
├── usi/
│   ├── unified_scholarship_interface/
│   │   ├── doctype/          # All DocTypes
│   │   ├── api/              # API endpoints
│   │   └── templates/        # Website pages
│   ├── www/                  # Static assets
│   └── hooks.py             # App configuration
├── DESIGN_PLAN.md            # Complete design plan
├── APPROACH_SUMMARY.md       # High-level approach
└── MIGRATION_INSTRUCTIONS.md # Migration guide
```

---

## 📚 Documentation

- **DESIGN_PLAN.md** - Complete technical design
- **APPROACH_SUMMARY.md** - High-level overview
- **MIGRATION_INSTRUCTIONS.md** - Setup guide
- **FINAL_DOCUMENTATION.md** - Complete status

---

## 🎨 Core DocTypes

1. Academic Year
2. Department Master
3. Scholarship Scheme
4. Institution Master
5. Applicant
6. Scholarship Application
7. Scheme Eligibility Criteria
8. Scheme Quota Allocation
9. Scheme Document Requirements
10. Disbursement Batch
11. Disbursement Record
12. Grievance Ticket

---

## 🔌 API Endpoints

### Public APIs
- `GET /api/method/usi.api.public.get_schemes` - List schemes
- `GET /api/method/usi.api.public.get_scheme_detail` - Scheme details
- `GET /api/method/usi.api.public.get_public_stats` - Statistics
- `GET /api/method/usi.api.public.check_application_status` - Track application

### Application APIs
- `POST /api/method/usi.api.application.submit_application` - Submit application
- `GET /api/method/usi.api.application.get_user_applications` - Get user applications

---

## 🌐 Website Pages

- `/index` - Home page
- `/schemes` - Schemes list
- `/scheme_detail` - Scheme details
- `/apply` - Application form
- `/track` - Track application
- `/login` - Login page
- `/profile` - User dashboard
- `/grievance` - Grievance portal
- `/about` - About page

---

## 🔧 Configuration

### Website Home Page
1. Go to **Website Settings** in Frappe Desk
2. Set **Home Page** to: `index`

### Naming Series
Naming series will auto-create on first use, or configure manually:
- Applicant: `APPL-.YYYY.-`
- Scholarship Application: `APP-.YYYY.-`
- Disbursement Batch: `DBATCH-.YYYY.-`
- Grievance Ticket: `GRV-.YYYY.-`

---

## 🧪 Testing

### Test Public Website
1. Visit `/index` - Should show homepage
2. Visit `/schemes` - Should list schemes
3. Submit test application via `/apply`
4. Track application via `/track`

### Test Admin Module
1. Create test scheme
2. Create test application
3. Verify validations work
4. Test status transitions

---

## 📝 Development

### Code Style
- Python: Follows Frappe standards
- JavaScript: ESLint configured
- Formatting: Pre-commit hooks enabled

### Running Tests
```bash
bench run-tests --app usi
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📄 License

MIT License - See `license.txt` for details

---

## 👥 Contributors

- Indusaction Team

---

## 📞 Support

For issues and questions:
- Email: ankit@impactyaan.com
- Create an issue in the repository

---

## 🎉 Status

**Current Version**: 1.0  
**Status**: ✅ Production Ready  
**Last Updated**: 2025-01-15

---

**Ready to manage scholarships efficiently!** 🚀
