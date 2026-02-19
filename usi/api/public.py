# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import logging
import os

# Configure logging to write to a file in Frappe's logs directory
def setup_logger():
	"""Setup logger for rules engine - called lazily to ensure Frappe is initialized"""
	logger = logging.getLogger("usi.rules_engine")
	
	# Only setup if not already configured
	if logger.handlers:
		return logger
		
	try:
		log_dir = frappe.get_site_path("logs")
		if not os.path.exists(log_dir):
			os.makedirs(log_dir)
		
		log_file = os.path.join(log_dir, "rules_engine.log")
		logger.setLevel(logging.INFO)
		
		handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
		handler.setLevel(logging.INFO)
		formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
		handler.setFormatter(formatter)
		logger.addHandler(handler)
		
		# Force flush after each log
		original_emit = handler.emit
		def emit_with_flush(record):
			original_emit(record)
			handler.stream.flush()
		handler.emit = emit_with_flush
	except Exception:
		# If Frappe not initialized or other error, use basic logging
		logging.basicConfig(level=logging.INFO)
	
	return logger

# Get logger instance (will be configured on first use)
logger = None

def get_logger():
	"""Get logger instance, setting it up if needed"""
	global logger
	if logger is None:
		logger = setup_logger()
	return logger

@frappe.whitelist(allow_guest=True)
def get_schemes(filters=None, limit=20, offset=0):
	"""Get list of published scholarship schemes"""
	try:
		# Build filters
		query_filters = {"status": "Published"}
		
		# Apply additional filters if provided
		if filters:
			if isinstance(filters, str):
				import json
				filters = json.loads(filters)
			
			if filters.get("search"):
				query_filters["scheme_name"] = ["like", f"%{filters['search']}%"]
			
			if filters.get("category"):
				query_filters["scheme_category"] = filters["category"]
		
		# Get schemes
		schemes = frappe.get_all(
			"Scholarship Scheme",
			filters=query_filters,
			fields=["name", "scheme_name", "scheme_code", "scheme_objective", 
					"start_date", "end_date", "total_budget", "scheme_category", "scheme_type"],
			limit=limit,
			start=offset,
			order_by="modified desc"
		)
		
		# Get total count
		total = frappe.db.count("Scholarship Scheme", query_filters)
		
		return {
			"schemes": schemes,
			"total": total
		}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Schemes Error")
		return {"schemes": [], "total": 0}


@frappe.whitelist(allow_guest=True)
def get_scheme_detail(scheme_name):
	"""Get detailed information about a specific scheme"""
	try:
		if not scheme_name:
			return None
		
		# Get scheme details
		scheme = frappe.get_doc("Scholarship Scheme", scheme_name)
		
		# Get eligibility criteria if exists
		eligibility = frappe.db.get_value(
			"Scheme Eligibility Criteria",
			{"scheme": scheme_name, "is_active": 1},
			["eligibility_rule_json", "rule_version"],
			as_dict=True
		)
		
		# Get document requirements
		doc_requirements = frappe.get_all(
			"Scheme Document Requirements",
			filters={"scheme": scheme_name},
			fields=["document_type", "is_mandatory", "is_conditional", "condition_description"]
		)
		
		scheme_dict = scheme.as_dict()
		scheme_dict["eligibility_criteria"] = eligibility
		scheme_dict["document_requirements"] = doc_requirements
		
		return scheme_dict
	except frappe.DoesNotExistError:
		return None
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Scheme Detail Error")
		return None


