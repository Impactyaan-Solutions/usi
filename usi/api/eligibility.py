# Copyright (c) 2025, Indusaction and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now
from usi.engine.rules_engine import RulesEngine, compile_scheme_rules


@frappe.whitelist(allow_guest=True)
def evaluate_eligibility(application_name=None, scheme_name=None, applicant_data=None):
	"""Evaluate eligibility for an application or applicant data"""
	try:
		# Get scheme name
		if application_name:
			application = frappe.get_doc("Scholarship Application", application_name)
			scheme_name = application.scheme
			applicant_doc = frappe.get_doc("Applicant", application.applicant)
			applicant_dict = applicant_doc.as_dict()
			application_dict = application.as_dict()
		elif scheme_name and applicant_data:
			if isinstance(applicant_data, str):
				import json
				applicant_data = json.loads(applicant_data)
		else:
			frappe.throw("Either application_name or (scheme_name and applicant_data) must be provided")
		
		# Initialize rules engine
		from usi.engine.rules_engine import get_logger
		get_logger().info(f"=== evaluate_eligibility called: application_name={application_name}, scheme_name={scheme_name} ===")
		
		engine = RulesEngine(scheme_name)
		
		# Prepare applicant data (already set above if application_name)
		if not application_name:
			applicant_dict = applicant_data
			application_dict = None
		else:
			get_logger().info(f"Applicant DOB from doc: {applicant_dict.get('date_of_birth')}")
		
		# Evaluate
		get_logger().info(f"Calling engine.evaluate() with applicant_dict keys: {list(applicant_dict.keys()) if applicant_dict else 'None'}")
		result = engine.evaluate(applicant_dict, application_dict)
		get_logger().info(f"Evaluation complete. Eligible: {result.get('eligible')}, Critical passed: {result.get('critical_passed')}")
		
		# Store evaluation result if application exists
		if application_name:
			store_evaluation_result(application_name, scheme_name, result)
			
			# Also update the application's eligibility fields
			application = frappe.get_doc("Scholarship Application", application_name)
			application.eligibility_status = "Eligible" if result.get("eligible", False) else "Ineligible"
			application.eligibility_score = result.get("proximity_score", 0)
			
			# Store remarks
			if result.get("critical_failed"):
				failed_rules = [r.get("rule_name", "") for r in result.get("critical_failed", [])]
				application.eligibility_remarks = f"Failed critical rules: {', '.join(failed_rules)}"
			elif result.get("eligible"):
				application.eligibility_remarks = "All eligibility criteria met"
			else:
				application.eligibility_remarks = "Eligibility check completed"
			
			# Get rule version
			criteria = frappe.db.get_value(
				"Scheme Eligibility Criteria",
				{"scheme": scheme_name, "is_active": 1},
				"rule_version"
			)
			application.eligibility_version = criteria or "1.0"
			
			application.save(ignore_permissions=True)
		
		return result
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Eligibility Evaluation Error")
		frappe.throw(f"Error evaluating eligibility: {str(e)}")


@frappe.whitelist()
def get_eligibility_rules(scheme_name):
	"""Get all rules for a scheme (for display)"""
	try:
		configs = frappe.get_all(
			"Scheme Rule Configuration",
			filters={"scheme": scheme_name, "is_active": 1},
			fields=["name"]
		)
		
		rules = []
		for config_name in configs:
			config = frappe.get_doc("Scheme Rule Configuration", config_name.name)
			for rule_item in config.rules:
				if rule_item.is_active:
					rule_def = frappe.get_doc("Eligibility Rule Definition", rule_item.rule)
					rules.append({
						"name": f"{config.name}-{rule_item.idx}",
						"rule": rule_item.rule,
						"rule_priority": rule_item.rule_priority,
						"rule_order": rule_item.rule_order,
						"operator": rule_item.operator,
						"value": rule_item.value,
						"error_message": rule_item.error_message,
						"score_weight": rule_item.score_weight,
						"rule_name": rule_def.rule_name,
						"rule_type": rule_def.rule_type,
						"field_name": rule_def.field_name
					})
		
		# Sort by rule_order
		rules.sort(key=lambda x: x.get("rule_order", 0))
		
		# Get composite rules
		composite_rules = frappe.get_all(
			"Composite Rule",
			filters={"scheme": scheme_name, "is_active": 1},
			fields=["name", "composite_rule_name", "logic_operator", "is_critical", "rule_order"],
			order_by="rule_order"
		)
		
		return {
			"rules": rules,
			"composite_rules": composite_rules
		}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Eligibility Rules Error")
		return {"rules": [], "composite_rules": []}


