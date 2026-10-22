"""
Grievance workflow for SJED Bot.

Allows citizens to raise grievances for Scholarship, Pension, and Palanhaar
schemes through Sampark integration. Grievances can be initiated from:
  - Application Enquiry (after a successful status check)
  - General Query
  - Renew workflow
  - New "Raise Grievance" main-menu option

Flow:
  1. Collect Application ID (if not already in session)
  2. Show grievance form  (Issue Type dropdown + free-text details)
  3. Show non-editable summary with confirmation
  4. Call Sampark API  (via STORE, retries once on failure)
  5. Show Ticket ID or fallback error message

State storage: wizard payload is kept in ChatSession.last_classification_json
under the key "grievance" — exactly the same column RenewalManager uses for
its own state (RenewalManager stores a dict with a "step" key at the root;
we nest under "grievance" so the two can coexist without collision).
"""
from __future__ import annotations

import json
import re
import traceback
import uuid
from datetime import datetime
from typing import Any, Optional

import frappe
from usi.models.chat import ChatSession
from usi.models.result import Result
from usi.services.dummy_sampark_store import DummySamparkStore

# ---------------------------------------------------------------------------
# Swap this for a live client when the Sampark API is ready.
# The replacement must implement: create_ticket(**kwargs) -> dict
#                                 get_ticket_status(ticket_id) -> dict | None
# ---------------------------------------------------------------------------
STORE = DummySamparkStore()

# ---------------------------------------------------------------------------
# Wizard steps
# ---------------------------------------------------------------------------
STEP_APP_ID    = "APP_ID"
STEP_FORM      = "FORM"
STEP_SUMMARY   = "SUMMARY"
STEP_SUBMITTED = "SUBMITTED"

# ---------------------------------------------------------------------------
# Issue-type options
# ---------------------------------------------------------------------------
ISSUE_TYPES = [
    {"id": "PAYMENT_ISSUE",             "title": "Payment Issue"},
    {"id": "APPLICATION_STATUS_ISSUE",  "title": "Application Status Issue"},
    {"id": "APPLICATION_RENEWAL_ISSUE", "title": "Application Renewal Issue"},
    {"id": "SCHEME_BENEFITS_STOPPED",   "title": "Scheme Benefits Wrongly Stopped"},
    {"id": "OTHER",                     "title": "Other"},
]

# ---------------------------------------------------------------------------
# Button IDs
# ---------------------------------------------------------------------------
BTN_PROCEED   = "GRIEVANCE_PROCEED"
BTN_GO_BACK   = "GRIEVANCE_GO_BACK"
BTN_EDIT      = "GRIEVANCE_EDIT"
BTN_MAIN_MENU = "GRIEVANCE_MAIN_MENU"
BTN_NO_APP_ID = "GRIEVANCE_NO_APP_ID"

# ---------------------------------------------------------------------------
# Entry-point labels (sent to Sampark)
# ---------------------------------------------------------------------------
ENTRY_POINT_STATUS    = "Application Enquiry"
ENTRY_POINT_GENERAL   = "General Query"
ENTRY_POINT_RENEW     = "Renew"
ENTRY_POINT_MAIN_MENU = "Main Menu - Raise Grievance"

# ---------------------------------------------------------------------------
# Validation limits
# ---------------------------------------------------------------------------
MIN_DETAILS_LENGTH = 20
MAX_DETAILS_LENGTH = 500


def _empty_payload() -> dict[str, Any]:
    return {
        "grievance_step": STEP_APP_ID,   # unique key so it never clashes with renewal's "step"
        "entry_point":    None,
        "application_id": None,
        "issue_type":     None,
        "issue_type_title": None,
        "details":        None,
        "request_id":     None,
        "ticket_id":      None,
        "retry_count":    0,
    }


# ===========================================================================
# GrievanceManager
# ===========================================================================

