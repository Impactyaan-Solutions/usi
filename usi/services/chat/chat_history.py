from usi.models.chat import ChatHistory
from typing import List
import frappe
import traceback
from usi.models.chat import ChatSession
import uuid
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
    
def update_chat_history(session_id: str, message: str, scheme: str | None = None) -> List[ChatHistory]:
    try:
        chat_history_messages = get_history(session_id) or []
        last_sequence_number = max(
            [m.sequence_number for m in chat_history_messages if m.sequence_number is not None],
            default=0,
        )
        locked_scheme = scheme if scheme in ["Scholarship", "Pension", "Palanhaar"] else None
        chat_history_doc = ChatHistory(
            session_id=session_id,
            content=message,
            sequence_number=last_sequence_number + 1,
            role="user",
            scheme=locked_scheme,
        )
        chat_history_doc.name = add_chat_history_message(chat_history_doc)
        chat_history_messages.append(chat_history_doc)
        return chat_history_messages
    except Exception as e:
        frappe.log_error(
            title="Error in get_and_update_chat_history",
            message=traceback.format_exc()
        )
        raise Exception(f"Failed to get and update chat history: {str(e)}")

def get_or_create_chat_session_for_whatsapp(mobile_number: str) -> ChatSession:
    try:
        session_data = frappe.db.get_value(
            "Chat Session",
            {"mobile_no": mobile_number},
            [
                "name",
                "scheme",
                "awaiting_clarification",
                "last_application_id",
                "session_id",
                "last_classification_json",
                "last_user_message_at",
                "intent" 
            ],
            as_dict=True
        )
        if not session_data:
            chat_session = _create_chat_session(mobile_number)
            chat_session.is_new_session = True
            return chat_session 
        session_expiry_hours = int(frappe.get_site_config().get("SESSION_EXPIRE_HOURS"))
        current_time = frappe.utils.now_datetime()
        last_user_message_at = session_data.get("last_user_message_at")
        if last_user_message_at and (current_time - last_user_message_at).total_seconds() > session_expiry_hours * 3600:
            chat_session = _create_chat_session(mobile_number)
            chat_session.is_new_session = True
            return chat_session
        
        chat_session = ChatSession(**session_data)
        chat_session.is_new_session = False
        chat_session.last_user_message_at = current_time
        update_session(chat_session)
        return chat_session
    except Exception as e:
        frappe.log_error(
            title="Error in get_or_create_chat_session",
            message=traceback.format_exc()
        )
        raise Exception(f"Failed to get or create chat session: {str(e)}")

def _create_chat_session(mobile_number: str=None) -> ChatSession:

    session_id = str(uuid.uuid4())
    session_doc = frappe.get_doc({
        "doctype": "Chat Session",
        "session_id": session_id,
        "mobile_no": mobile_number,
        "awaiting_clarification": "Yes",
        "status": "Open",
        "scheme": "Unknown",
        "last_user_message_at": frappe.utils.now_datetime(),
        "intent": "UNKNOWN"
    })  
    session_doc.insert(ignore_permissions=True)
    return ChatSession(
        name=session_doc.name,
        session_id=session_doc.session_id,
        scheme=session_doc.scheme,
        awaiting_clarification=session_doc.awaiting_clarification,
        last_application_id=session_doc.last_application_id,
        last_classification_json=session_doc.last_classification_json,
        last_user_message_at=session_doc.last_user_message_at,
        intent=session_doc.intent,
    )


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

def get_or_create_chat_session_for_web(session_id: str) -> ChatSession:
    try:
        if not session_id:
            chat_session = _create_chat_session()
            return chat_session 
        
        session_data = frappe.db.get_value(
            "Chat Session",
            {"session_id": session_id},
            [
                "name",
                "scheme",
                "awaiting_clarification",
                "last_application_id",
                "session_id",
                "last_classification_json",
                "last_user_message_at",
                "intent"
            ],
            as_dict=True
        )
        if not session_data:
            chat_session = _create_chat_session()
            return chat_session 

        chat_session = ChatSession(**session_data)
        chat_session.last_user_message_at = frappe.utils.now_datetime()
        update_session(chat_session)
        return chat_session
    except Exception as e:
        frappe.log_error(
            title="Error in get_or_create_chat_session",
            message=traceback.format_exc()
        )
        raise Exception(f"Failed to get or create chat session: {str(e)}")