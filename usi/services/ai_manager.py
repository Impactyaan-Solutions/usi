from usi.models.result import Result
import json
from pathlib import Path
import frappe
from openai import OpenAI
import re
import traceback
from functools import lru_cache
class AIManager:
    _client: OpenAI | None = None
    
    
    @classmethod
    def get_chatbot_answer(
        cls, 
        question: str, 
        application_status: object | None = None,
        chat_history_messages: list[dict[str, str]] | None = None,
        faq_text: str | None = None,
        active_scheme: str | None = None,
        session_id: str | None = None,
        status_response_rules: str | None = None,
        vocabulary_rules: str | None = None,
        ) -> Result:
        try:
            system_prompt = cls._read_text_file("system_prompt.md")
            history_msgs = chat_history_messages if isinstance(chat_history_messages, list) else []

            safe_history_msgs: list[dict[str, str]] = []
            for m in history_msgs:
                if not isinstance(m, dict):
                    continue
                role = (m.get("role") or "").lower()
                if role not in {"user", "assistant"}:
                    continue
                safe_history_msgs.append({"role": role, "content": (m.get("content") or "")})

            try:
                status_json = json.dumps(application_status, ensure_ascii=False)
            except Exception:
                status_json = json.dumps(str(application_status), ensure_ascii=False)
            scheme_label = active_scheme if active_scheme in ["Scholarship", "Pension"] else "Unknown"
            faq_block = faq_text or ""

            messages = [
                {"role": "system", "content": system_prompt+ """

                        Return your response strictly in JSON format:

                        {
                        "user_response": "<final response to show the user>",
                        "internal_reasoning": "<short explanation for system logs only>"
                        }

                        Rules:
                        - user_response must follow all formatting and language rules above.
                        - internal_reasoning must NOT appear inside user_response.
                        - internal_reasoning is for system logging only.
                        """
                },
                {
                    "role": "system",
                    "content": (
                        "ActiveScheme:\n"
                        f"{scheme_label}\n\n"
                        "BEGIN_FAQ\n"
                        f"{faq_block}\n"
                        "END_FAQ\n\n"
                        "BEGIN_APPLICATION_STATUS_DATA_JSON\n"
                        f"{status_json}\n"
                        "END_APPLICATION_STATUS_DATA_JSON\n\n"
                        "BEGIN_STATUS_RESPONSE_RULES\n"
                        f"{status_response_rules}\n"
                        "END_STATUS_RESPONSE_RULES\n\n"
                        "BEGIN_VOCABULARY_RULES\n"
                        f"{vocabulary_rules}\n"
                        "END_VOCABULARY_RULES\n\n"
                    ),
                },
                *safe_history_msgs,
                {"role": "user", "content": question},
            ]

            # Optional: log what we send to the model (safe preview by default).
            # Enable via site_config.json: USI_DEBUG_LLM_MESSAGES = 1
            chat_prompt_doc = frappe.get_doc(
                {
                    "doctype": "Chat Prompts",
                    "prompt": json.dumps(messages),
                    "session_id": session_id,
                }
            )
            chat_prompt_doc.insert(ignore_permissions=True)  

            response = cls._get_client().chat.completions.create(
                model="grok-4-1-fast-reasoning",
                messages=messages,
                temperature=0.2,
            )
            raw_content = response.choices[0].message.content

            try:
                parsed = json.loads(raw_content)
                user_answer = parsed.get("user_response", "")
                internal_reasoning = parsed.get("internal_reasoning", "")
            except Exception:
                # fallback in case model returns plain text
                user_answer = raw_content
                internal_reasoning = "Parsing failed — model did not return JSON."
            answer = {
                "user_response": user_answer,
                "internal_reasoning": internal_reasoning
            }
            return Result.success(message="Chatbot answer fetched successfully", data=answer)
        except Exception as e:
            frappe.log_error(
                title="Error in get_chatbot_answer",
                message=traceback.format_exc()
            )
            return Result.failure(message="Failed to get chatbot answer", error_data=traceback.format_exc())
    

    @staticmethod
    @lru_cache(maxsize=64)
    def _read_text_file(filename: str) -> str:
        # Robust path resolution (never relative to /usi/api)
        app_root = Path(frappe.get_app_path("usi"))
        path = app_root / "prompt" / filename
        return path.read_text(encoding="utf-8")
    
    @classmethod
    def _get_xai_api_key(cls) -> str | None:
        # Prefer site_config.json; fallback to frappe.conf
        key = frappe.get_site_config().get("XAI_API_KEY")
        if not key:
            frappe.throw("Missing `XAI_API_KEY` in site_config.json.")
            frappe.log_error(
                title="Error in _get_xai_api_key",
                message="Missing `XAI_API_KEY` in site_config.json."
            )
            return None 
        return key

    @classmethod
    def _get_client(cls) -> OpenAI:
        """Create OpenAI-compatible client lazily (x.ai)."""
        if cls._client is not None:
            return cls._client
        
        api_key = cls._get_xai_api_key()
        if not api_key:
            frappe.throw("Missing `XAI_API_KEY` in site_config.json.")

        cls._client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        return cls._client

    @classmethod
    def classify_message(cls, question: str) -> Result:
        try:
            question_clean = question.strip()

            full_id_match = re.fullmatch(r"\d{6,8}", question_clean)
            if full_id_match:
                return Result.success(
                    message="Classification successful (regex shortcut)",
                    data={
                        "scheme": "Unknown",
                        "intent": "STATUS",
                        "application_id": question_clean,
                        "explicit_switch": "No",
                        "decision_summary": "Message contains only numeric application ID.",
                        "signals_detected": [question_clean],
                        "confidence": "HIGH",
                    },
                )

            CLASSIFIER_PROMPT = cls._read_text_file("intent_prompt.md")

            response = cls._get_client().chat.completions.create(
                model="grok-4-1-fast-reasoning",
                temperature=0,
                messages=[
                    {"role": "system", "content": CLASSIFIER_PROMPT},
                    {"role": "user", "content": question_clean},
                ],
            )

            raw_content = response.choices[0].message.content.strip()

            try:
                result = json.loads(raw_content)
            except Exception:
                frappe.log_error(
                    title="Classifier JSON Parse Error",
                    message=f"Raw response:\n{raw_content}\n\n{traceback.format_exc()}",
                )
                return Result.failure(
                    message="Classifier returned invalid JSON",
                    error_data=raw_content,
                )

            # --------------------------------------------------
            # Embedded ID Fallback (if model missed it)
            # --------------------------------------------------
            if not result.get("application_id"):
                embedded_match = re.search(r"\b\d{6,8}\b", question_clean)
                if embedded_match:
                    result["application_id"] = embedded_match.group()
                    result["intent"] = "STATUS"

            result = cls.normialize_result(result)


            return Result.success(
                message="Classification successful",
                data=result,
            )

        except Exception:
            frappe.log_error(
                title="Error in classify_message",
                message=traceback.format_exc(),
            )
            return Result.failure(
                message="Failed to classify message",
                error_data=traceback.format_exc(),
            )
    
    @staticmethod
    def normialize_result(result: dict) -> dict:

        required_fields = {
            "scheme": "Unknown",
            "intent": "GENERAL",
            "application_id": None,
            "explicit_switch": "No",
            "decision_summary": "",
            "signals_detected": [],
            "confidence": "LOW",
        }

        # Step 1️⃣ Ensure keys exist and not None
        for key, default in required_fields.items():
            if key not in result or result[key] is None:
                result[key] = default

        # Step 2️⃣ Enforce allowed values (strict safety)

        if result["scheme"] not in ["Scholarship", "Pension", "Unknown"]:
            result["scheme"] = "Unknown"

        if result["intent"] not in ["STATUS", "GENERAL"]:
            result["intent"] = "GENERAL"

        if result["confidence"] not in ["HIGH", "MEDIUM", "LOW"]:
            result["confidence"] = "LOW"

        if result["explicit_switch"] not in ["Yes", "No"]:
            result["explicit_switch"] = "No"

        # Step 3️⃣ Ensure application_id is valid 6–7 digit string
        if result["application_id"]:
            if not re.fullmatch(r"\d{6,8}", str(result["application_id"])):
                result["application_id"] = None

        # Step 4️⃣ Ensure signals_detected is list (max 5 items)
        if not isinstance(result["signals_detected"], list):
            result["signals_detected"] = []
        else:
            result["signals_detected"] = result["signals_detected"][:5]

        # Step 5️⃣ Ensure decision_summary is short string
        if not isinstance(result["decision_summary"], str):
            result["decision_summary"] = ""
        else:
            result["decision_summary"] = result["decision_summary"][:200]
        return result