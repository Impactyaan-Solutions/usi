from __future__ import annotations

from pathlib import Path

import frappe

_client = None
_context_cache = None
import json
import re
from typing import Any
logger = frappe.logger("api", allow_site=True, file_count=50)

APPLICATION_ID_PATTERN = re.compile(r"\b\d{6,14}\b")
STATUS_INTENT_PATTERN = re.compile(
	r"\b(status|track|tracking|application\s*status|आवेदन\s*स्थिति|स्थिति|स्टेटस|ट्रैक)\b",
	re.IGNORECASE,
)
EXPLICIT_APP_ID_PATTERN = re.compile(
	r"\b(app\s*id|application\s*id|application\s*number|application\s*no|app\s*no)\b",
	re.IGNORECASE,
)
NON_STATUS_NUMBER_CONTEXT_PATTERN = re.compile(
	r"\b(phone|mobile|contact|otp|aadhaar|aadhar|bank|account)\b",
	re.IGNORECASE,
)
SJMS_STATUS_API_URL = "https://sjmsnew.rajasthan.gov.in/ScholarShipApi/api/Scholarship/ScholarShipStatus"


def _read_chat_file(filename: str) -> str:
	# Robust path resolution (never relative to /usi/api)
	app_root = Path(frappe.get_app_path("usi"))
	path = app_root / "chat_files" / filename
	return path.read_text(encoding="utf-8")


def _get_context() -> dict[str, str]:
	global _context_cache
	if _context_cache is not None:
		return _context_cache

	_context_cache = {
		"faq": _read_chat_file("FAQ.txt"),
		"system_prompt": _read_chat_file("prompt.md"),
	}
	return _context_cache


def _extract_application_id(message: str) -> str | None:
	"""Extract numeric application id from a user message."""
	if not message:
		return None

	matches = [(m.group(0), m.start()) for m in APPLICATION_ID_PATTERN.finditer(message)]
	if not matches:
		return None

	intent_positions = [m.start() for m in EXPLICIT_APP_ID_PATTERN.finditer(message)]
	if not intent_positions:
		return matches[0][0]

	best_dist = None
	best_num = None
	for num, pos in matches:
		dist = min(abs(pos - ipos) for ipos in intent_positions)
		if best_dist is None or dist < best_dist:
			best_dist = dist
			best_num = num

	return best_num or matches[0][0]


def _should_call_status_api(message: str) -> tuple[bool, str | None]:
	"""
	Call status API only if:
	- user mentions status/track OR explicitly says app/application id/number
	- a numeric application id is present in the same message
	"""
	msg = (message or "").strip()
	if not msg:
		return False, None
	logger.info(f"Message: {msg}")
	
	has_status_intent = bool(STATUS_INTENT_PATTERN.search(msg))
	has_explicit_id = bool(EXPLICIT_APP_ID_PATTERN.search(msg))
	app_id = _extract_application_id(msg)

	if not app_id:
		return False, None

	# If message clearly talks about phone/aadhaar/bank and doesn't mention status/id, don't treat number as app id.
	if not (has_status_intent or has_explicit_id) and NON_STATUS_NUMBER_CONTEXT_PATTERN.search(msg):
		return False, None

	logger.info(f"has_status_intent: {has_status_intent}")
	logger.info(f"has_explicit_id: {has_explicit_id}")
	logger.info(f"app_id: {app_id}")
	
	return (has_status_intent or has_explicit_id), app_id


def _fetch_application_status(application_id: str) -> dict | None:
	"""
	Fetch live application status from your backend.

	Uses SJMS API:
	POST https://sjmsnew.rajasthan.gov.in/ScholarShipApi/api/Scholarship/ScholarShipStatus?ScholarshipNumber=<id>

	We only return the *latest* status entry: data[0]
	"""
	if not application_id:
		return None
	try:
		# Allow overriding URL via site_config.json if needed
		site_config = frappe.get_site_config() or {}
		url = site_config.get("SJMS_STATUS_API_URL") or SJMS_STATUS_API_URL

		session = frappe.utils.get_request_session()
		params = {"ScholarshipNumber": application_id}

		# API is described as POST; some gateways accept either querystring or body.
		# We'll send both to maximize compatibility.
		res = session.post(
			url,
			params=params,
			json={"ScholarshipNumber": application_id},
			timeout=12,
		)
		res.raise_for_status()
		payload: dict[str, Any] = res.json() if res.content else {}

		if not payload.get("isSuccess"):
			return None

		rows = payload.get("data") or []
		if not isinstance(rows, list) or not rows:
			return None

		latest = rows[0] if isinstance(rows[0], dict) else None
		if not latest:
			return None

		# Return only the latest entry (plus the queried scholarship number for traceability)
		return {"scholarshipNumber": application_id, **latest}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Scholarship Assistant: status lookup failed")
	return None