@frappe.whitelist()
def test_rule(rule_name, test_data):
	"""Test a rule against sample data"""
	try:
		if isinstance(test_data, str):
			import json
			test_data = json.loads(test_data)
		
		rule_def = frappe.get_doc("Eligibility Rule Definition", rule_name)
		
		# Create a mock rule object
		rule_obj = {
			"rule_id": rule_name,
			"rule_name": rule_def.rule_name,
			"field_name": rule_def.field_name,
			"operator": rule_def.operator,
			"value": rule_def.value,
			"error_message": rule_def.error_message_template or ""
		}
		
		# Create a simple engine instance for testing
		engine = RulesEngine("")  # Empty scheme for testing
		
		# Evaluate
		result = engine.evaluate_rule(rule_obj, test_data)
		
		return result
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Test Rule Error")
		frappe.throw(f"Error testing rule: {str(e)}")


@frappe.whitelist()
def compile_rules(scheme_name):
	"""Manually compile rules for a scheme"""
	try:
		compiled = compile_scheme_rules(scheme_name)
		if compiled:
			frappe.msgprint("Rules compiled successfully")
			return compiled
		else:
			frappe.throw("Failed to compile rules")
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Compile Rules Error")
		frappe.throw(f"Error compiling rules: {str(e)}")


def _json_serialize(obj):
	"""Helper to serialize objects to JSON, handling dates and other non-serializable types"""
	from datetime import date, datetime
	from frappe.utils import formatdate, format_datetime
	
	if isinstance(obj, (date, datetime)):
		if isinstance(obj, datetime):
			return format_datetime(obj)
		else:
			return formatdate(obj)
	elif hasattr(obj, '__dict__'):
		return str(obj)
	else:
		return str(obj)

def store_evaluation_result(application_name, scheme_name, evaluation_result):
	"""Store evaluation result in Eligibility Evaluation Result DocType"""
	try:
		import json
		from datetime import date, datetime
		
		# Check if result already exists
		existing = frappe.db.get_value(
			"Eligibility Evaluation Result",
			{"application": application_name},
			"name"
		)
		
		# Get rule version
		criteria = frappe.db.get_value(
			"Scheme Eligibility Criteria",
			{"scheme": scheme_name, "is_active": 1},
			"rule_version"
		)
		rule_version = criteria or "1.0"
		
		# Prepare field values - convert lists to JSON strings for JSON fields
		# Use default=str to handle date objects and other non-serializable types
		critical_failed = evaluation_result.get("critical_failed", [])
		details = evaluation_result.get("details", [])
		critical_failed_json = json.dumps(critical_failed, default=_json_serialize) if critical_failed else "[]"
		details_json = json.dumps(details, default=_json_serialize) if details else "[]"
		# For evaluation_log (Code field), use JSON string
		evaluation_log_json = json.dumps(evaluation_result, default=_json_serialize, indent=2)
		
		if existing:
			# Update existing record using db_set to bypass validation
			frappe.db.set_value("Eligibility Evaluation Result", existing, {
				"overall_eligible": evaluation_result.get("eligible", False),
				"critical_rules_passed": evaluation_result.get("critical_passed", 0),
				"critical_rules_total": evaluation_result.get("critical_rules_total", 0),
				"optional_score": evaluation_result.get("optional_score", 0),
				"max_optional_score": evaluation_result.get("max_optional_score", 0),
				"proximity_score": evaluation_result.get("proximity_score", 0),
				"failed_critical_rules": critical_failed_json,
				"evaluation_details": details_json,
				"evaluation_log": evaluation_log_json,
				"evaluation_date": now(),
				"rule_version": rule_version
			}, update_modified=False)
			return existing
		else:
			# Create new record - create doc first without JSON fields
			result_doc = frappe.get_doc({
				"doctype": "Eligibility Evaluation Result",
				"application": application_name,
				"scheme": scheme_name,
				"overall_eligible": evaluation_result.get("eligible", False),
				"critical_rules_passed": evaluation_result.get("critical_passed", 0),
				"critical_rules_total": evaluation_result.get("critical_rules_total", 0),
				"optional_score": evaluation_result.get("optional_score", 0),
				"max_optional_score": evaluation_result.get("max_optional_score", 0),
				"proximity_score": evaluation_result.get("proximity_score", 0),
				"evaluation_date": now(),
				"rule_version": rule_version
			})
			# Set JSON fields after creation but before insert
			result_doc.failed_critical_rules = critical_failed_json
			result_doc.evaluation_details = details_json
			result_doc.evaluation_log = evaluation_log_json
			result_doc.insert(ignore_permissions=True)
			return result_doc.name
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Store Evaluation Result Error")
		# Don't throw, just log - eligibility check should not fail application submission