@frappe.whitelist(allow_guest=True)
def get_public_stats():
	"""Get public statistics for homepage"""
	try:
		# Get total published schemes
		total_schemes = frappe.db.count("Scholarship Scheme", {"status": "Published"})
		
		# Get total beneficiaries (approved or disbursed applications)
		# Try disbursed first, fall back to approved if disbursed doesn't exist
		try:
			total_beneficiaries = frappe.db.count(
				"Scholarship Application", 
				{"application_status": "Disbursed"}
			)
		except:
			# If disbursed status doesn't exist, use approved
			try:
				total_beneficiaries = frappe.db.count(
					"Scholarship Application", 
					{"application_status": "Approved"}
				)
			except:
				# If neither exists, just count all applications
				total_beneficiaries = frappe.db.count("Scholarship Application")
		
		# Get total funds disbursed
		# Check if Disbursement Record table exists
		funds_disbursed = 0
		try:
			funds_result = frappe.db.sql("""
				SELECT SUM(disbursement_amount) 
				FROM `tabDisbursement Record` 
				WHERE disbursement_status = 'Processed'
			""")
			funds_disbursed = funds_result[0][0] if funds_result and funds_result[0][0] else 0
		except:
			# If table doesn't exist, set to 0
			funds_disbursed = 0
		
		# Get districts covered (from institutions)
		# Check if Institution Master table exists
		districts_covered = 0
		try:
			districts_result = frappe.db.sql("""
				SELECT COUNT(DISTINCT district) 
				FROM `tabInstitution Master` 
				WHERE is_active = 1 AND district IS NOT NULL
			""")
			districts_covered = districts_result[0][0] if districts_result and districts_result[0][0] else 0
		except:
			# If table doesn't exist, try to get from Applicant addresses or set to 0
			try:
				districts_result = frappe.db.sql("""
					SELECT COUNT(DISTINCT district) 
					FROM `tabApplicant` 
					WHERE district IS NOT NULL AND district != ''
				""")
				districts_covered = districts_result[0][0] if districts_result and districts_result[0][0] else 0
			except:
				districts_covered = 0
		
		stats = {
			"total_schemes": total_schemes or 0,
			"total_beneficiaries": total_beneficiaries or 0,
			"funds_disbursed": f"₹{funds_disbursed:,.0f}" if funds_disbursed else "₹0",
			"districts_covered": districts_covered or 0
		}
		
		return stats
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Public Stats Error")
		# Return default values on error, but try to at least get schemes count
		try:
			schemes_count = frappe.db.count("Scholarship Scheme", {"status": "Published"}) or 0
		except:
			schemes_count = 0
		return {
			"total_schemes": schemes_count,
			"total_beneficiaries": 0,
			"funds_disbursed": "₹0",
			"districts_covered": 0
		}


@frappe.whitelist(allow_guest=True)
def get_academic_years():
	"""Get list of active academic years"""
	try:
		years = frappe.get_all(
			"Academic Year",
			filters={"is_active": 1},
			fields=["name", "academic_year", "start_date", "end_date"],
			order_by="start_date desc"
		)
		return {"academic_years": years}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Academic Years Error")
		return {"academic_years": []}


@frappe.whitelist(allow_guest=True)
def get_institutions():
	"""Get list of active institutions"""
	try:
		institutions = frappe.get_all(
			"Institution Master",
			filters={"is_active": 1},
			fields=["name", "institution_name", "institution_type", "district", "state"],
			order_by="institution_name"
		)
		return {"institutions": institutions}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Institutions Error")
		return {"institutions": []}


