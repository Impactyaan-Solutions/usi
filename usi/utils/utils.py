import frappe

def log_integration_request(request_data, response_data, service_name, request_description, error_data=None, reference_doctype=None, reference_docname=None, error_title=None):
	"""
	Generic method to log API requests to Integration Request doctype.
	
	Args:
		request_data (dict): Request data to log
		response_data (dict): Response data containing message, status, data, status_code
		service_name (str): Name of the integration service (e.g., "Event Checkin API", "Add User API")
		request_description (str): Description of the request (e.g., "Event checkin via API")
		error_data (dict, optional): Error data if request failed
		reference_doctype (str, optional): Reference doctype name
		reference_docname (str, optional): Reference document name
		error_title (str, optional): Title for error logging (defaults to service_name)
	"""
	try:
		request_headers = {}
		if hasattr(frappe.request, 'headers'):
			request_headers = dict(frappe.request.headers)
		
		url = None
		if hasattr(frappe.request, 'url'):
			url = frappe.request.url
		
		response_output = response_data if isinstance(response_data, dict) else {}
		
		integration_request = frappe.get_doc({
			"doctype": "Integration Request",
			"integration_request_service": service_name,
			"is_remote_request": 0,
			"url": url,
			"request_headers": frappe.as_json(request_headers) if request_headers else "",
			"data": frappe.as_json(request_data) if request_data else "",
			"output": frappe.as_json(response_output) if response_output else "",
			"error": frappe.as_json(error_data) if error_data else "",
			"status": "Completed" if not error_data else "Failed",
			"reference_doctype": reference_doctype,
			"reference_docname": reference_docname,
			"request_description": request_description,
		})
		integration_request.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception as e:
		error_title = error_title or service_name
		frappe.log_error(f"Error logging Integration Request: {str(e)}", f"{error_title} Integration Request Error")