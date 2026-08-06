from operator import is_
from typing import Any, Dict
import uuid
import frappe
from typing import List
import traceback
from usi.models.result import Result
import re
from usi.models.chat import ChatHistory
from usi.services.ai_manager import AIManager
from usi.services.scholarship_manager import ScholarshipManager
from usi.services.pension_manager import PensionManager
from usi.services.palanhaar_manager import PalanhaarManager
from usi.services.anuprati_manager import AnupratiManager
from usi.models.chat import ChatSession
import json
from usi.utils.utils import is_small_talk
from frappe.utils import logger
from rapidfuzz import fuzz
import re
from usi.services.chat.chat_constants import (
    ALLOWED_SCHEMES,
    ALLOWED_INTENTS,
    SCHEME_KEYWORDS,
)
from usi.services.chat.message_helper import send_welcome_message, send_intent_selection_message, send_intent_selection_message_on_scheme_change, send_general_query_prompt, send_application_id_prompt,status_lookup_error_response
from usi.services.chat.chat_history import update_chat_history, add_chat_history_message, update_session, get_or_create_chat_session_for_web,get_or_create_chat_session_for_whatsapp

logger.set_log_level("DEBUG")
logger = frappe.logger("api", allow_site=True, file_count=50)

class ChatManager:
    @staticmethod
    def _generate_response(message: str,session_id: str) -> Result:
        # Help markdown parser render lists: ensure blank line before list blocks
        reply_for_md = re.sub(r"([^\n])\n(-\s)", r"\1\n\n\2", message)
        reply_for_md = re.sub(r"([^\n])\n(\d+\.\s)", r"\1\n\n\2", reply_for_md)
        reply_html = frappe.utils.markdown(reply_for_md, sanitize=True, linkify=True) if reply_for_md else ""
        return Result.success(message="Response generated successfully", data={
            "reply": message,
            "reply_html": reply_html,
            "session_id": session_id,
        })

    @staticmethod
    def _extract_application_id(message:str)->str:
        try:
            # --------------------------------
            # FULL Application ID
            # --------------------------------
            full_id_match = re.fullmatch(r"\d{3,8}", message)
            if full_id_match:
                return message

            # --------------------------------
            # PARTIAL Application ID
            # --------------------------------
            partial_id_match = re.search(r"\b\d{3,8}\b", message)
            if partial_id_match:
                return partial_id_match.group()

            return None
                            
        except Exception as e:
            frappe.log_error(
                title="Error in extract_application_id",
                message=traceback.format_exc()
            )
            return None
    
    @classmethod
    def chat(cls, message: str, session_id: str|None = None, channel="Website", mobile_number: str|None = None) -> Result:
        try:
            chat_session:ChatSession = get_or_create_chat_session_for_web(session_id) if channel=="Website" else get_or_create_chat_session_for_whatsapp(mobile_number)

            if (chat_session.scheme=="Unknown" and message not in ALLOWED_SCHEMES) or is_small_talk(message):
                chat_session.scheme="Unknown"
                chat_session.intent="UNKNOWN"
                return send_welcome_message(chat_session.session_id,channel=channel,mobile_no=mobile_number)

            if chat_session.scheme=="Unknown" and message in   ALLOWED_SCHEMES:
                chat_session.scheme = message
                return send_intent_selection_message(chat_session.session_id,channel=channel,mobile_no=mobile_number)

            detected_scheme = cls._detect_scheme(message)
            logger.info(f"Detected scheme: {detected_scheme} for message: {message}")
            if detected_scheme and detected_scheme != chat_session.scheme:
                chat_session.scheme = detected_scheme
                chat_session.intent = "UNKNOWN"
                chat_session.last_application_id = None
                chat_session.awaiting_clarification = "Yes"
                return send_intent_selection_message_on_scheme_change(chat_session.session_id, chat_session.scheme, channel=channel,mobile_no=mobile_number)
            
            intent_keys = [item["id"] for item in ALLOWED_INTENTS]
            if chat_session.intent == "UNKNOWN" and message not in intent_keys:
                return send_intent_selection_message(chat_session.session_id,channel=channel,mobile_no=mobile_number)
            
            if chat_session.intent == "UNKNOWN" and message in intent_keys:
                chat_session.intent = message

                if chat_session.intent == "GENERAL":
                    return send_general_query_prompt(chat_session.session_id)
                else:
                    return send_application_id_prompt(chat_session.session_id)
            
            if is_small_talk(message):
                if chat_session.intent == "GENERAL":
                    return send_general_query_prompt(chat_session.session_id)
                else:
                    return send_application_id_prompt(chat_session.session_id)
            
            if chat_session.intent == "STATUS" and not chat_session.last_application_id:  
                app_id = ChatManager._extract_application_id(message)
                if app_id:
                    chat_session.last_application_id = app_id
                else:
                    return send_application_id_prompt(chat_session.session_id)
            
            # Check if the user is asking for status of another application
            app_id = ChatManager._extract_application_id(message)
            if app_id and chat_session.last_application_id!=app_id:
                chat_session.last_application_id = app_id
                chat_session.intent = "STATUS"
            
            response = cls.get_response(chat_session,message)
            return response
        except Exception as e:
            frappe.log_error(
                title="Error in chat",
                message=traceback.format_exc()
            )
            return Result.error(message=f"Internal Server Error: {str(e)}")
        finally:
            update_session(chat_session)

    @classmethod
    def get_response(cls,chat_session: ChatSession, message: str) -> Result:
        try:
            chat_history_messages = update_chat_history(
                chat_session.session_id,
                message,
            )

            api_result = None
            if chat_session.intent == "STATUS":
                if chat_session.scheme == "Scholarship":
                    api_result = ScholarshipManager.fetch_application_status_and_next_steps(chat_session.last_application_id)
                elif chat_session.scheme == "Pension":
                    api_result = PensionManager.fetch_pension_status(chat_session.last_application_id)
                elif chat_session.scheme == "Palanhaar":
                    api_result = PalanhaarManager.fetch_palanhar_status(chat_session.last_application_id)
                elif chat_session.scheme == "Anuprati" :
                    api_result = AnupratiManager.fetch_anuprati_status(chat_session.last_application_id)
                if api_result and not api_result.is_success:
                    chat_session.intent="UNKNOWN"
                    return ChatManager._generate_response(status_lookup_error_response(api_result), chat_session.session_id)

            # ==================================================
            # STEP 4 : FAQ Context
            # ==================================================
            faq_text = None
            if chat_session.scheme == "Scholarship":
                faq_text = ScholarshipManager.get_scholarship_faq()
            elif chat_session.scheme == "Pension":
                faq_text = PensionManager.get_pension_faq()
            elif chat_session.scheme == "Palanhaar":
                faq_text = PalanhaarManager.get_palanhar_faq()
            elif chat_session.scheme == "Anuprati":
                 faq_text = AnupratiManager.get_anuprati_faq()    
            # ==================================================
            # STEP 6 : Filter History by Scheme
            # ==================================================
            chat_history_payload: list[dict[str, str]] = []

            recent = (chat_history_messages or [])[-12:]
            boundary_idx = -1
            if chat_session.scheme in ALLOWED_SCHEMES:
                for i in range(len(recent) - 1, -1, -1):
                    m = recent[i]
                    role = (m.role or "").strip().lower()
                    if role != "assistant":
                        continue
                    if m.scheme in ALLOWED_SCHEMES and m.scheme != chat_session.scheme:
                        boundary_idx = i
                        break

            sliced = recent[boundary_idx + 1:] if boundary_idx >= 0 else recent

            # ── NEW: keep last 2 turns only ──────────────────────
            sliced = sliced[-4:]  # 4 = 2 user + 2 assistant messages
            # ──────────────────d───────────────────────────────────

            for m in sliced:
                role = (m.role or "").strip().lower()
                if role not in {"user", "assistant"}:
                    continue
                content = m.content or ""

                # ── NEW: trim long assistant responses ───────────
                if role == "assistant" and len(content) > 300:
                    content = content[:300] + "..."
                # ─────────────────────────────────────────────────

                # ── NEW: skip if duplicate of current question ───
                if role == "user" and content.strip() == message.strip():
                    continue
                # ─────────────────────────────────────────────────

                chat_history_payload.append({"role": role, "content": content})

            # ==================================================
            # STEP 7 : Generate Response
            # ==================================================
            status_response_rules = (
                api_result.data.get("next_steps")
                if api_result
                and isinstance(api_result.data, dict)
                and api_result.data.get("next_steps")
                else None
            )

            # AIManager.get_chatbot_answer() is used to get the response from the AI model.
            # But currently for demo purpose, we are using the dummy response.
            # This can be uncommented once the AI model is ready.
            answer_result = AIManager.get_chatbot_answer(
                question=message,
                application_status=api_result.data if api_result and isinstance(api_result.data, dict) else None,
                chat_history_messages=chat_history_payload,
                faq_text=faq_text,
                active_scheme=chat_session.scheme if chat_session.scheme in ALLOWED_SCHEMES else None,
                session_id=chat_session.name,
                status_response_rules=status_response_rules
            )

            """ answer_result = cls.get_dummy_answer(
                message=message,
                scheme=chat_session.scheme,
                intent=chat_session.intent,
                application_status = api_result.data if api_result and isinstance(api_result.data, dict) else None,
                ) """

            if not answer_result.is_success:
                return answer_result

            answer = answer_result.data.get("user_response")

            last_sequence_number = 0
            if chat_history_messages:
                last_sequence_number = max(
                    (m.sequence_number or 0) for m in chat_history_messages
                )

            add_chat_history_message(ChatHistory(
                session_id=chat_session.session_id,
                role="assistant",
                content=answer,
                sequence_number=last_sequence_number + 1,
                scheme=chat_session.scheme,
            ))
            return ChatManager._generate_response(answer, chat_session.session_id)
        except Exception as e:
            frappe.log_error(
                title="Error in get_web_chat_response",
                message=traceback.format_exc()
            )
            return Result.error(message=f"Internal Server Error: {str(e)}")

    @classmethod
    def get_dummy_answer(cls, scheme:str, intent:str,application_status:str | None = None)->Result:
        import time
        import random
        #introduce a 3-7 seconds delay
        time.sleep(random.randint(3, 7))
        if scheme == "Scholarship":
            if intent == "STATUS":
                return Result.success(
                        message="Scholarship Status",
                        data={
                            "user_response": json.dumps(application_status, indent=2)
                        }
                )
            if intent == "GENERAL":
                return Result.success(
                        message="General Scholarship",
                        data={
                            "user_response": "This is a response for a general scholarship query."
                        }
                )
        if scheme == "Pension":
            if intent == "STATUS":
                return Result.success(
                        message="Pension Status",
                        data=
                        {
                            "user_response": json.dumps(application_status, indent=2)
                        }
                )
            if intent == "GENERAL":
                return Result.success(
                        message="General Pension",
                        data={
                            "user_response": "This is a response for a general pension query."
                        }
                )
        if scheme == "Palanhaar":
           if intent == "STATUS":
               return Result.success(
                       message="Palanhaar Status",
                       data={"user_response": json.dumps(application_status, indent=2)}
                )
           if intent == "GENERAL":
               return Result.success(
                       message="General Palanhaar",
                       data={"user_response": "This is a response for a general Palanhaar query."}
                )
        if scheme == "Anuprati":
            if intent == "STATUS":
                return Result.success(
                        message="Anuprati Status",
                        data=
                        {
                            "user_response": json.dumps(application_status, indent=2)
                        }
                )
            if intent == "GENERAL":
                return Result.success(
                        message="General Anuprati",
                        data={
                            "user_response": "This is a response for a general Anuprati  query."
                        }
                )            

    @classmethod
    def _detect_scheme(cls, message: str) -> str | None:
        message = message.lower().strip()

        # Remove punctuation
        normalized = re.sub(r"[^\w\s\u0900-\u097F]", " ", message)
        normalized = " ".join(normalized.split())

        # Ignore greetings / very short messages
        if len(normalized) < 5:
            return None

        # Exact keyword match first
        for scheme, keywords in SCHEME_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in normalized:
                    return scheme

        # Fuzzy matching
        best_scheme = None
        best_score = 0

        for scheme, keywords in SCHEME_KEYWORDS.items():
            for keyword in keywords:
                score = fuzz.token_set_ratio(
                    normalized,
                    keyword.lower()
                )

                if score > best_score:
                    best_score = score
                    best_scheme = scheme

        # Stricter threshold
        return best_scheme if best_score >= 90 else None



    