@frappe.whitelist(allow_guest=True)
def check_application_status(application_number=None, aadhaar_number=None):
	"""Check application status by application number or Aadhaar"""
	try:
		if not application_number and not aadhaar_number:
			return None
		
		# Build filters
		filters = {}
		app_name = None
		
		if application_number:
			# Try searching by application_number field first
			filters["application_number"] = application_number
			
			# Also try searching by document name (in case application_number field is not set)
			# The document name might be the application number itself
			app_name = application_number.strip()
		
		# If searching by Aadhaar, first find applicant
		if aadhaar_number:
			applicant = frappe.db.get_value(
				"Applicant",
				{"aadhaar_number": aadhaar_number},
				"name"
			)
			if applicant:
				filters["applicant"] = applicant
			else:
				return None
		
		# Get application - try by filters first
		application = frappe.get_all(
			"Scholarship Application",
			filters=filters,
			fields=["*"],
			limit=1
		)
		
		# If not found and we have an app_name, try searching by document name
		if not application and app_name:
			try:
				# Check if document exists with this name
				if frappe.db.exists("Scholarship Application", app_name):
					app_doc = frappe.get_doc("Scholarship Application", app_name)
					app_dict = app_doc.as_dict()
					application = [app_dict]
			except:
				pass
		
		# If still not found, try case-insensitive search on application_number
		if not application and application_number:
			# Get all applications and filter in Python (less efficient but more flexible)
			all_apps = frappe.get_all(
				"Scholarship Application",
				fields=["name", "application_number", "applicant", "scheme", "application_status"],
				limit=1000  # Reasonable limit
			)
			for app in all_apps:
				# Check if application_number matches (case-insensitive)
				if app.get("application_number") and app.get("application_number").upper() == application_number.upper():
					application = [app]
					break
				# Also check if document name matches
				if app.get("name") and app.get("name").upper() == application_number.upper():
					application = [app]
					break
		
		if application:
			app = application[0]
			
			# Get applicant details
			if app.get("applicant"):
				try:
					applicant_details = frappe.get_doc("Applicant", app["applicant"])
					app["applicant_name"] = applicant_details.applicant_name
				except:
					app["applicant_name"] = app.get("applicant", "-")
			
			# Get scheme details
			if app.get("scheme"):
				try:
					scheme_details = frappe.get_doc("Scholarship Scheme", app["scheme"])
					app["scheme_name"] = scheme_details.scheme_name
				except:
					app["scheme_name"] = app.get("scheme", "-")
			
			# Ensure application_number is set (use document name if field is empty)
			if not app.get("application_number") and app.get("name"):
				app["application_number"] = app["name"]
			
			return {"application": app}
		
		return None
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Check Application Status Error")
		return None


