from usi.services.anuprati_scheme_manager import AnupratiSchemeManager
import json
import frappe
from usi.utils.custom_response import custom_response

logger = frappe.logger("api", allow_site=True, file_count=50)
@frappe.whitelist()
def submit(application):
    logger.info(f"Submitting application: {application}")
    try:
        return AnupratiSchemeManager().create_application(application).to_custom_response()
    except Exception as e:
        logger.error(f"Error submitting application: {e}")
        return custom_response(message=str(e), data=None, status_code=500)

@frappe.whitelist(allow_guest=True)
def get_scheme_meta(scheme_name: str):
    logger.info(f"Getting scheme meta for {scheme_name}")
    try:
        return AnupratiSchemeManager().get_scheme_meta().to_custom_response()
    except Exception as e:
        logger.error(f"Error getting scheme meta: {e}")
        return custom_response(message=str(e), data=None, status_code=500)

@frappe.whitelist(allow_guest=True)
def get_data(jan_aadhar_id: str):
    logger.info(f"Getting data: {jan_aadhar_id}")
    try:
        file_path = frappe.get_app_path("usi", "jan_aadhar_data.json")
        with open(file_path, "r", encoding="utf-8") as f:
            jan_aadhar_data = json.load(f)
            for data in jan_aadhar_data:
                if data["jan_aadhar_id"] == jan_aadhar_id:
                    return custom_response(message="Data fetched successfully", data=data, status_code=200)
        return custom_response(message="Data not found", data=None, status_code=404)
    except Exception as e:
        frappe.log_error(f"Error getting application: {e}")
        return custom_response(message=str(e), data=None, status_code=500)

@frappe.whitelist(allow_guest=True)
def run_eligibility_check(application: dict):
    logger.info(f"Running eligibility check for {application}")
    try:
        return AnupratiSchemeManager().run_eligibility_check(application).to_custom_response()
    except Exception as e:
        logger.error(f"Error running eligibility check: {e}")
        return custom_response(message=str(e), data=None, status_code=500)