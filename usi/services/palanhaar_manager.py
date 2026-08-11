import frappe
import json
from typing import Any
from usi.models.result import Result
from usi.utils import utils
from pathlib import Path
from functools import lru_cache

PALANHAR_STATUS_API_URL = "https://sjmsnew.rajasthan.gov.in/ScholarShipApi/api/Scholarship/SJEDApplication_Status"


class PalanhaarManager:

    # ----------------------------------------------------------------
    # FAQ
    # ----------------------------------------------------------------
    @classmethod
    def get_palanhar_faq(cls) -> str:
        return cls._read_text_file("palanhaar/FAQ.txt")

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
    def fetch_palanhar_status(cls, application_id: str) -> Result:
        """
        Fetch live Palanhar application status.

        Uses SJED Application Status API:
        POST https://sjmsnew.rajasthan.gov.in/ScholarShipApi/api/Scholarship/SJEDApplication_Status

        Request body:
        {
            "SchemeName": "PALANHAAR",
            "ApplicationNo": "<application_id>"
        }

        Returns only the latest status entry: data[0]
        """
        if not application_id:
            return Result.failure(message="Application ID is required and cannot be empty")

        result_data: dict[str, Any] = {}
        error_data: Any = None

        try:
            # Allow overriding URL via site_config.json if needed
            site_config = frappe.get_site_config() or {}
            url = site_config.get("PALANHAR_STATUS_API_URL") or PALANHAR_STATUS_API_URL

            session = frappe.utils.get_request_session()

            request_body = {
                "SchemeName": "PALANHAAR",
                "ApplicationNo": application_id,
            }

            res = session.post(
                url,
                json=request_body,
                timeout=12,
            )
            res.raise_for_status()
            payload: dict[str, Any] = res.json() if res.content else {}

            # API returned isSuccess: false
            if not payload.get("isSuccess"):
                error_data = payload.get("errorMessage") or "Unknown error"
                return Result.failure(
                    message="Failed to fetch Palanhar application status",
                    error_data=error_data
                )

            rows = payload.get("data") or []

            # API returned empty data array
            if not isinstance(rows, list) or not rows:
                error_data = "No application status found"
                return Result.not_found(
                    message="No Palanhar application status found",
                    data=error_data
                )

            # Take only the latest entry (first in list)
            latest = rows[0] if isinstance(rows[0], dict) else None
            if not latest:
                error_data = "No application status found"
                return Result.failure(
                    message="Failed to fetch Palanhar application status",
                    error_data=error_data
                )

            result_data = {
                "applicationNo": application_id,
                "scheme": "PALANHAAR",
                **latest
            }

            return Result.success(
                message="Palanhar application status fetched successfully",
                data=result_data
            )

        except Exception:
            error_data = frappe.get_traceback()
            frappe.log_error(
                frappe.get_traceback(),
                "Palanhar Assistant: status lookup failed"
            )
            return Result.failure(
                message="Failed to fetch Palanhar application status",
                error_data=error_data
            )

        finally:
            utils.log_integration_request(
                request_data={"application_id": application_id},
                response_data=result_data if isinstance(result_data, dict) else {},
                service_name='Fetch Palanhar Application Status',
                request_description=f'Fetch application status for application ID: {application_id}',
                error_data=error_data,
                reference_doctype=None,
                reference_docname=None,
                error_title='Fetch Palanhar Application Status Error',
            )