@frappe.whitelist(allow_guest=True)
def find_matching_schemes(gender=None, date_of_birth=None, caste_category=None, income_group=None, disability_status=None, religion=None):
	"""Find matching scholarship schemes based on basic applicant details (all fields optional)"""
	try:
		from usi.engine.rules_engine import RulesEngine
		get_logger().info(f"find_matching_schemes called: gender={gender}, date_of_birth={date_of_birth}, caste_category={caste_category}, income_group={income_group}, disability_status={disability_status}, religion={religion}")
		# Normalize empty strings to None (handle both None and empty strings)
		if gender and isinstance(gender, str):
			gender = gender.strip() if gender.strip() else None
		elif not gender:
			gender = None
			
		if date_of_birth and isinstance(date_of_birth, str):
			date_of_birth = date_of_birth.strip() if date_of_birth.strip() else None
		elif not date_of_birth:
			date_of_birth = None
			
		if caste_category and isinstance(caste_category, str):
			caste_category = caste_category.strip() if caste_category.strip() else None
		elif not caste_category:
			caste_category = None
		
		if income_group and isinstance(income_group, str):
			income_group = income_group.strip() if income_group.strip() else None
		elif not income_group:
			income_group = None
		
		if disability_status and isinstance(disability_status, str):
			disability_status = disability_status.strip() if disability_status.strip() else None
		elif not disability_status:
			disability_status = None
		
		if religion and isinstance(religion, str):
			religion = religion.strip() if religion.strip() else None
		elif not religion:
			religion = None
		
		# Check if at least one field is provided
		has_gender = bool(gender)
		has_dob = bool(date_of_birth)
		has_caste = bool(caste_category)
		has_income = bool(income_group)
		has_disability = bool(disability_status)
		has_religion = bool(religion)
		
		if not has_gender and not has_dob and not has_caste and not has_income and not has_disability and not has_religion:
			return {
				"schemes": [],
				"message": "Please provide at least one criteria"
			}
		
		# Get all published schemes
		schemes = frappe.get_all(
			"Scholarship Scheme",
			filters={"status": "Published"},
			fields=["name", "scheme_name", "scheme_code", "scheme_objective", 
					"scheme_category", "scheme_type", "start_date", "end_date"],
			order_by="scheme_name"
		)
		
		if not schemes:
			return {
				"schemes": [],
				"message": "No published schemes found"
			}
		
		# Prepare applicant data for eligibility check (only include provided fields)
		applicant_data = {}
		if has_gender:
			applicant_data["gender"] = gender
		if has_dob:
			applicant_data["date_of_birth"] = date_of_birth
		if has_caste:
			applicant_data["caste_category"] = caste_category
		if has_income:
			applicant_data["income_group"] = income_group
		if has_disability:
			applicant_data["disability_status"] = disability_status
		if has_religion:
			applicant_data["religion"] = religion
		
		# Check eligibility for each scheme
		matching_schemes = []
		for scheme in schemes:
			try:
				# Initialize rules engine for this scheme
				engine = RulesEngine(scheme.name)
				
				# Skip schemes that don't have any rules configured
				if not engine.rules.get("critical") and not engine.rules.get("optional"):
					# No rules configured, skip this scheme
					continue
				
				# Evaluate eligibility with partial data
				result = engine.evaluate(applicant_data, {})
				
				# Include all schemes (eligible and partially eligible) with proximity scores
				# Extract failed rules information
				failed_critical = result.get("critical_failed", [])
				failed_optional = result.get("optional_failed", [])
				
				# Build list of failed rules with messages
				failed_rules = []
				for rule in failed_critical:
					failed_rules.append({
						"rule_name": rule.get("rule_name", "Unknown Rule"),
						"message": rule.get("message", "Rule failed"),
						"priority": "Critical"
					})
				for rule in failed_optional:
					failed_rules.append({
						"rule_name": rule.get("rule_name", "Unknown Rule"),
						"message": rule.get("message", "Rule failed"),
						"priority": "Optional"
					})
				
				# Skip schemes with 0% match
				proximity_score = result.get("proximity_score", 0) * 100
				if proximity_score <= 0:
					continue
				
				# Determine eligibility status
				if result.get("eligible", False):
					eligibility_status = "Eligible"
					match_reason = "Meets all eligibility criteria"
				else:
					eligibility_status = "Partially Eligible"
					critical_failed_count = len(failed_critical)
					if critical_failed_count > 0:
						match_reason = f"Does not meet {critical_failed_count} critical requirement(s)"
					else:
						match_reason = f"Matches {proximity_score:.0f}% of criteria"
				
				matching_schemes.append({
					"name": scheme.name,  # Include scheme ID for linking
					"scheme_name": scheme.scheme_name,
					"scheme_code": scheme.scheme_code,
					"scheme_category": scheme.scheme_category,
					"scheme_type": scheme.scheme_type,
					"scheme_objective": scheme.scheme_objective,
					"start_date": scheme.start_date,
					"end_date": scheme.end_date,
					"eligibility_status": eligibility_status,
					"eligibility_score": round(proximity_score, 1),
					"match_reason": match_reason,
					"failed_rules": failed_rules,
					"critical_passed": result.get("critical_passed", 0),
					"critical_failed_count": len(failed_critical),
					"optional_passed": len(result.get("optional_passed", [])),
					"optional_failed_count": len(failed_optional)
				})
			except Exception as e:
				# If evaluation fails, skip this scheme (don't add to results)
				frappe.log_error(f"Error evaluating scheme {scheme.name}: {str(e)}", "Find Matching Schemes Error")
				continue
		# Sort by eligibility score (highest first), then by scheme name
		matching_schemes.sort(key=lambda x: (
			x.get("eligibility_score") if x.get("eligibility_score") is not None else -1,
			x["scheme_name"]
		), reverse=True)
		
		# Build message based on provided criteria
		provided_criteria = []
		if has_gender:
			provided_criteria.append("gender")
		if has_dob:
			provided_criteria.append("date of birth")
		if has_caste:
			provided_criteria.append("caste category")
		if has_income:
			provided_criteria.append("income group")
		if has_disability:
			provided_criteria.append("disability")
		if has_religion:
			provided_criteria.append("religion")
		
		criteria_text = ", ".join(provided_criteria)
		message = f"Found {len(matching_schemes)} matching scheme(s) based on {criteria_text}"
		
		return {
			"schemes": matching_schemes,
			"total": len(matching_schemes),
			"message": message
		}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Find Matching Schemes Error")
		return {
			"schemes": [],
			"total": 0,
			"message": f"Error finding matching schemes: {str(e)}"
		}


