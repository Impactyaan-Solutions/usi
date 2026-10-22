"""
Dummy Sampark Grievance store.

This class is the ONLY place that should talk to the Sampark grievance backend.
Today it reads usi/data/sampark_grievance_dummy.json and simulates ticket creation
with an auto-incrementing counter.

When the Sampark API is available, add a live client with the same method
signatures (create_ticket, get_ticket_status) and change GrievanceManager.STORE
to that client. Do not change the chat wizard.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Optional
import json
import uuid

import frappe


class DummySamparkStore:
    """Stand-in for the Sampark Grievance API."""

    # In-memory counter so each new dummy ticket gets a unique number per process.
    _ticket_counter: int = 100006

    @staticmethod
    @lru_cache(maxsize=1)
    def _load() -> dict[str, Any]:
        path = (
            Path(frappe.get_app_path("usi")) / "data" / "sampark_grievance_dummy.json"
        )
        return json.loads(path.read_text(encoding="utf-8"))

    def create_ticket(
        self,
        scheme_name: str,
        application_id: str,
        issue_type: str,
        grievance_details: str,
        entry_point: str,
        mobile_number: str,
        language: str,
        channel: str,
        request_id: str,
        submitted_at: str,
    ) -> dict[str, Any]:
        """
        Submit a grievance to Sampark and return the ticket result.

        Live API later: POST Sampark API with the above fields -> ticket_id.

        Dummy behaviour:
        - Returns a pre-seeded ticket if request_id matches a known fixture.
        - Simulates failure if request_id is in simulated_failures.
        - Otherwise mints a new SMP-XXXXXX ticket ID on the fly.

        Returns dict with keys: status, ticket_id, registered_at, error_message
        """
        data = self._load()

        # Check simulated failures first
        if request_id in (data.get("simulated_failures") or []):
            return {
                "status": "Failed",
                "ticket_id": None,
                "registered_at": None,
                "error_message": "Simulated failure for testing retry logic.",
            }

        # Check if a fixture ticket exists for this request_id
        tickets = data.get("tickets") or {}
        if request_id in tickets:
            existing = tickets[request_id]
            return {
                "status": "Created",
                "ticket_id": existing["ticket_id"],
                "registered_at": existing["registered_at"],
                "error_message": None,
            }

        # Mint a new ticket ID
        DummySamparkStore._ticket_counter += 1
        ticket_id = f"SMP-{DummySamparkStore._ticket_counter}"

        return {
            "status": "Created",
            "ticket_id": ticket_id,
            "registered_at": submitted_at,
            "error_message": None,
        }

    def get_ticket_status(self, ticket_id: str) -> Optional[dict[str, Any]]:
        """
        Fetch status of an existing Sampark ticket.

        Live API later: GET Sampark API status(ticket_id).
        Dummy: look up from fixture data; return None if not found.
        """
        ticket_id = (ticket_id or "").strip()
        tickets = (self._load().get("tickets") or {}).values()
        match = next((t for t in tickets if t.get("ticket_id") == ticket_id), None)
        if not match:
            return None

        return {
            "ticket_id": match["ticket_id"],
            "status": match.get("status") or "Unknown",
            "scheme_name": match.get("scheme_name"),
            "application_id": match.get("application_id"),
            "issue_type": match.get("issue_type"),
            "registered_at": match.get("registered_at"),
        }
