from __future__ import annotations

from typing import List
from pathlib import Path

import frappe

_client = None
_context_cache = None
import json
import re
from typing import Any
from usi.models.chat import ChatHistory
import uuid
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
def get_chatbot_answer(
	question: str,
	application_status: dict | None = None,
	application_id: str | None = None,
	chat_history_messages: list[dict[str, str]] | None = None,
):
	question = (question or "").strip()
	if not question:
		return {"status": "error", "answer": "Please enter a question."}

	ctx = _get_context()
	status_context = "None"
	if application_id and not application_status:
		status_context = f"Not found for application_id={application_id}"
	elif application_status:
		status_context = json.dumps(application_status, ensure_ascii=False, indent=2)

	history_msgs = chat_history_messages if isinstance(chat_history_messages, list) else []

	response = _get_client().chat.completions.create(
		model="grok-4-1-fast-reasoning",
		messages=[
			{"role": "system", "content": ctx["system_prompt"]},
			{"role": "system", "content": f"FAQ:\n{ctx['faq']}\n\nApplication Status Data:\n{status_context}"},
			*history_msgs,
			{"role": "user", "content": question},
		],
		temperature=0.2,
	)

	answer = response.choices[0].message.content
	return {"status": "success", "answer": answer}


@frappe.whitelist(allow_guest=True)
def initate_chat(message: str | None = None, session_id: str | None = None, page: str | None = None):
	"""Endpoint used by the website chat widget."""
	message = (message or "").strip()
	if not message:
		return {"reply": "Please type a message so I can help.", "session_id": session_id}

	if not session_id:
		session_id = str(uuid.uuid4())
		last_sequence_number = 0
		chat_history_doc = ChatHistory(
			session_id=session_id,
			content=message,
			sequence_number=last_sequence_number + 1,
			role="user",
		)
		frappe.get_doc(
			{
				"doctype": "Chat History",
				**chat_history_doc.model_dump(),
			}
		).insert()
		frappe.db.commit()
		session_id = chat_history_doc.session_id
		chat_history_messages = [chat_history_doc]
	else:
		chat_history_messages = get_history(session_id)
		last_sequence_number = chat_history_messages[-1].sequence_number if chat_history_messages else 0
		
		chat_history_doc = ChatHistory(
				session_id=session_id,
				content=message,
				sequence_number=last_sequence_number + 1,
				role="user",
		)
		frappe.get_doc(
			{
				"doctype": "Chat History",
				**chat_history_doc.model_dump(),
			}
		).insert()
		frappe.db.commit()
		session_id = chat_history_doc.session_id
		chat_history_messages.append(chat_history_doc)


	result = extract_intent_and_id(message)
	intent = result.get("intent")
	application_id = result.get("application_id")

	if intent == "STATUS":
		if application_id:
			application_status = _fetch_application_status(application_id)
		else:
			return {"reply": "Please share your 6–7 digit application ID.", "session_id": session_id}

		result = get_chatbot_answer(
			message,
			application_status=application_status,
			application_id=application_id,
			chat_history_messages=chat_history_messages,
		)
		reply = result.get("answer") or ""
	else:
		result = get_chatbot_answer(message, chat_history_messages=chat_history_messages)
		reply = result.get("answer") or ""
	
	frappe.get_doc(
		{
				"doctype": "Chat History",
				"session_id": session_id,
				"role": "assistant",
				"content": reply,
				"sequence_number": last_sequence_number + 2,
			}
		).insert()
	frappe.db.commit()
	
	
	# Help markdown parser render lists: ensure blank line before list blocks
	reply_for_md = re.sub(r"([^\n])\n(-\s)", r"\1\n\n\2", reply)
	reply_for_md = re.sub(r"([^\n])\n(\d+\.\s)", r"\1\n\n\2", reply_for_md)
	reply_html = frappe.utils.markdown(reply_for_md, sanitize=True, linkify=True) if reply_for_md else ""
	return {"reply": reply, "reply_html": reply_html, "session_id": session_id}

def get_history(session_id: str) -> List[ChatHistory]:
        chat_history_messages = frappe.get_all(
            "Chat History",
            filters={"session_id": session_id},
            fields=[ "content", "role", "response_type", "sequence_number","session_id"],
            order_by="sequence_number asc",
        )
        return [
            ChatHistory(
                content=chat_history_message.get("content") or "",
                role=chat_history_message.get("role") or "",
                sequence_number=chat_history_message.get("sequence_number") or 0,
                session_id=chat_history_message.get("session_id") or "",
            )
            for chat_history_message in chat_history_messages
        ]

def extract_intent_and_id(message: str):

    is_applicaton_id =  bool(re.fullmatch(r"\d{6,7}", message.strip()))
    if is_applicaton_id:
        return {
            "intent": "STATUS",
            "application_id": message.strip(),
        }

    response = _get_client().chat.completions.create(
        model="grok-2-mini",
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": """
					You are a routing assistant for a government scheme chatbot.

					Tasks:
					1. Detect if the user wants to check application status.
					2. Extract a 6 or 7 digit application ID if present.

					Return ONLY valid JSON in this format:

					{
					"intent": "STATUS" or "GENERAL",
					"application_id": "string or null"
					}

					Rules:
					- If user is asking about application status → intent = STATUS
					- Otherwise → GENERAL
					- Extract only 6 or 7 digit numbers as application_id
					- If no ID present → application_id = null
					"""
            },
            {
                "role": "user",
                "content": message
            }
        ]
    )
    try:
        result = json.loads(response.choices[0].message.content) or {}
        if isinstance(result, dict):
            return result
        return {"intent": "GENERAL", "application_id": None}
    except Exception:
        return {"intent": "GENERAL", "application_id": None}