@frappe.whitelist(allow_guest=True)
def get_youtube_videos(limit=3):
	"""Get active YouTube videos for homepage"""
	try:
		videos = frappe.get_all(
			"YouTube Video",
			filters={"is_active": 1},
			fields=["name", "video_title", "youtube_url", "description", "display_order"],
			order_by="display_order asc, creation desc",
			limit=limit or 3
		)
		
		# Extract video ID from URL for embedding
		for video in videos:
			url = video.get("youtube_url", "")
			video_id = None
			
			# Handle different YouTube URL formats
			if "youtube.com/watch?v=" in url:
				video_id = url.split("v=")[1].split("&")[0]
			elif "youtu.be/" in url:
				video_id = url.split("youtu.be/")[1].split("?")[0]
			elif "youtube.com/embed/" in url:
				video_id = url.split("embed/")[1].split("?")[0]
			
			video["video_id"] = video_id
			video["embed_url"] = f"https://www.youtube.com/embed/{video_id}" if video_id else None
		
		return {"videos": videos}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get YouTube Videos Error")
		return {"videos": []}


@frappe.whitelist(allow_guest=True)
def get_testimonials(limit=10):
	"""Get active testimonials for homepage"""
	try:
		testimonials = frappe.get_all(
			"Testimonial",
			filters={"is_active": 1},
			fields=["name", "person_name", "photo", "testimonial", "designation", "institution", "display_order"],
			order_by="display_order asc, creation desc",
			limit=limit or 10
		)
		
		# Get full testimonial content (Text Editor field)
		for testimonial in testimonials:
			try:
				doc = frappe.get_doc("Testimonial", testimonial["name"])
				testimonial["testimonial"] = doc.testimonial
				# Remove document name/ID from testimonial if it somehow got included
				if testimonial.get("name") and testimonial.get("testimonial"):
					# Remove any reference to the document name/ID
					testimonial["testimonial"] = testimonial["testimonial"].replace(testimonial["name"], "").strip()
			except:
				pass
		
		# Remove 'name' field from response to avoid any ID display
		for testimonial in testimonials:
			if "name" in testimonial:
				del testimonial["name"]
		
		# Get full file URLs for photos
		for testimonial in testimonials:
			if testimonial.get("photo"):
				testimonial["photo_url"] = frappe.utils.get_url(testimonial["photo"])
			else:
				testimonial["photo_url"] = None
		
		return {"testimonials": testimonials}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Testimonials Error")
		return {"testimonials": []}


@frappe.whitelist(allow_guest=True)
def get_government_authorities(limit=20):
	"""Get active government authorities for homepage"""
	try:
		authorities = frappe.get_all(
			"Government Authority",
			filters={"is_active": 1},
			fields=["name", "person_name", "photo", "designation", "department", "contact_email", "display_order"],
			order_by="display_order asc, creation desc",
			limit=limit or 20
		)
		
		# Get full file URLs for photos
		for authority in authorities:
			if authority.get("photo"):
				authority["photo_url"] = frappe.utils.get_url(authority["photo"])
			else:
				authority["photo_url"] = None
		
		return {"authorities": authorities}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Government Authorities Error")
		return {"authorities": []}

