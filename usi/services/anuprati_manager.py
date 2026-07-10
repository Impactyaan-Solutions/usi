import frappe
from functools import lru_cache
from pathlib import Path


class AnupratiManager:

    # ----------------------------------------------------------------
    # FAQ
    # ----------------------------------------------------------------
    @classmethod
    def get_anuprati_faq(cls) -> str:
        """
        Read and return the Anuprati FAQ content
        from prompt/anuprati/FAQ.txt.
        """
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
    def fetch_anuprati_status(cls, application_id: str):
        """
        Steps to implement:

        1. Validate that application_id is provided.
           - If empty, return Result.failure(...)

        2. Read the Anuprati Status API URL from site_config.json.
           - Fallback to the default API URL if not configured.

        3. Create a request session using:
           frappe.utils.get_request_session()

        4. Prepare the request payload.
           Example:
           {
               "SchemeName": "ANUPRATI",
               "ApplicationNo": application_id
           }

        5. Send a POST request to the API.

        6. Raise an exception for HTTP errors.

        7. Parse the JSON response.

        8. If isSuccess is False:
           - Return Result.failure with the API error message.

        9. Read the "data" array from the response.

        10. If the data array is empty:
            - Return Result.not_found(...)

        11. Take the latest status record (first element).

        12. Prepare the response object containing:
            - application number
            - scheme name
            - status details returned by the API

        13. Return Result.success(...) with the formatted data.

        14. Handle any exceptions:
            - Log the traceback using frappe.log_error().
            - Return Result.failure(...)

        15. In the finally block:
            - Call utils.log_integration_request(...)
            - Log request data, response data, service name,
              description, and any errors.
        """
        pass