def _get_xai_api_key() -> str | None:
	# Prefer site_config.json; fallback to frappe.conf
	site_config = frappe.get_site_config() or {}
	return (
		site_config.get("XAI_API_KEY")
		or site_config.get("xai_api_key")
		or frappe.conf.get("XAI_API_KEY")
		or frappe.conf.get("xai_api_key")
	)


def _get_client():
	"""Create OpenAI-compatible client lazily (x.ai)."""
	global _client
	if _client is not None:
		return _client

	try:
		from openai import OpenAI  # lazy import so method can resolve even if missing
	except ModuleNotFoundError:
		frappe.throw(
			"Python package `openai` is not installed in the bench environment. "
			"Run: `bench pip install -r apps/usi/requirements.txt`"
		)

	api_key = _get_xai_api_key()
	if not api_key:
		frappe.throw("Missing `XAI_API_KEY` in site_config.json.")

	_client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
	return _client


@frappe.whitelist(allow_guest=True)
def get_chatbot_status():
	return {"status": "running"}


@frappe.whitelist(allow_guest=True)
def get_chatbot_answer(question: str, application_status: dict | None = None, application_id: str | None = None):
	question = (question or "").strip()
	if not question:
		return {"status": "error", "answer": "Please enter a question."}

	ctx = _get_context()
	status_context = "None"
	if application_id and not application_status:
		status_context = f"Not found for application_id={application_id}"
	elif application_status:
		status_context = json.dumps(application_status, ensure_ascii=False, indent=2)

	response = _get_client().chat.completions.create(
		model="grok-4-1-fast-reasoning",
		messages=[
			{"role": "system", "content": ctx["system_prompt"]},
			{
				"role": "user",
				"content": (
					f"FAQ:\n{ctx['faq']}\n\nApplication Status Data:\n{status_context}\n\nQuestion: {question}"
				),
			},
		],
		temperature=0.2,
	)

	answer = response.choices[0].message.content
	return {"status": "success", "answer": answer}


@frappe.whitelist(allow_guest=True)
def initate_chat(message: str | None = None, session_id: str | None = None, page: str | None = None):
	"""Endpoint used by the website chat widget."""
	if not session_id:
		session_id = frappe.generate_hash(length=10)

	message = (message or "").strip()
	if not message:
		return {"reply": "Please type a message so I can help.", "session_id": session_id}

	# Best UX: if student enters only the number, treat it as ScholarshipNumber and fetch status.
	if re.fullmatch(r"\d{6,14}", message):
		should_lookup, application_id = True, message
	else:
		should_lookup, application_id = _should_call_status_api(message)
		# If we detected a number but there's no status/app-id intent, ask for a clearer message
		# to avoid false lookups on phone/aadhaar/bank numbers in free text.
		if application_id and not should_lookup:
			reply = (
				"To check status, please type like:\n"
				f"- app id {application_id}\n"
				f"- status {application_id}\n\n"
				'फ़ॉर्मेट संकेत: SCHOLARSHIP/2016-17/XXXXXX में से केवल XXXXXX (अंत वाले अंक) ही दर्ज करें।'
			)
			reply_html = frappe.utils.markdown(reply, sanitize=True, linkify=True)
			return {"reply": reply, "reply_html": reply_html, "session_id": session_id}

	application_status = _fetch_application_status(application_id) if (should_lookup and application_id) else None

	# Only pass application_id to the LLM when we actually attempted lookup (or have status),
	# otherwise the model may incorrectly claim "not found".
	llm_application_id = application_id if should_lookup else None
	result = get_chatbot_answer(message, application_status=application_status, application_id=llm_application_id)
	reply = result.get("answer") or ""
	# Help markdown parser render lists: ensure blank line before list blocks
	reply_for_md = re.sub(r"([^\n])\n(-\s)", r"\1\n\n\2", reply)
	reply_for_md = re.sub(r"([^\n])\n(\d+\.\s)", r"\1\n\n\2", reply_for_md)
	reply_html = frappe.utils.markdown(reply_for_md, sanitize=True, linkify=True) if reply_for_md else ""
	return {"reply": reply, "reply_html": reply_html, "session_id": session_id}
