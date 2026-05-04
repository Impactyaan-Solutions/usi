import frappe
from functools import lru_cache
from pathlib import Path
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
		url = None

		req = getattr(frappe.local, "request", None)

		if req:
			if hasattr(req, "headers"):
				request_headers = dict(req.headers)
			if hasattr(req, "url"):
				url = req.url
		
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
	except Exception as e:
		error_title = error_title or service_name
		frappe.log_error(f"Error logging Integration Request: {str(e)}", f"{error_title} Integration Request Error")

@lru_cache(maxsize=64)
def read_text_file(filename: str) -> str:
	# Robust path resolution (never relative to /usi/api)
	app_root = Path(frappe.get_app_path("usi"))
	path = app_root/ filename
	return path.read_text(encoding="utf-8")


import re

def _normalize(msg: str) -> str:
    msg = (msg or "").strip().lower()

    # normalize spaces
    msg = re.sub(r"\s+", " ", msg)

    # remove punctuation except Hindi
    msg = re.sub(r"[^\w\s\u0900-\u097F]", "", msg)

    # collapse repeated characters (heyyyy -> heyy)
    msg = re.sub(r"(.)\1{2,}", r"\1\1", msg)

    return msg

def is_small_talk(message: str) -> bool:
    msg = _normalize(message)
    tokens = msg.split()

    greetings = {
		"hi", "hii", "hiii",
		"hey", "heyy",
		"hello", "helo", "helloo", "heello",
		"hlo", "hloo", "hllo",
		"hy", "hyy", "hyyy",
		"hio", "hilo", "halli", "helli",
		"halo", "hye", "hay", "haii",

		"namaste", "नमस्ते",
		"namaskar", "नमस्कार",
		"namaskaram",

		"jai hind",
		"ram ram",
		"pranam", "pranaam",

		"हाय", "हेलो",

		"समाधान साथी",
		"hilllo"
	}

    thanks = {
        "thanks", "thank you", "thx", "ty",
        "धन्यवाद", "shukriya",
    }

    polite_phrases = {
        "good morning", "good evening", "good afternoon",
        "gm", "ge", "ga",
        "how are you", "how are you doing",
        "kaise ho", "kya haal", "aur batao",
        "आप कैसे हैं",
    }

    all_phrases = greetings | thanks | polite_phrases

    # ---- CASE 1: exact match ----
    if msg in all_phrases:
        return True

    # ---- CASE 2: single-word fuzzy ----
    if len(tokens) == 1:
        word = tokens[0]

        if (
            re.fullmatch(r"h+i+", word) or
            re.fullmatch(r"he+y+", word) or
            re.fullmatch(r"he*l+o+", word)
        ):
            return True

    # ---- CASE 3: multi-word (safe matching) ----
    if len(tokens) <= 4:
        for phrase in all_phrases:
            # match full words only
            if re.search(rf"\b{re.escape(phrase)}\b", msg):
                return True

    return False