class GrievanceManager:

    # ------------------------------------------------------------------
    # State helpers  (mirrors RenewalManager._load_payload / clear_state)
    # ------------------------------------------------------------------

    @staticmethod
    def _load_payload(chat_session: ChatSession) -> dict[str, Any]:
        """
        Read grievance wizard state from last_classification_json.
        Grievance state is stored under the "grievance" key so it can
        coexist with renewal state which uses a "step" key at root level.
        """
        raw = chat_session.last_classification_json
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, dict) and isinstance(data.get("grievance"), dict):
                    inner = data["grievance"]
                    if inner.get("grievance_step"):
                        return inner
            except (TypeError, json.JSONDecodeError):
                pass
        return _empty_payload()

    @staticmethod
    def _save_payload(chat_session: ChatSession, payload: dict) -> None:
        """
        Write grievance wizard state back into last_classification_json,
        preserving any existing renewal state at the root level.
        """
        raw = chat_session.last_classification_json
        try:
            outer = json.loads(raw) if raw else {}
            if not isinstance(outer, dict):
                outer = {}
        except (TypeError, json.JSONDecodeError):
            outer = {}
        outer["grievance"] = payload
        chat_session.last_classification_json = json.dumps(outer, ensure_ascii=False)

    @classmethod
    def clear_state(cls, chat_session: ChatSession) -> None:
        """Remove grievance state; leave any renewal state untouched."""
        raw = chat_session.last_classification_json
        try:
            outer = json.loads(raw) if raw else {}
            if isinstance(outer, dict):
                outer.pop("grievance", None)
                chat_session.last_classification_json = (
                    json.dumps(outer, ensure_ascii=False) if outer else None
                )
        except (TypeError, json.JSONDecodeError):
            pass

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    @classmethod
    def initiate(
        cls,
        chat_session: ChatSession,
        entry_point: str,
        channel: str = "Website",
        mobile_no: str | None = None,
    ) -> Result:
        """Start the wizard from a 'Raise Grievance' link or menu tap."""
        payload = _empty_payload()
        payload["entry_point"] = entry_point

        if chat_session.last_application_id:
            payload["application_id"] = chat_session.last_application_id
            payload["grievance_step"] = STEP_FORM
        else:
            payload["grievance_step"] = STEP_APP_ID

        cls._save_payload(chat_session, payload)
        result = (
            cls._prompt_form(payload, chat_session.scheme)
            if payload["grievance_step"] == STEP_FORM
            else cls._prompt_app_id()
        )
        return cls._to_channel_result(result, chat_session.session_id, channel, mobile_no)

    @classmethod
    def handle(
        cls,
        chat_session: ChatSession,
        message: str,
        channel: str = "Website",
        mobile_no: str | None = None,
    ) -> Result:
        """Main dispatcher – called by ChatManager on every grievance message."""
        try:
            payload = cls._load_payload(chat_session)
            step = payload.get("grievance_step") or STEP_APP_ID
            text = (message or "").strip()

            # Global: Main Menu at any step
            if text == BTN_MAIN_MENU:
                cls.clear_state(chat_session)
                chat_session.intent = "UNKNOWN"
                chat_session.scheme = "Unknown"
                from usi.services.chat.message_helper import send_welcome_message
                return send_welcome_message(
                    chat_session.session_id, channel=channel, mobile_no=mobile_no
                )

            if step == STEP_APP_ID:
                result = cls._step_app_id(payload, text, chat_session)
            elif step == STEP_FORM:
                result = cls._step_form(payload, text, chat_session.scheme)
            elif step == STEP_SUMMARY:
                result = cls._step_summary(payload, text, chat_session)
            elif step == STEP_SUBMITTED:
                result = cls._already_submitted(payload)
            else:
                payload["grievance_step"] = STEP_APP_ID
                result = cls._prompt_app_id()

            # Go Back exits the wizard
            if isinstance(result.data, dict) and result.data.get("_exit_grievance"):
                cls.clear_state(chat_session)
                return cls._route_back(chat_session, payload, channel, mobile_no)

            cls._save_payload(chat_session, payload)
            return cls._to_channel_result(result, chat_session.session_id, channel, mobile_no)

        except Exception:
            frappe.log_error(
                title="Error in GrievanceManager.handle",
                message=traceback.format_exc(),
            )
            return Result.failure(message="Internal Server Error: grievance submission failed")

    # ------------------------------------------------------------------
    # Step handlers
    # ------------------------------------------------------------------

    @classmethod
    def _step_app_id(cls, payload: dict, text: str, chat_session: ChatSession) -> Result:
        if text == BTN_GO_BACK:
            return cls._exit_grievance_result()

        if text == BTN_NO_APP_ID:
            payload["application_id"] = "Not provided"
            payload["grievance_step"] = STEP_FORM
            return cls._prompt_form(payload, chat_session.scheme)

        app_id = cls._extract_application_id(text)
        if app_id:
            payload["application_id"] = app_id
            payload["grievance_step"] = STEP_FORM
            return cls._prompt_form(payload, chat_session.scheme)

        return cls._prompt_app_id(invalid=bool(text))

    @classmethod
    def _step_form(cls, payload: dict, text: str, scheme: str) -> Result:
        """
        Expects: "<ISSUE_TYPE_ID>|<details text>"
        e.g.  "PAYMENT_ISSUE|I received payment for only 1 child..."
        """
        if text == BTN_GO_BACK:
            return cls._exit_grievance_result()

        if "|" not in text:
            return cls._prompt_form(payload, scheme)

        issue_type_id, _, details = text.partition("|")
        issue_type_id = issue_type_id.strip()
        details = details.strip()

        issue_obj = next((it for it in ISSUE_TYPES if it["id"] == issue_type_id), None)
        if not issue_obj:
            return cls._prompt_form(
                payload, scheme,
                error="Invalid issue type. Please choose one from the list."
            )

        if len(details) < MIN_DETAILS_LENGTH:
            return cls._prompt_form(
                payload, scheme,
                error=f"Please describe your issue in at least {MIN_DETAILS_LENGTH} characters.",
            )
        if len(details) > MAX_DETAILS_LENGTH:
            return cls._prompt_form(
                payload, scheme,
                error=f"Description too long. Maximum {MAX_DETAILS_LENGTH} characters.",
            )

        payload["issue_type"]       = issue_type_id
        payload["issue_type_title"] = issue_obj["title"]
        payload["details"]          = details
        payload["request_id"]       = (
            f"GRV-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        )
        payload["grievance_step"] = STEP_SUMMARY
        return cls._prompt_summary(payload, scheme)

    @classmethod
    def _step_summary(cls, payload: dict, text: str, chat_session: ChatSession) -> Result:
        if text == BTN_EDIT:
            payload["grievance_step"] = STEP_FORM
            return cls._prompt_form(payload, chat_session.scheme)

        if text == BTN_PROCEED:
            return cls._call_sampark(payload, chat_session)

        return cls._prompt_summary(payload, chat_session.scheme)

    # ------------------------------------------------------------------
    # Sampark API call (one retry)
    # ------------------------------------------------------------------

    @classmethod
    def _call_sampark(cls, payload: dict, chat_session: ChatSession) -> Result:
        request_data = {
            "scheme_name":       chat_session.scheme or "Unknown",
            "application_id":    payload.get("application_id") or "Not provided",
            "issue_type":        payload.get("issue_type_title") or "Other",
            "grievance_details": payload.get("details") or "",
            "entry_point":       payload.get("entry_point") or "Unknown",
            "mobile_number":     getattr(chat_session, "mobile_no", None) or "Not available",
            "language":          "Hindi",
            "channel":           "SJED WhatsApp Bot",
            "request_id":        payload.get("request_id"),
            "submitted_at":      datetime.now().strftime("%d-%m-%Y %H:%M"),
        }

        last_error = None
        for attempt in range(2):
            try:
                response = STORE.create_ticket(**request_data)
                if response.get("status") == "Created":
                    payload["ticket_id"]      = response["ticket_id"]
                    payload["grievance_step"] = STEP_SUBMITTED
                    cls._log_integration(request_data, response, "Sampark Create Ticket", None)
                    return cls._show_success(response["ticket_id"])

                last_error = response.get("error_message") or "Unknown error"
                payload["retry_count"] = attempt + 1

            except Exception as exc:
                last_error = str(exc)
                payload["retry_count"] = attempt + 1
                frappe.log_error(
                    title=f"Sampark API error (attempt {attempt + 1})",
                    message=traceback.format_exc(),
                )

        cls._log_integration(request_data, {}, "Sampark Create Ticket", last_error)
        return cls._show_failure()

    # ------------------------------------------------------------------
    # Terminal / static state
    # ------------------------------------------------------------------

    @classmethod
    def _already_submitted(cls, payload: dict) -> Result:
        ticket_id = payload.get("ticket_id") or "Unknown"
        return cls._text(
            "यह शिकायत पहले से दर्ज हो चुकी है।\n"
            "This grievance has already been submitted.\n\n"
            f"Ticket ID: {ticket_id}"
        )

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------

    @staticmethod
    def _prompt_app_id(invalid: bool = False) -> Result:
        prefix = (
            "आवेदन आईडी नहीं मिली। कृपया दोबारा दर्ज करें।\n"
            "Application ID not recognised. Please try again.\n\n"
            if invalid else ""
        )
        return Result.success(
            message="grievance_prompt",
            data={
                "interactive_msg": {
                    "title": (
                        prefix
                        + "कृपया अपना आवेदन आईडी दर्ज करें।\n"
                        + "Please enter your Application ID."
                    ),
                    "buttons": [
                        {"id": BTN_NO_APP_ID, "title": "I don't have an application ID"},
                        {"id": BTN_GO_BACK,   "title": "Go Back"},
                    ],
                }
            },
        )

    @staticmethod
    def _prompt_form(payload: dict, scheme: str, error: str | None = None) -> Result:
        app_id     = payload.get("application_id") or "Not provided"
        error_line = f"\n⚠️ {error}\n" if error else ""

        issue_list = "\n".join(
            f"{i + 1}. {it['title']}  [{it['id']}]"
            for i, it in enumerate(ISSUE_TYPES)
        )

        prefill_issue   = payload.get("issue_type_title") or ""
        prefill_details = payload.get("details") or ""
        prefill_block   = ""
        if prefill_issue or prefill_details:
            short = prefill_details[:120] + "..." if len(prefill_details) > 120 else prefill_details
            prefill_block = (
                f"\n📝 Previously entered:\n"
                f"Issue Type : {prefill_issue or '-'}\n"
                f"Details    : {short or '-'}\n"
            )

        title = (
            f"शिकायत दर्ज करें / Raise a Grievance\n"
            f"Scheme: {scheme}  |  Application ID: {app_id}\n"
            f"{error_line}"
            f"{prefill_block}\n"
            f"1️⃣  Issue Type (choose one):\n{issue_list}\n\n"
            f"2️⃣  Describe your issue ({MIN_DETAILS_LENGTH}–{MAX_DETAILS_LENGTH} characters)\n\n"
            f"Reply in this format:\n"
            f"ISSUE_TYPE_ID|Your detailed description\n\n"
            f"Example:\n"
            f"PAYMENT_ISSUE|I received payment for only 1 child out of 3."
        )
        return Result.success(
            message="grievance_prompt",
            data={
                "interactive_msg": {
                    "title": title,
                    "issue_types": ISSUE_TYPES,
                    "prefill": {
                        "issue_type": payload.get("issue_type"),
                        "details":    payload.get("details"),
                    },
                    "buttons": [{"id": BTN_GO_BACK, "title": "Go Back"}],
                }
            },
        )

    @staticmethod
    def _prompt_summary(payload: dict, scheme: str) -> Result:
        app_id  = payload.get("application_id") or "Not provided"
        issue   = payload.get("issue_type_title") or "Other"
        details = payload.get("details") or ""
        display = details[:200] + "…" if len(details) > 200 else details

        title = (
            "आपकी शिकायत / Your Grievance\n\n"
            f"Scheme        : {scheme}\n"
            f"Application ID: {app_id}\n"
            f"Issue Type    : {issue}\n"
            f"Details       : {display}\n\n"
            "आपकी जानकारी SJED Sampark के साथ साझा की जाएगी।\n"
            "Your details will be shared with SJED Sampark to register this grievance."
        )
        return Result.success(
            message="grievance_prompt",
            data={
                "interactive_msg": {
                    "title": title,
                    "buttons": [
                        {"id": BTN_PROCEED,   "title": "Proceed"},
                        {"id": BTN_EDIT,      "title": "Edit"},
                        {"id": BTN_MAIN_MENU, "title": "Main Menu"},
                    ],
                }
            },
        )

    @staticmethod
    def _show_success(ticket_id: str) -> Result:
        return Result.success(
            message="grievance_success",
            data={
                "reply": (
                    "✅ आपकी शिकायत Sampark में दर्ज हो गई है।\n"
                    "Your grievance has been registered with Sampark.\n\n"
                    f"Ticket ID: {ticket_id}\n\n"
                    "कृपया इस Ticket ID को सुरक्षित रखें। आप अपनी शिकायत की "
                    "स्थिति 181 पर कॉल करके, Sampark App या Sampark Portal पर जाँच सकते हैं।\n"
                    "Please keep this Ticket ID safe. You can check the status of your "
                    "grievance by calling 181, or on the Sampark App or Sampark Portal."
                ),
                "show_main_menu_link": True,
            },
        )

    @staticmethod
    def _show_failure() -> Result:
        return Result.success(
            message="grievance_failure",
            data={
                "reply": (
                    "सिस्टम टिकट बनाने में असमर्थ है। कृपया 181 पर कॉल करके या "
                    "Sampark Portal पर अपनी शिकायत दर्ज करें।\n"
                    "System unable to create ticket. Please register your grievance "
                    "at Sampark by calling 181 or at Sampark Portal."
                ),
                "show_main_menu_link": True,
            },
        )

    @staticmethod
    def _text(reply: str) -> Result:
        return Result.success(message="grievance_text", data={"reply": reply})

    @staticmethod
    def _exit_grievance_result() -> Result:
        return Result.success(message="grievance_exit", data={"_exit_grievance": True})

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_application_id(text: str) -> str | None:
        try:
            text = (text or "").strip()
            for pattern in (
                r"\bPALANHAR/\d{4}-\d{2}/\d{3,}\b",
                r"\bSCHOLARSHIP/\d{4}-\d{2}/\d{3,}\b",
            ):
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    return m.group(0).upper()
            if re.fullmatch(r"\d{3,8}", text):
                return text
            m = re.search(r"\b\d{3,8}\b", text)
            if m:
                return m.group()
        except Exception:
            frappe.log_error(
                title="GrievanceManager._extract_application_id error",
                message=traceback.format_exc(),
            )
        return None

    @staticmethod
    def _route_back(
        chat_session: ChatSession,
        payload: dict,
        channel: str,
        mobile_no: str | None,
    ) -> Result:
        entry_point = payload.get("entry_point")
        if entry_point == ENTRY_POINT_RENEW:
            from usi.services.renewal_manager import RenewalManager
            return RenewalManager.handle(chat_session, "", channel=channel, mobile_no=mobile_no)
        from usi.services.chat.message_helper import send_intent_selection_message
        return send_intent_selection_message(
            chat_session.session_id,
            channel=channel,
            mobile_no=mobile_no,
            scheme=chat_session.scheme,
        )

    @staticmethod
    def _to_channel_result(
        result: Result,
        session_id: str | None,
        channel: str,
        mobile_no: str | None,
    ) -> Result:
        data          = result.data if isinstance(result.data, dict) else {}
        interactive   = data.get("interactive_msg")
        reply         = data.get("reply")
        show_main_menu = data.get("show_main_menu_link", False)

        if channel == "Website":
            out: dict[str, Any] = {"session_id": session_id}
            if interactive:
                out["interactive_msg"] = interactive
            if reply:
                out["reply"] = reply
            if show_main_menu:
                out["show_main_menu_link"] = True
            return Result.success(message="Response generated successfully", data=out)

        # WhatsApp
        if interactive:
            msg = frappe.get_doc({
                "doctype": "WhatsApp Message", "to": mobile_no,
                "message": interactive.get("title") or "",
                "type": "Outgoing", "content_type": "interactive",
                "buttons": json.dumps(interactive.get("buttons") or []),
            })
            msg.insert(ignore_permissions=True)
            return Result.success(message="Response generated successfully", data={})

        if reply:
            msg = frappe.get_doc({
                "doctype": "WhatsApp Message", "to": mobile_no,
                "content_type": "text", "message": reply, "type": "Outgoing",
            })
            msg.insert(ignore_permissions=True)
            return Result.success(message="Response generated successfully", data={})

        return Result.success(
            message="Response generated successfully", data={"session_id": session_id}
        )

    @staticmethod
    def _log_integration(
        request_data: dict, response_data: dict, service_name: str, error_data: Any
    ) -> None:
        try:
            from usi.utils.utils import log_integration_request
            log_integration_request(
                request_data=request_data,
                response_data=response_data,
                service_name=service_name,
                request_description=f"Grievance – request_id: {request_data.get('request_id')}",
                error_data=error_data,
                reference_doctype=None,
                reference_docname=None,
                error_title=f"{service_name} Error" if error_data else None,
            )
        except Exception:
            frappe.log_error(
                title="GrievanceManager._log_integration error",
                message=traceback.format_exc(),
            )
