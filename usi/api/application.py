# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now


@frappe.whitelist(allow_guest=True)
def submit_application(applicant_data, scheme, academic_year, institution=None):
	"""Submit a new scholarship application"""
	try:
		# Validate required fields
		if not applicant_data or not scheme or not academic_year:
			return {
				"success": False,
				"message": "Missing required fields: applicant_data, scheme, or academic_year"
			}
		
		# Parse applicant_data if it's a string
		if isinstance(applicant_data, str):
			import json
			applicant_data = json.loads(applicant_data)
		
		# Clean up empty strings - convert to None
		for key in applicant_data:
			if applicant_data[key] == "" or applicant_data[key] == "null" or applicant_data[key] == "undefined":
				applicant_data[key] = None
		
		# Validate applicant data
		if not applicant_data.get("applicant_name"):
			return {
				"success": False,
				"message": "Applicant name is required"
			}
		
		# Check if applicant exists, if not create
		applicant_name = None
		# Try to find by Aadhaar if provided
		if applicant_data.get("aadhaar_number"):
			aadhaar = applicant_data.get("aadhaar_number")
			if isinstance(aadhaar, str):
				aadhaar = aadhaar.strip()
			if aadhaar:
				applicant_name = frappe.db.get_value(
					"Applicant",
					{"aadhaar_number": aadhaar},
					"name"
				)
		# If not found by Aadhaar, try to find by mobile number if provided
		if not applicant_name and applicant_data.get("mobile_number"):
			mobile = applicant_data.get("mobile_number")
			if isinstance(mobile, str):
				mobile = mobile.strip()
			if mobile:
				applicant_name = frappe.db.get_value(
					"Applicant",
					{"mobile_number": mobile},
					"name"
				)
		# If still not found, try to find by email if provided
		if not applicant_name and applicant_data.get("email"):
			email = applicant_data.get("email")
			if isinstance(email, str):
				email = email.strip()
			if email:
				applicant_name = frappe.db.get_value(
					"Applicant",
					{"email": email},
					"name"
				)
		
		if not applicant_name:
			# Create new applicant
			# Only include aadhaar_number if it's provided and not empty
			applicant_dict = {
				"doctype": "Applicant",
				"naming_series": "APPL-.YYYY.-",
				"applicant_name": applicant_data.get("applicant_name"),
				"date_of_birth": applicant_data.get("date_of_birth"),
				"gender": applicant_data.get("gender"),
				"jan_aadhaar_id": applicant_data.get("jan_aadhaar_id") or "",
				"email": applicant_data.get("email") or "",
				"caste_category": applicant_data.get("caste_category") or "",
				"income_group": applicant_data.get("income_group") or "",
				"permanent_address": applicant_data.get("permanent_address") or "",
				"data_synced_from": "Manual"
			}
			
			# Only add optional fields if they have values
			aadhaar = applicant_data.get("aadhaar_number")
			if aadhaar:
				if isinstance(aadhaar, str):
					aadhaar = aadhaar.strip()
				if aadhaar:
					applicant_dict["aadhaar_number"] = aadhaar
			
			mobile = applicant_data.get("mobile_number")
			if mobile:
				if isinstance(mobile, str):
					mobile = mobile.strip()
				if mobile:
					applicant_dict["mobile_number"] = mobile
			
			# Add religion if provided
			if applicant_data.get("religion"):
				applicant_dict["religion"] = applicant_data.get("religion")
			
			applicant = frappe.get_doc(applicant_dict)
			applicant.insert()
			applicant_name = applicant.name
		else:
			# Update existing applicant if needed
			applicant = frappe.get_doc("Applicant", applicant_name)
			# Update fields if provided and different
			if applicant_data.get("mobile_number") and applicant.mobile_number != applicant_data.get("mobile_number"):
				applicant.mobile_number = applicant_data.get("mobile_number")
			if applicant_data.get("email") and applicant.email != applicant_data.get("email"):
				applicant.email = applicant_data.get("email")
			applicant.save()
		
		# Check if application already exists for this scheme and academic year
		existing_app = frappe.db.get_value(
			"Scholarship Application",
			{
				"applicant": applicant_name,
				"scheme": scheme,
				"academic_year": academic_year,
				"application_status": ["!=", "Rejected"]
			},
			"name"
		)
		
		if existing_app:
			return {
				"success": False,
				"message": "An application already exists for this scheme and academic year",
				"application_number": frappe.db.get_value("Scholarship Application", existing_app, "application_number")
			}
		
		# Create application
		application = frappe.get_doc({
			"doctype": "Scholarship Application",
			"applicant": applicant_name,
			"scheme": scheme,
			"academic_year": academic_year,
			"institution": institution or "",
			"application_status": "Submitted",
			"submitted_on": now(),
			"applied_amount": applicant_data.get("applied_amount", 0)
		})
		application.insert()
		
		# Reload to get application_number
		application.reload()
		
		# Check eligibility after application is created
		try:
			from usi.api.eligibility import evaluate_eligibility
			eligibility_result = evaluate_eligibility(application_name=application.name)
			
			# Update eligibility fields
			application.eligibility_status = "Eligible" if eligibility_result.get("eligible", False) else "Ineligible"
			application.eligibility_score = eligibility_result.get("proximity_score", 0)
			
			# Store remarks
			if eligibility_result.get("critical_failed"):
				failed_rules = [r.get("rule_name", "") for r in eligibility_result.get("critical_failed", [])]
				application.eligibility_remarks = f"Failed critical rules: {', '.join(failed_rules)}"
			elif eligibility_result.get("eligible"):
				application.eligibility_remarks = "All eligibility criteria met"
			else:
				application.eligibility_remarks = "Eligibility check completed"
			
			# Save eligibility results
			application.save()
		except Exception as e:
			# Log error but don't fail the submission
			frappe.log_error(frappe.get_traceback(), "Eligibility Check Error on Application Submit")
			application.eligibility_status = "Pending Clarification"
			application.eligibility_remarks = f"Error checking eligibility: {str(e)}"
			application.save()
		
		return {
			"success": True,
			"application_number": application.application_number or application.name,
			"application_name": application.name,
			"message": "Application submitted successfully",
			"eligibility_status": application.eligibility_status,
			"eligibility_score": application.eligibility_score
		}
	except frappe.ValidationError as e:
		return {
			"success": False,
			"message": str(e)
		}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Submit Application Error")
		return {
			"success": False,
			"message": f"Error submitting application: {str(e)}"
		}


