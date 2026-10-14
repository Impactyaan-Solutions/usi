import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import frappe
from usi.models.result import Result
from usi.utils import utils

ANUPRATI_STATUS_API_URL = "https://sjmsnew.rajasthan.gov.in/ScholarShipApi/api/Anuprati/Anuprati_SamadhanSathi"


class AnupratiManager:

    # ----------------------------------------------------------------
    # FAQ
    # ----------------------------------------------------------------
    @classmethod
    def get_anuprati_faq(cls) -> str:
        """Read and return the Anuprati FAQ content from prompt/anuprati/FAQ.txt."""
        return cls._read_text_file("anuprati/FAQ.txt")

    @staticmethod
    @lru_cache(maxsize=64)
    def _read_text_file(filename: str) -> str:
        app_root = Path(frappe.get_app_path("usi"))
        path = app_root / "prompt" / filename
        return path.read_text(encoding="utf-8")

    # ----------------------------------------------------------------
    # STATUS
    # ----------------------------------------------------------------
    @classmethod
    def fetch_anuprati_status(cls, application_id: str) -> Result:
        """Fetch live Anuprati application status.

        Uses SJED Application Status API: POST
        https://sjmsnew.rajasthan.gov.in/ScholarShipApi/api/Anuprati/Anuprati_SamadhanSathi

        Request query/params:
        {"ApplicationNo": "DoSJED/ANUPRACOA/2024/415412"}

        Returns only the latest status entry.
        """
        if not application_id:
            return Result.failure(message="Application ID is required and cannot be empty")

        result_data: dict[str, Any] = {}
        error_data: Any = None

        try:
            # Allow overriding URL via site_config.json if needed
            site_config = frappe.get_site_config() or {}
            url = site_config.get("ANUPRATI_STATUS_API_URL") or ANUPRATI_STATUS_API_URL

            session = frappe.utils.get_request_session()

            res = session.get(
                url,
                params={"ApplicationNo": application_id},
                headers={
                    "Accept": "*/*",
                    "Connection": "close",
                    "Content-Type": "application/json",
                },
                timeout=12,
            )
            res.raise_for_status()
            payload = res.json() if res.content else {}
            frappe.log_error(
                title="Anuprati API Raw Response",
                message=frappe.as_json({
                    "status_code": res.status_code,
                    "application_id": application_id,
                    "response": payload,
                }),
            )

            if isinstance(payload, list):
                rows = payload
            elif isinstance(payload, dict):
                if not payload.get("isSuccess", True):
                    error_data = payload.get("errorMessage") or "Unknown error"
                    return Result.failure(
                        message="Failed to fetch Anuprati application status",
                        error_data=error_data,
                    )
                rows = payload.get("data") or []
            else:
                error_data = "Unexpected API response format"
                return Result.failure(
                    message="Failed to fetch Anuprati application status",
                    error_data=error_data,
                )

            if not isinstance(rows, list) or not rows:
                error_data = "No application status found"
                return Result.failure(
                    message="Failed to fetch Anuprati application status",
                    error_data=error_data,
                )

            latest = rows[0]
            if not isinstance(latest, dict):
               error_data = "Unexpected application status entry format"
               return Result.failure(
                   message="Failed to fetch Anuprati application status",
                   error_data=error_data,
            )
            result_data = {
                "applicationNo": application_id,
                "scheme": "ANUPRATI",
                **latest,
            }

            return Result.success(
                message="Anuprati application status fetched successfully",
                data=result_data,
            )

        except Exception:
            error_data = frappe.get_traceback()
            frappe.log_error(
                frappe.get_traceback(),
                "Anuprati Assistant: status lookup failed",
            )
            return Result.failure(
                message="Failed to fetch Anuprati application status",
                error_data=error_data,
            )

        finally:
            utils.log_integration_request(
                request_data={"application_id": application_id},
                response_data=result_data if isinstance(result_data, dict) else {},
                service_name="Fetch Anuprati Application Status",
                request_description=f"Fetch application status for application ID: {application_id}",
                error_data=error_data,
                reference_doctype=None,
                reference_docname=None,
                error_title="Fetch Anuprati Application Status Error",
            )