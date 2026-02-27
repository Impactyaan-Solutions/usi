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

class ChatManager:
    """Generic chat orchestration based on use_case."""
    _ALLOWED_SCHEMES = {"Scholarship", "Pension"}
    @classmethod
    def chat(cls, message: str, session_id: str|None = None) -> Result:
        """Endpoint used by the website chat widget."""
        try:
            message = (message or "").strip()
            if not message:
                return Result.bad_request(message="Please type a message so I can help.")

            chat_session = cls.get_or_create_chat_session(session_id)

            if not chat_session.session_id:
                return Result.bad_request(message="Failed to create chat session.")

            chat_history_messages = cls.update_chat_history(
                chat_session.session_id,
                message,
                scheme=chat_session.scheme,
            )

            result =  cls.handle_user_message(message, chat_session, chat_history_messages)
                
            if not result.is_success:
                return result
            
            answer = (
                (result.data.get("answer") or result.data.get("reply") or "")
                if isinstance(result.data, dict)
                else (result.data or "")
            )


            # Help markdown parser render lists: ensure blank line before list blocks
            reply_for_md = re.sub(r"([^\n])\n(-\s)", r"\1\n\n\2", answer)
            reply_for_md = re.sub(r"([^\n])\n(\d+\.\s)", r"\1\n\n\2", reply_for_md)
            reply_html = frappe.utils.markdown(reply_for_md, sanitize=True, linkify=True) if reply_for_md else ""
            return Result.success(message="Chat message added successfully", data={
                "reply": answer,
                "reply_html": reply_html,
                "session_id": chat_session.session_id,
            })
        except Exception as e:
            frappe.log_error(
                title="Error in chat",
                message=traceback.format_exc()
            )
            return Result.failure(message="Failed to chat", error_data=traceback.format_exc())

    @staticmethod
    def get_history(session_id: str) -> List[ChatHistory]:
        try:
            chat_history_messages = frappe.get_all(
                "Chat History",
                filters={"session_id": session_id},
                fields=["name", "content", "role", "session_id", "sequence_number", "scheme", "creation"],
                order_by="sequence_number asc, creation asc",
            )
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
    def handle_user_message(
        message: str,
        chat_session: ChatSession,
        chat_history_messages: List[ChatHistory]
    ) -> Result:
        try:
            # --------------------------------------------------
            # 1️⃣ Classify
            # --------------------------------------------------
            classification_result = AIManager.classify_message(message)

            if not classification_result.is_success:
                return ChatManager.fallback_error_response(message)

            classification = classification_result.data
            scheme = classification["scheme"]
            intent = classification["intent"]
            application_id = classification["application_id"]
            explicit_switch = classification["explicit_switch"]

            chat_session.last_classification_json = frappe.as_json(classification)

            # --------------------------------------------------
            # 0️⃣ Small Talk Handling (Before FSM)
            # --------------------------------------------------

            if (
                chat_session.scheme not in ChatManager._ALLOWED_SCHEMES
                and classification["scheme"] == "Unknown"
                and classification["intent"] == "GENERAL"
                and not classification["application_id"]
            ):
                if ChatManager.is_small_talk(message):
                    return ChatManager.greeting_response(message)

            # ==================================================
            # STATE 1: Awaiting Scheme Clarification
            # ==================================================
            if chat_session.awaiting_clarification == "Yes":

                if scheme in ChatManager._ALLOWED_SCHEMES:
                    # Resolve missing scheme
                    chat_session.scheme = scheme
                    chat_session.awaiting_clarification = "No"
                else:
                    # Still unclear
                    ChatManager.update_session(chat_session)
                    return ChatManager.ask_scheme_clarification(message)

                # After resolving scheme, continue normally
                # DO NOT apply switch logic here
                scheme = chat_session.scheme
            # ==================================================
            # STATE 2: Normal Routing
            # ==================================================
            else:

                # ---------- Explicit Switch ----------
                if explicit_switch == "Yes" and scheme in ChatManager._ALLOWED_SCHEMES:
                    chat_session.scheme = scheme

                # ---------- Implicit Switch ----------
                elif (
                    scheme in ChatManager._ALLOWED_SCHEMES
                    and chat_session.scheme in ChatManager._ALLOWED_SCHEMES
                    and scheme != chat_session.scheme
                ):
                    chat_session.scheme = scheme

                # ---------- No Scheme Yet ----------
                elif chat_session.scheme not in ChatManager._ALLOWED_SCHEMES:
                    if scheme in ChatManager._ALLOWED_SCHEMES:
                        chat_session.scheme = scheme
                    else:
                        chat_session.awaiting_clarification = "Yes"
                        ChatManager.update_session(chat_session)
                        return ChatManager.ask_scheme_clarification(message)

                scheme = chat_session.scheme

            # ==================================================
            # 3️⃣ STATUS Routing
            # ==================================================
            api_result = None

            if intent == "STATUS":

                # Scheme must be locked before tool call
                if scheme not in ChatManager._ALLOWED_SCHEMES:
                    chat_session.awaiting_clarification = "Yes"
                    if application_id:
                        chat_session.last_application_id = application_id
                    ChatManager.update_session(chat_session)
                    return ChatManager.ask_scheme_clarification(message)

                # Resolve Application ID
                if not application_id:
                    if chat_session.last_application_id:
                        application_id = chat_session.last_application_id
                    else:
                        ChatManager.update_session(chat_session)
                        return ChatManager.ask_for_application_id(message)

                # Call Tool
                if scheme == "Scholarship":
                    api_result = ScholarshipManager.fetch_application_status(application_id)

                elif scheme == "Pension":
                    api_result = PensionManager.fetch_pension_status(application_id)

                chat_session.last_application_id = application_id

            # ==================================================
            # 4️⃣ FAQ Context
            # ==================================================
            faq_text = None
            if scheme == "Scholarship":
                faq_text = ScholarshipManager.get_scholarship_faq()
            elif scheme == "Pension":
                faq_text = PensionManager.get_pension_faq()

            # ==================================================
            # 5️⃣ Persist Session
            # ==================================================
            chat_session.scheme = scheme
            chat_session.awaiting_clarification = "No"
            ChatManager.update_session(chat_session)

            # ==================================================
            # 6️⃣ Filter History by Scheme
            # ==================================================
            chat_history_payload: list[dict[str, str]] = []

            for m in (chat_history_messages or [])[-12:]:
                role = (m.role or "").lower()
                if role not in {"user", "assistant"}:
                    continue

                if scheme in ChatManager._ALLOWED_SCHEMES:
                    if m.scheme and m.scheme not in (scheme, "Unknown"):
                        continue

                chat_history_payload.append({
                    "role": role,
                    "content": m.content or ""
                })

            # ==================================================
            # 7️⃣ Generate Response
            # ==================================================
     
            answer_result = AIManager.get_chatbot_answer(
                question=message,
                application_status=api_result.data if api_result else None,
                chat_history_messages=chat_history_payload,
                faq_text=faq_text,
                active_scheme=scheme if scheme in ChatManager._ALLOWED_SCHEMES else None,
            )

            if not answer_result.is_success:
                return answer_result

            answer = (
                (answer_result.data.get("answer") or answer_result.data.get("reply") or "")
                if isinstance(answer_result.data, dict)
                else (answer_result.data or "")
            )

            # Save assistant reply
            last_sequence_number = (
                chat_history_messages[-1].sequence_number
                if chat_history_messages and chat_history_messages[-1].sequence_number is not None
                else 0
            )

            ChatManager.add_chat_history_message(ChatHistory(
                session_id=chat_session.session_id,
                role="assistant",
                content=answer,
                sequence_number=last_sequence_number + 1,
                scheme=scheme,
            ))

            return answer_result

        except Exception:
            frappe.log_error(
                title="Error in handle_user_message",
                message=traceback.format_exc()
            )
            return ChatManager.fallback_error_response(message)
    
    @staticmethod
    def detect_script(message: str) -> str:
        if re.search(r'[\u0900-\u097F]', message):
            return "DEVANAGARI"

        return "LATIN"

    @staticmethod
    def ask_for_application_id(message: str) -> Result:
        script =ChatManager.detect_script(message)

        if script == "DEVANAGARI":
            reply = "कृपया अपना आवेदन ID/नंबर दर्ज करें (केवल अंक)।"
        else:
            reply = "Please enter your application ID (digits only)."

        return Result.success(
            message="Ask for application ID",
            data=reply
        )
    @staticmethod
    def is_small_talk(message: str) -> bool:
        msg = message.strip().lower()

        # very short messages
        if len(msg.split()) <= 2:
            return True

        casual_words = [
            "hi", "hello", "hey", "namaste",
            "thanks", "thank you",
            "good morning", "good evening",
            "how are you", "how are you doing",
            "नमस्ते", "नमस्ते आप कैसे हैं", "नमस्ते आप कैसे हैं",
        ]

        return any(word in msg for word in casual_words)
    @staticmethod
    def greeting_response(message: str) -> Result:
        script = ChatManager.detect_script(message)

        if script == "DEVANAGARI":
            reply = "नमस्ते 😊 मैं आपकी कैसे मदद कर सकता/सकती हूँ? आप छात्रवृत्ति या पेंशन के बारे में मुझसे कुछ भी पूछ सकते हैं?"
        else:
            reply = "Hello 😊 How can I help you today? You can ask me anything about Scholarship or Pension?"

        return Result.success(message="Greeting response", data=reply)
        
    @staticmethod
    def ask_scheme_clarification(message: str) -> str:
        script = ChatManager.detect_script(message)

        if script == "DEVANAGARI":
            reply = "कृपया बताएं कि आप छात्रवृत्ति के बारे में पूछ रहे हैं या पेंशन के बारे में?"
        else:
            reply = "Please tell me whether you are asking about Scholarship or Pension."

        return Result.success(
            message="Ask scheme clarification",
            data=reply
        )
    @staticmethod
    def fallback_error_response(message: str | None = None) -> Result:
        script = ChatManager.detect_script(message)

        if script == "DEVANAGARI":
            reply = "कृपया बताएं कि आप छात्रवृत्ति के बारे में पूछ रहे हैं या पेंशन के बारे में?"
        else:
            reply = "Please tell me whether you are asking about Scholarship or Pension."

        return Result.success(
            message="Fallback error response",
            data=reply
        )
    
    @staticmethod
    def update_session(chat_session: ChatSession) -> None:
        doc = frappe.get_doc("Chat Session", chat_session.name)
        # Update only allowed fields
        for field, value in chat_session.model_dump().items():
            if field != "name":
                doc.set(field, value)

        doc.save(ignore_permissions=True)


    @classmethod
    def get_or_create_chat_session(cls, session_id: str) -> ChatSession:
        try:
            if not session_id:
                session_id = str(uuid.uuid4())

                session_doc = frappe.get_doc({
                    "doctype": "Chat Session",
                    "session_id": session_id,
                    "awaiting_clarification": "No",
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
                raise Exception("Chat session not found")

            return ChatSession(**session_data)

        except Exception as e:
            frappe.log_error(
                title="Error in get_or_create_session",
                message=traceback.format_exc()
            )
            raise Exception(f"Failed to get and update chat history: {str(e)}")

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