@frappe.whitelist()
def get_user_applications():
	"""Get applications for logged-in user"""
	try:
		# Get applicant linked to current user
		# TODO: Link applicant to user when authentication is implemented
		# For now, try to find by email or get all if admin
		user = frappe.session.user
		
		if user == "Guest":
			return {"applications": []}
		
		# If System Manager, return all applications (for testing)
		# Otherwise, find applicant by user email
		if "System Manager" in frappe.get_roles():
			applications = frappe.get_all(
				"Scholarship Application",
				fields=["name", "application_number", "scheme", "application_status", 
						"submitted_on", "sanctioned_amount"],
				order_by="modified desc",
				limit=50
			)
		else:
			# Find applicant by user email
			applicant = frappe.db.get_value(
				"Applicant",
				{"email": user},
				"name"
			)
			
			if not applicant:
				return {"applications": []}
			
			applications = frappe.get_all(
				"Scholarship Application",
				filters={"applicant": applicant},
				fields=["name", "application_number", "scheme", "application_status", 
						"submitted_on", "sanctioned_amount"],
				order_by="modified desc"
			)
		
		# Add scheme names
		for app in applications:
			if app.scheme:
				scheme_name = frappe.db.get_value("Scholarship Scheme", app.scheme, "scheme_name")
				app["scheme_name"] = scheme_name
		
		return {"applications": applications}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get User Applications Error")
		return {"applications": []}

