import frappe
import json
import requests
import xml.etree.ElementTree as ET
from typing import Any
from usi.models.result import Result
from usi.utils import utils
from pathlib import Path
from functools import lru_cache
# from usi.utils.xml_parser import get_application_status




class PalanhaarManager:
    @frappe.whitelist(allow_guest=True)
    def get_application_status(application_id):
        url = "https://sjmsnew.rajasthan.gov.in/palanhaar/Tracking.asmx/APPLICATIONSTATUSChatBot"
        payload = {
            "APPLICATIONID": application_id
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        try:
            response = requests.post(
                url,
                data=payload,
                headers=headers,
                timeout=30
            )
        
            response.raise_for_status()
        
            root = ET.fromstring(response.content)
        
            json_string = root.text
        
            if not json_string:
                frappe.throw("Empty response from Palanhar API")
        
            return json.loads(json_string)
        
        except requests.exceptions.ConnectionError:
            frappe.throw(
                "Unable to connect to Palanhar API. "
                "Please check server internet/network connectivity."
            )
        
        except requests.exceptions.Timeout:
            frappe.throw("Palanhar API request timed out.")
        
        except ET.ParseError:
                frappe.throw("Invalid XML response received from Palanhar API.")
        
        except json.JSONDecodeError:
            frappe.throw("API response contains invalid JSON.")
    ...  # rest of the function exactly as it was

    # ------------------------------------------------------------
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
        
        if not application_id:
            return Result.failure(message="Application ID is required and cannot be empty")
            

        result_data: dict[str, Any] = {}
        error_data: Any = None

        try:
            
            rows = PalanhaarManager.get_application_status(application_id)
            allowed_field_rows ={
                  "1", "2", "3", "5",
                    "8",
                   "10", "11", "12", "13", "14", "15", "16"
            }
            filtered_rows =[
                row
                for row in rows
                if isinstance(row, dict)
                and str(row.get("FieldNo")) in allowed_field_rows
            ]


            if not filtered_rows:
                error_data = "No application status found"

                return Result.not_found(
                    message="No Palanhar application status found",
                    data=error_data
                )
            if not isinstance(rows, list):
                return Result.failure(
                   message="Invalid Palanhar application status response",
                   error_data="Expected a list of status entries"
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
                "status": filtered_rows
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