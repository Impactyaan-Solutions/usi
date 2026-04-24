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
from usi.models.chat import ChatSession
import json
from usi.utils import utils
from frappe.utils import now_datetime
from usi.models.chat import Classification

class ChatManager:
    _ALLOWED_SCHEMES = {"Scholarship", "Pension"}
    _ALLOWED_CHANNELS = {"Website", "WhatsApp"}
    @classmethod
    def chat(
        cls, 
        message: str, 
        session_id: str|None = None,
        dry_run: bool = False,
        mobile_number: str|None = None,
        channel:str = "Website"
    ) -> Result:
        try:
            message = (message or "").strip()
            if not message:
                return Result.bad_request(message="Please type a message so I can help.")

            if channel not in ChatManager._ALLOWED_CHANNELS:
                return Result.bad_request(message="Invalid channel.")

            chat_session = cls.get_or_create_chat_session(session_id, mobile_number, channel)

            if not chat_session.session_id:
                return Result.bad_request(message="Failed to create chat session.")

            chat_history_messages = cls.update_chat_history(
                chat_session.session_id,
                message,
            )
            if dry_run:
                return cls.dry_run_response(chat_session, chat_history_messages)

            # ==================================================
            # PREPROCESSING: Small Talk Handling (Before FSM)
            # ==================================================
            if ChatManager.is_small_talk(message):
                chat_session.last_user_message_at = now_datetime()
                ChatManager.update_session(chat_session)
                return ChatManager.greeting_response(message, chat_session.session_id)
            
            # ==================================================
            # STEP 1 : Classify
            # ==================================================
            classification = ChatManager.try_deterministic_routing(message)
            if not classification:
                classification_result = AIManager.classify_message(message)
                if not classification_result.is_success:
                    return ChatManager.fallback_error_response(message, chat_session.session_id)
                classification = classification_result.data
            chat_session.last_classification_json = frappe.as_json(classification)           
            # ==================================================
            # STEP 2 : Resolve Scheme
            # ==================================================
            scheme_changed = False
            if chat_session.awaiting_clarification == "Yes":
                if classification.scheme in ChatManager._ALLOWED_SCHEMES:
                    # Resolve missing scheme
                    chat_session.scheme = classification.scheme
                    chat_session.awaiting_clarification = "No"
                else:
                    # Still unclear
                    ChatManager.update_session(chat_session)
                    return ChatManager.ask_scheme_clarification(message, chat_session.session_id)
            else:
                if classification.scheme in ChatManager._ALLOWED_SCHEMES:
                    if classification.scheme != chat_session.scheme:
                        scheme_changed = True
                    chat_session.scheme = classification.scheme
                elif chat_session.scheme not in ChatManager._ALLOWED_SCHEMES:
                    if classification.scheme in ChatManager._ALLOWED_SCHEMES:
                        chat_session.scheme = classification.scheme
                    else:
                        chat_session.awaiting_clarification = "Yes"
                        ChatManager.update_session(chat_session)
                        return ChatManager.ask_scheme_clarification(message, chat_session.session_id)
            if classification.scheme not in ChatManager._ALLOWED_SCHEMES and chat_session.scheme not in ChatManager._ALLOWED_SCHEMES:
                return ChatManager.ask_scheme_clarification(message, chat_session.session_id)
            elif classification.scheme not in ChatManager._ALLOWED_SCHEMES and chat_session.scheme in ChatManager._ALLOWED_SCHEMES:
                classification.scheme = chat_session.scheme
            # ==================================================
            # STEP 3 : STATUS Routing
            # ==================================================
            api_result = None
            chat_session.intent = classification.intent
            if scheme_changed and classification.application_id:
                chat_session.last_application_id = classification.application_id
            if scheme_changed and not classification.application_id:
                chat_session.last_application_id = None
                ChatManager.update_session(chat_session)
            if classification.intent == "STATUS":
                if not classification.application_id:
                    if chat_session.last_application_id and not scheme_changed:
                        classification.application_id = chat_session.last_application_id
                    else:
                        ChatManager.update_session(chat_session)
                        return ChatManager.ask_for_application_id(message, chat_session.session_id)

                if classification.scheme == "Scholarship":
                    api_result = ScholarshipManager.fetch_application_status_and_next_steps(classification.application_id)

                elif classification.scheme == "Pension":
                    api_result = PensionManager.fetch_pension_status(classification.application_id)

                chat_session.last_application_id = classification.application_id

                if not api_result.is_success:
                    ChatManager.update_session(chat_session)
                    return ChatManager.application_not_found_response(message, chat_session.session_id)
            else:
                api_result = None
                
            # ==================================================
            # STEP 4 : FAQ Context
            # ==================================================
            faq_text = None
            if classification.scheme == "Scholarship":
                faq_text = ScholarshipManager.get_scholarship_faq()
            elif classification.scheme == "Pension":
                faq_text = PensionManager.get_pension_faq()

            # ==================================================
            # STEP 5 : Persist Session
            # ==================================================
            chat_session.scheme = classification.scheme
            chat_session.awaiting_clarification = "No"
            
            # ==================================================
            # STEP 6 : Filter History by Scheme
            # ==================================================
            chat_history_payload: list[dict[str, str]] = []

            # If scheme changes, do NOT send mixed history. Keep only messages after the last
            # cross-scheme assistant message (acts as a boundary).
            recent = (chat_history_messages or [])[-12:]
            boundary_idx = -1
            if classification.scheme in ChatManager._ALLOWED_SCHEMES:
                for i in range(len(recent) - 1, -1, -1):
                    m = recent[i]
                    role = (m.role or "").strip().lower()
                    if role != "assistant":
                        continue
                    if m.scheme in ChatManager._ALLOWED_SCHEMES and m.scheme != classification.scheme:
                        boundary_idx = i
                        break

            sliced = recent[boundary_idx + 1:] if boundary_idx >= 0 else recent
            for m in sliced:
                role = (m.role or "").strip().lower()
                if role not in {"user", "assistant"}:
                    continue
                chat_history_payload.append({"role": role, "content": m.content or ""})

            # ==================================================
            # STEP 7 : Generate Response
            # ==================================================
            vocabulary_rules = utils.read_text_file("prompt/vocabulary_rules.md")
            status_response_rules = (
                api_result.data.get("next_steps")
                if api_result
                and isinstance(api_result.data, dict)
                and api_result.data.get("next_steps")
                else None
            )
            answer_result = AIManager.get_chatbot_answer(
                question=message,
                application_status=api_result.data if api_result and isinstance(api_result.data, dict) else None,
                chat_history_messages=chat_history_payload,
                faq_text=faq_text,
                active_scheme=classification.scheme if classification.scheme in ChatManager._ALLOWED_SCHEMES else None,
                session_id=chat_session.name,
                status_response_rules=status_response_rules,
                vocabulary_rules=vocabulary_rules,
            )

            if not answer_result.is_success:
                return answer_result

            answer = answer_result.data.get("user_response")

            last_sequence_number = 0
            if chat_history_messages:
                last_sequence_number = max(
                    (m.sequence_number or 0) for m in chat_history_messages
                )

            ChatManager.add_chat_history_message(ChatHistory(
                session_id=chat_session.session_id,
                role="assistant",
                content=json.dumps(answer_result.data),
                sequence_number=last_sequence_number + 1,
                scheme=classification.scheme,
            ))
            chat_session.last_user_message_at = now_datetime()
            ChatManager.update_session(chat_session)

            return ChatManager.generate_response(answer, chat_session.session_id)
            
        except Exception as e:
            frappe.log_error(
                title="Error in chat",
                message=traceback.format_exc()
            )
            return ChatManager.fallback_error_response(message, chat_session.session_id)

    @staticmethod
    def try_deterministic_routing(message):

        msg = message.strip().lower()

        scheme = None
        intent = None
        application_id = None
        signals = []

        # --------------------------------
        # FULL Application ID
        # --------------------------------
        full_id_match = re.fullmatch(r"\d{3,8}", msg)

        if full_id_match:
            application_id = msg
            intent = "STATUS"
            signals.append(msg)

        # --------------------------------
        # PARTIAL Application ID
        # --------------------------------
        if not application_id:
            partial_id_match = re.search(r"\b\d{3,8}\b", msg)

            if partial_id_match:
                application_id = partial_id_match.group()
                intent = "STATUS"
                signals.append(application_id)

        # --------------------------------
        # STATUS intent detection
        # --------------------------------
        if "status" in msg or msg in ["check", "check status"]:
            intent = "STATUS"
            signals.append("status_keyword")

        # --------------------------------
        # Scheme detection
        # --------------------------------
        if "scholarship" in msg:
            scheme = "Scholarship"
            signals.append("scholarship_keyword")

        elif "pension" in msg:
            scheme = "Pension"
            signals.append("pension_keyword")

        # --------------------------------
        # If nothing detected → use LLM
        # --------------------------------
        if not intent:
            return None

        return Classification(
            scheme=scheme or "Unknown",
            intent=intent,
            application_id=application_id,
            explicit_switch="No",
            decision_summary="Deterministic routing",
            signals_detected=signals,
            confidence="HIGH",
        )


    @staticmethod
    def get_history(session_id: str) -> List[ChatHistory]:
        try:
            chat_history_messages = frappe.get_all(
                "Chat History",
                filters={"session_id": session_id},
                fields=["name", "content", "role", "session_id", "sequence_number", "scheme", "creation"],
                order_by="sequence_number desc",
                limit=12,
            )
            chat_history_messages.reverse()

        except Exception as e:
            frappe.log_error(
                title="Error in get_history",
                message=traceback.format_exc()
            )
            return []
        return [
            ChatHistory(
                name=chat_history_message.get("name"),
                content=chat_history_message.get("content") or "",
                role=chat_history_message.get("role") or "",
                session_id=chat_history_message.get("session_id") or "",
                sequence_number=chat_history_message.get("sequence_number"),
                scheme=chat_history_message.get("scheme"),
            )
            for chat_history_message in chat_history_messages
        ]

    @staticmethod
    def add_chat_history_message(chat_history: ChatHistory) -> str:
        try:
            chat_history_doc = frappe.get_doc(
                {
                    "doctype": "Chat History",
                    "content": chat_history.content,
                    "role": chat_history.role,
                    "session_id": chat_history.session_id,
                    "sequence_number": chat_history.sequence_number,
                    "scheme": chat_history.scheme,
                }
            )
            chat_history_doc.insert(ignore_permissions=True)
            
            return chat_history_doc.name
        except Exception as e:
            frappe.log_error(
                title="Error in add_chat_history_message",
                message=traceback.format_exc()
            )
            raise Exception(f"Failed to add message: {str(e)}")
    
    @classmethod
    def add_chat_message(cls, request_data: Dict[str, Any]) -> Result:
        if not request_data.get("content"):
            raise ValueError("Content is required and cannot be emptyddd")
        if not request_data.get("role"):
            raise ValueError("Role is required and cannot be empty")
        if not request_data.get("response_type"):
            raise ValueError("Response type is required and cannot be empty")
        if not request_data.get("use_case"):
            raise ValueError("Use case is required and cannot be empty")
        
        if request_data.get("session_id") is None:
            session_id = cls.create_session(request_data.get("use_case"))
            request_data["session_id"] = session_id
            request_data["sequence_number"] = 1
        else:
            last_sequence_number = cls.get_last_message_sequence_number(request_data.get("session_id"))
            request_data["sequence_number"] = last_sequence_number + 1
        chat_history = ChatHistory(
            user_message=request_data.get("content"),
            role=request_data.get("role"),
            response_type=request_data.get("response_type"),
            use_case=request_data.get("use_case"),
            session_id=request_data.get("session_id"),
            event_id=request_data.get("event_id") or "",
            user=request_data.get("user") or "",
            sequence_number=request_data.get("sequence_number"),
        )
        message_id = cls.add_chat_history_message(chat_history)
        return Result.success(message="Chat message added successfully", data={
            "session_id": chat_history.session_id,
            "chat_id": message_id,
            "sequence_number": chat_history.sequence_number,
        })

    @classmethod
    def submit_feedback_for_session(cls, request_data: Dict[str, Any]) -> Result:
        if not request_data.get("session_id"):
            raise ValueError("Session ID is required and cannot be empty")
        if not request_data.get("feedback_rating"):
            raise ValueError("Feedback rating is required and cannot be empty")

        try:
            chat_session_doc = frappe.get_doc("Chat Session", {"session_id": request_data.get("session_id")})
            chat_session_doc.feedback_rating = request_data.get("feedback_rating")
            chat_session_doc.feedback_comments = request_data.get("feedback_comments")
            chat_session_doc.save(ignore_permissions=True)

            return Result.success(message="Feedback submitted successfully")
        except Exception as e:
            frappe.log_error(
                title="Error in submit_feedback_for_session",
                message=traceback.format_exc()
            )
            return Result.failure(message=f"Failed to submit feedback for session: {str(e)}", error_data=traceback.format_exc())

    @staticmethod
    def create_session(use_case: str) -> str:
        if not use_case:
            raise ValueError("Use case is required and cannot be empty")
        chat_session_doc = frappe.get_doc({
            "doctype": "Chat Session",
            "use_case": use_case,
            "session_id": str(uuid.uuid4()),
        })
        chat_session_doc.insert(ignore_permissions=True)

        return chat_session_doc.session_id
    
    @classmethod
    def submit_feedback_for_chat_message(cls, request_data: Dict[str, Any]) -> Result:
        if not request_data.get("chat_id"):
            raise ValueError("Chat ID  is required and cannot be empty")
        if not request_data.get("feedback_rating"):
            raise ValueError("Feedback rating is required and cannot be empty")
       
        try:
            chat_feedback_doc = frappe.get_doc(
                {
                    "doctype": "Chat Feedback",
                    "chat_history_message": request_data.get("chat_id"),
                    "chat_feedback": request_data.get("feedback_rating"),
                    "chat_feedback_comment": request_data.get("feedback_comments"),
                }
            )
            chat_feedback_doc.insert(ignore_permissions=True)
  
            return Result.success(message="Feedback submitted successfully")
        except Exception as e:
            frappe.log_error(
                title="Error in submit_feedback_for_chat_message",
                message=traceback.format_exc()
            )
            return Result.failure(message=f"Failed to submit feedback for chat message: {str(e)}", error_data=traceback.format_exc())
    
    @classmethod
    def get_last_message_sequence_number(cls, session_id: str) -> int:
        last_message = frappe.get_all(
            "Chat History",
            filters={"session_id": session_id},
            fields=["name", "sequence_number"],
            order_by="sequence_number desc",
            limit=1,
        )
        if last_message:
            return last_message[0].get("sequence_number")
        return 0

    @classmethod
    def get_chat_history_by_session_id(cls, session_id: str) -> Result:
        if not session_id:
            raise ValueError("Session ID is required and cannot be empty")
        try:
            chat_history_messages = cls.get_history(session_id)
            return Result.success(message="Chat history fetched successfully", data=[chat_history_message.model_dump() for chat_history_message in chat_history_messages])
        except Exception as e:
            frappe.log_error(
                title="Error in get_chat_history_by_session_id",
                message=traceback.format_exc()
            )
            return Result.failure(message=f"Failed to get chat history by session ID: {str(e)}", error_data=traceback.format_exc())

    @staticmethod
    def dry_run_response(
        chat_session: ChatSession, 
        chat_history_messages: List[ChatHistory]
    ) -> Result:
        #add 3 seconds delay
        import time
        time.sleep(3)
        classification_result ={
            "scheme": "Scholarship",
            "intent": "STATUS",
            "application_id": "123456",
            "explicit_switch": "No",
            "decision_summary": "Dry run classification successful",
            "signals_detected": ["dry run"],
            "confidence": "HIGH",
            "awaiting_clarification": "No",
        }

        # Reuse the existing session object so `name` is present.
        chat_session.scheme = "Scholarship"
        chat_session.awaiting_clarification = "No"
        chat_session.last_application_id = "123456"
        chat_session.last_classification_json = json.dumps(classification_result)
        ChatManager.update_session(chat_session)
        answer_result = {
            "user_response": "This is a dry run response",
        }
        last_sequence_number = (
            chat_history_messages[-1].sequence_number
            if chat_history_messages and chat_history_messages[-1].sequence_number is not None
            else 0
        )
        ChatManager.add_chat_history_message(ChatHistory(
            session_id=chat_session.session_id,
            role="assistant",
            content=json.dumps(answer_result),
            sequence_number=last_sequence_number + 1,
            scheme="Scholarship",
        ))
        return Result.success(message="Dry run successful", data=answer_result["user_response"])

    @staticmethod
    def detect_script(message: str) -> str:
        if re.search(r'[\u0900-\u097F]', message):
            return "DEVANAGARI"

        return "LATIN"

    @staticmethod
    def ask_for_application_id(message: str, session_id: str) -> Result:

        reply = "कृपया अपना आवेदन ID/नंबर दर्ज करें (केवल अंक)। \n Please enter your application ID (digits only)."

        return ChatManager.generate_response(reply, session_id)
    
    @staticmethod
    def is_small_talk(message: str) -> bool:
        msg = (message or "").strip().lower()

        # normalize spaces
        msg = re.sub(r"\s+", " ", msg)

        greetings = {
            "hi",
            "hello",
            "hey",
            "namaste",
            "नमस्ते",
        }

        thanks = {
            "thanks",
            "thank you",
            "thx",
            "धन्यवाद",
        }

        polite_phrases = {
            "good morning",
            "good evening",
            "how are you",
            "how are you doing",
            "आप कैसे हैं",
        }

        # tokenize
        tokens = msg.split()

        # Case 1: exact greeting
        if msg in greetings:
            return True

        # Case 2: exact thanks
        if msg in thanks:
            return True

        # Case 3: exact polite phrases
        if msg in polite_phrases:
            return True

        # Case 4: greeting + punctuation (hi!, hello.)
        if len(tokens) == 1:
            word = re.sub(r"[^\w\u0900-\u097F]", "", tokens[0])
            if word in greetings or word in thanks:
                return True

        return False
        
    @staticmethod
    def greeting_response(message: str, session_id: str) -> Result:

        reply = "नमस्कार, मैं आपका समाधान साथी हूँ! आपकी कैसे मदद कर सकता हूँ? आप छात्रवृत्ति या पेंशन के बारे में मुझसे कुछ भी पूछ सकते हैं?  \n Hi! I’m your Samadhaan Saathi. How can I help you today? ? You can ask me anything about Scholarship or Pension?"

        return ChatManager.generate_response(reply, session_id)

    @staticmethod
    def generate_response(message: str,session_id: str) -> Result:
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
    def application_not_found_response(message: str, session_id: str) -> Result:

        reply = "इस आईडी/नंबर से संबंधित आवेदन नहीं मिला। कृपया अपना आवेदन नंबर दोबारा जांच लें। \n Application corresponding to this ID/number is not found. Please double check your application number."

        return ChatManager.generate_response(reply, session_id)

    @staticmethod
    def ask_scheme_clarification(message: str, session_id: str) -> Result:

        reply = "कृपया बताएं कि आप छात्रवृत्ति के बारे में पूछ रहे हैं या पेंशन के बारे में? \n Please tell me whether you are asking about Scholarship or Pension."

        return ChatManager.generate_response(reply, session_id)
   
    @staticmethod
    def fallback_error_response(message: str, session_id: str) -> Result:

        reply = "एक एरर आया है। कृपया थोड़ी देर बाद फिर से प्रयास करें। \n I have encountered an error. Please try again later."


        return ChatManager.generate_response(reply, session_id)
    
    @staticmethod
    def update_session(chat_session: ChatSession) -> None:
        # `doc.save()` performs a modified timestamp check and can fail when
        # concurrent requests update the same chat session within seconds.
        # For this flow we only need a partial field update, so use DB update.
        updates = {
            field: value
            for field, value in chat_session.model_dump().items()
            if field != "name"
        }
        if updates:
            frappe.db.set_value("Chat Session", chat_session.name, updates, update_modified=True)

    @classmethod
    def get_or_create_chat_session(cls, session_id: str, mobile_number: str|None = None, channel:str = "Website") -> ChatSession:
        try:

            if channel == "Website":
                if not session_id:
                    session_id = str(uuid.uuid4())

                    session_doc = frappe.get_doc({
                        "doctype": "Chat Session",
                        "session_id": session_id,
                        "awaiting_clarification": "Yes",
                        "status": "Open",
                        "scheme": "Unknown",
                    })

                    session_doc.insert(ignore_permissions=True)

                    return ChatSession(
                        name=session_doc.name,
                        session_id=session_doc.session_id,
                        scheme=session_doc.scheme,
                        awaiting_clarification=session_doc.awaiting_clarification,
                        last_application_id=session_doc.last_application_id,
                        last_classification_json=session_doc.last_classification_json,
                    )
                # Fetch existing session
                session_data = frappe.db.get_value(
                    "Chat Session",
                    {"session_id": session_id},
                    [
                        "name",
                        "scheme",
                        "awaiting_clarification",
                        "last_application_id",
                        "session_id",
                        "last_classification_json"
                    ],
                    as_dict=True
                )
                if not session_data:
                    raise Exception(f"Chat session not found for session ID: {session_id}")
                return ChatSession(**session_data)

            if channel == "WhatsApp":
                session_data = frappe.db.get_value(
                    "Chat Session",
                    {"mobile_no": mobile_number},
                    [
                        "name",
                        "scheme",
                        "awaiting_clarification",
                        "last_application_id",
                        "session_id",
                        "last_classification_json"
                    ],
                    as_dict=True
                )
                if session_data:
                    return ChatSession(**session_data)
                else:
                    session_id = str(uuid.uuid4())
                    session_doc = frappe.get_doc({
                        "doctype": "Chat Session",
                        "session_id": session_id,
                        "mobile_no": mobile_number,
                        "awaiting_clarification": "Yes",
                        "status": "Open",
                        "scheme": "Unknown",
                    })  
                    session_doc.insert(ignore_permissions=True)
                    return ChatSession(
                        name=session_doc.name,
                        session_id=session_doc.session_id,
                        scheme=session_doc.scheme,
                        awaiting_clarification=session_doc.awaiting_clarification,
                        last_application_id=session_doc.last_application_id,
                        last_classification_json=session_doc.last_classification_json,
                    )
        except Exception as e:
            frappe.log_error(
                title="Error in get_or_create_chat_session",
                message=traceback.format_exc()
            )
            raise Exception(f"Failed to get or create chat session: {str(e)}")

    @classmethod
    def update_chat_history(cls, session_id: str, message: str, scheme: str | None = None) -> List[ChatHistory]:
        try:
            chat_history_messages = cls.get_history(session_id) or []
            last_sequence_number = max(
                [m.sequence_number for m in chat_history_messages if m.sequence_number is not None],
                default=0,
            )
            locked_scheme = scheme if scheme in ["Scholarship", "Pension"] else None
            chat_history_doc = ChatHistory(
                session_id=session_id,
                content=message,
                sequence_number=last_sequence_number + 1,
                role="user",
                scheme=locked_scheme,
            )
            chat_history_doc.name = cls.add_chat_history_message(chat_history_doc)
            chat_history_messages.append(chat_history_doc)
            return chat_history_messages
        except Exception as e:
            frappe.log_error(
                title="Error in get_and_update_chat_history",
                message=traceback.format_exc()
            )
            raise Exception(f"Failed to get and update chat history: {str(e)}")