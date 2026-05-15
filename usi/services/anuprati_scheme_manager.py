import frappe
from usi.models.result import Result
from usi.services.base_scheme_manager import BaseSchemeManager
import re
import uuid
import logging
from frappe.utils.file_manager import save_file
from time import sleep
logger = frappe.logger("anuprati_application", allow_site=True, file_count=50)
logger.setLevel(logging.INFO)
class AnupratiSchemeManager(BaseSchemeManager):
    DOCTYPE = "Anuprati Scheme Application"
    ATTACHMENT_FIELDS = ("12th_marksheet", "annual_income_certificate")

    def __init__(self, scheme_config=None, user=None):
        self.scheme_config = scheme_config or {}
        self.user = user or frappe.session.user
    def run_eligibility_check(self, application: dict) -> Result:
        try:
            checks =[]
            checks.append(self._check_domicile_status(application))
            checks.append(self._check_applicant_category(application))
            checks.append(self._check_family_income(application))
            checks.append(self._check_scheme_application_previous_year(application))
            checks.append(self._check_current_year_scheme_application(application))
            checks.append(self._check_qualification(application))
            return Result.success(message="Eligibility check completed", data=checks)
        except Exception as e:
            frappe.log_error(f"Error running eligibility check: {e}")
            return Result.failure(message=str(e), data=None)

    def _check_domicile_status(self, application: dict) -> dict:
        return {
              "type": "success",
              "title": {
                "en": "Rajasthan Domicile",
                "hi": "राजस्थान जिला"
              },
              "message": {
                "en": "Applicant is a Rajasthan domicile",
                "hi": "उम्मीदवार राजस्थान जिला का निवासी है"
              }
        }

    def _check_applicant_category(self, applicant_data: dict) -> dict:
        if applicant_data["category"] in [
            "Scheduled Caste (SC)",
            "Scheduled Tribe (ST)",
            "Other Backward Class (OBC)",
            "Most Backward Class (MBC)"
        ]:
             return {
              "type": "success",
              "title": {
                "en": "Applicant Category",
                "hi": "उम्मीदवार श्रेणी"
              },
              "message": {
                "en": "Applicant is eligible for the scheme as per the category",
                "hi": "उम्मीदवार श्रेणी के अनुसार योग्य है"
              }
            }
        return {
            "type": "failure",
            "title": {
            "en": "Applicant Category",
            "hi": "उम्मीदवार श्रेणी"
            },
            "message": {
            "en": "Applicant is not eligible for the scheme as per the category",
            "hi": "उम्मीदवार श्रेणी के अनुसार योग्य नहीं है"
            }
        }
    def _check_qualification(self, applicant_data: dict) -> dict:
        if (
            applicant_data["graduation_status"] in ("Passed", "Ongoing Year 3")
            and float(applicant_data["12th_marks_percentage"]) >= 60
        ):
            return {
                "type": "success",
                "title": {
                    "en": "Qualification",
                    "hi": "उम्मीदवार की शैक्षिक प्रतियोगिता"
                },
                "message": {
                    "en": "Applicant is eligible for the scheme as per the qualification",
                    "hi": "उम्मीदवार शैक्षिक प्रतियोगिता के अनुसार योग्य है"
                }
            }
        return {
            "type": "failure",
            "title": {
                "en": "Qualification",
                "hi": "उम्मीदवार की शैक्षिक प्रतियोगिता"
            },
            "message": {
                "en": "Applicant is not eligible for the scheme as per the qualification",
                "hi": "उम्मीदवार शैक्षिक प्रतियोगिता के अनुसार योग्य नहीं है"
            }
        }
    def _check_family_income(self, applicant_data: dict) -> dict:
        if float(applicant_data["family_income"]) <= 800000:
             return {
              "type": "success",
              "title": {
                "en": "Family Income below 800000 limit",
                "hi": "उम्मीदवार परिवार की आय 800000 सीमा से नीचे है"
              },
              "message": {
                "en": "Your family income is recorded as " + str(applicant_data["family_income"])+" which is below the 800000 limit",
                "hi": "उम्मीदवार परिवार की आय रिकॉर्ड की गई है " + str(applicant_data["family_income"]) + " जो 800000 सीमा से नीचे है"
              }
            }
        return {
            "type": "failure",
            "title": {
            "en": "Family Income above 800000 limit",
            "hi": "उम्मीदवार परिवार की आय 800000 सीमा से ऊपर है"
            },
            "message": {
            "en": "Your family income is recorded as " + str(applicant_data["family_income"])+" which is above the 800000 limit",
            "hi": "उम्मीदवार परिवार की आय रिकॉर्ड की गई है " + str(applicant_data["family_income"]) + " जो 800000 सीमा से ऊपर है"
            }
        }
    
    def _check_current_year_scheme_application(self, applicant_data: dict) -> dict:
        return {
            "type": "warning",
            "title": {
                "en": "One scheme already submitted",
                "hi": "एक स्कीम पहले से आवेदन किया है"
            },
            "message": {
                "en": "You have already applied for Anuprati Scheme for other exam. You can submit only one more scheme application for this year",
                "hi": "आपने पहले से आवेदन किया है इस वर्ष के लिए एक स्कीम आवेदन किया है। आप केवल एक और स्कीम आवेदन दे सकते हैं"
            }
        }

    def _check_scheme_application_previous_year(self, applicant_data: dict) -> dict:
        return {
            "type": "success",
            "title": {
                "en": "Previous year scheme application",
                "hi": "पिछले वर्ष स्कीम आवेदन"
            },
            "message": {
                "en": "You have not availed the scheme before this year",
                "hi": "आपने पिछले वर्ष स्कीम नहीं लाया है"
            }
        }

    def create_application(self, data):
        try:
            self._validate_create(data)
            data = self._transform_create(data)
            if "preference_1" in data and data["preference_1"]:
                data["preference_1"] = frappe.get_doc("Coaching Institute", {"institute_name": data["preference_1"]}).name
            if "preference_2" in data and data["preference_2"]:
                data["preference_2"] = frappe.get_doc("Coaching Institute", {"institute_name": data["preference_2"]}).name  
            data["name"] = self._generate_application_id(data)
            logger.info(f"Generated application ID: {data}")
            doc = self._insert_doc(data)
            self._save_attachments(doc)
            self._post_create(doc)

            return Result.success(
                message="Application submitted successfully",
                data={"name": doc.name},
            )
        except frappe.ValidationError as exc:
            return Result.bad_request(message=str(exc))
        except Exception as exc:
            frappe.log_error(
                frappe.get_traceback(), "Anuprati Application Submission Error"
            )
            return Result.failure(message=str(exc), data=None)

    def _save_attachments(self, doc):
        files = getattr(frappe.request, "files", None)
        if not files:
            return

        attachment_updates = {}
        for fieldname in self.ATTACHMENT_FIELDS:
            uploaded_file = files.get(fieldname)
            if not uploaded_file or not getattr(uploaded_file, "filename", None):
                continue

            file_doc = save_file(
                fname=uploaded_file.filename,
                content=uploaded_file.stream.read(),
                dt=doc.doctype,
                dn=doc.name,
                is_private=1,
            )
            attachment_updates[fieldname] = file_doc.file_url

        if attachment_updates:
            doc.db_set(attachment_updates, update_modified=True)

    def _generate_application_id(self, applicant_data: dict)->str:
        applicant = applicant_data.get("first_name")
        clean_name = re.sub(r'[^A-Za-z]', '', applicant).upper()
        prefix = clean_name[:4].ljust(4, 'X')
        unique_id = str(uuid.uuid4())[:8].upper()
        return f"AS-{prefix}-{unique_id}"
    
    def run_allotment(self):
        try:
            application_names = frappe.get_all(
                self.DOCTYPE,
                filters={"workflow_state": "Verified"},
                pluck="name",
            )

            allotted_count = 0
            for application_name in application_names:
                application_doc = frappe.get_doc(self.DOCTYPE, application_name)
                result = self.run_eligibility_check(application_doc.as_dict())

                if not result.success:
                    continue

                checks = result.data or []
                has_failure = any(check.get("type") == "failure" for check in checks)
                if has_failure:
                    continue

                application_doc.workflow_state = "Shortlisted"
                application_doc.save(ignore_permissions=True)
                allotted_count += 1

            frappe.db.commit()
            return Result.success(
                message=f"Allotment completed. {allotted_count} application(s) allotted.",
                data={"allotted_count": allotted_count, "verified_count": len(application_names)},
            )
        except Exception as e:
            frappe.log_error(f"Error running allotment: {e}")
            return Result.failure(message=str(e), data=None)


@frappe.whitelist()
def run_allotment():
    result = AnupratiSchemeManager().run_allotment()
    if result.success:
        return result.message
    frappe.throw(result.message or "Failed to run allotment")