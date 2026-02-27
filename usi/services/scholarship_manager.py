import frappe
from typing import Any
from usi.models.result import Result
from usi.utils import utils
from pathlib import Path
from functools import lru_cache
SJMS_STATUS_API_URL = "https://sjmsnew.rajasthan.gov.in/ScholarShipApi/api/Scholarship/ScholarShipStatus"

class ScholarshipManager:
    
    @classmethod
    def get_scholarship_faq(cls) -> str:
        return cls._read_text_file("scholarships/FAQ.txt")

    @staticmethod
    @lru_cache(maxsize=64)
    def _read_text_file(filename: str) -> str:
        # Robust path resolution (never relative to /usi/api)
        app_root = Path(frappe.get_app_path("usi"))
        path = app_root / "prompt" / filename
        return path.read_text(encoding="utf-8")
    
    @classmethod
    def fetch_application_status(cls, application_id: str) -> Result:
        """
        Fetch live application status from your backend.

        Uses SJMS API:
        POST https://sjmsnew.rajasthan.gov.in/ScholarShipApi/api/Scholarship/ScholarShipStatus?ScholarshipNumber=<id>

        We only return the *latest* status entry: data[0]
        """
        if not application_id:
            return Result.failure(message="Application ID is required and cannot be empty")
        result_data: dict[str, Any] = {}
        error_data: Any = None
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
                error_data = payload.get("errorMessage") or "Unknown error"
                return Result.failure(message="Failed to fetch application status", error_data=error_data)

            rows = payload.get("data") or []
            if not isinstance(rows, list) or not rows:
                error_data = "No application status found"
                return Result.not_found(message="No application status found", data=error_data)

            latest = rows[0] if isinstance(rows[0], dict) else None
            if not latest:
                error_data = "No application status found"
                return Result.failure(message="Failed to fetch application status", error_data=error_data)
            result_data = {"scholarshipNumber": application_id, **latest}
            # Return only the latest entry (plus the queried scholarship number for traceability)
            return Result.success(message="Application status fetched successfully", data=result_data)
        except Exception:
            error_data = frappe.get_traceback()
            frappe.log_error(frappe.get_traceback(), "Scholarship Assistant: status lookup failed")
            return Result.failure(message="Failed to fetch application status", error_data=error_data) 
        finally:
            utils.log_integration_request(
                request_data={"application_id": application_id},
                response_data=result_data if isinstance(result_data, dict) else {},
                service_name='Fetch Scholarship Application Status',
                request_description='Fetch application status for application ID: {application_id}',
                error_data=error_data,
                reference_doctype=None,
                reference_docname=None,
                error_title='Fetch Scholarship Application Status Error',
            )