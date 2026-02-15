from __future__ import annotations

from pathlib import Path

import frappe

_client = None
_context_cache = None
import re


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
		"candidates": _read_chat_file("candidates.json"),
	}
	return _context_cache


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
def get_chatbot_answer(question: str):
	question = (question or "").strip()
	if not question:
		return {"status": "error", "answer": "Please enter a question."}

	ctx = _get_context()

	response = _get_client().chat.completions.create(
		model="grok-4-1-fast-reasoning",
		messages=[
			{"role": "system", "content": ctx["system_prompt"]},
			{
				"role": "user",
				"content": (
					f"FAQ:\n{ctx['faq']}\n\nCandidates:\n{ctx['candidates']}\n\nQuestion: {question}"
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

	result = get_chatbot_answer(message)
	reply = result.get("answer") or ""
	# Help markdown parser render lists: ensure blank line before list blocks
	reply_for_md = re.sub(r"([^\n])\n(-\s)", r"\1\n\n\2", reply)
	reply_for_md = re.sub(r"([^\n])\n(\d+\.\s)", r"\1\n\n\2", reply_for_md)
	reply_html = frappe.utils.markdown(reply_for_md, sanitize=True, linkify=True) if reply_for_md else ""
	return {"reply": reply, "reply_html": reply_html, "session_id": session_id}
