"""
app/ai/tools/definitions.py — Voice Agent Tool Calling Schemas

Defines OpenAI and Groq compatible tool/function calling schemas for:
  - Checking calendar availability
  - Booking new appointments
  - Confirming existing bookings
  - Rescheduling slots
  - Cancelling appointments
  - Escalating to human receptionists
  - Ending the call gracefully
"""

from typing import Any

VOICE_AGENT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check open booking slots for a requested date and duration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_date": {
                        "type": "string",
                        "description": "Date to query in YYYY-MM-DD format (e.g. 2026-11-21).",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Duration of service in minutes (e.g. 30, 45, 60). Defaults to 30.",
                        "default": 30,
                    },
                },
                "required": ["target_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a new appointment slot for a customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Full name of the caller/patient.",
                    },
                    "customer_phone": {
                        "type": "string",
                        "description": "Customer phone number in E.164 format (e.g. +919876543210).",
                    },
                    "scheduled_at": {
                        "type": "string",
                        "description": "Scheduled start datetime in ISO format (e.g. 2026-11-21T10:30:00Z).",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Duration in minutes. Defaults to 30.",
                        "default": 30,
                    },
                    "service_name": {
                        "type": "string",
                        "description": "Optional name of the requested service (e.g. General Consultation, Dental Checkup).",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes or reason for visit provided by customer.",
                    },
                },
                "required": ["customer_name", "customer_phone", "scheduled_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_appointment",
            "description": "Confirm that customer will attend their existing upcoming appointment slot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "UUID of the appointment to confirm (optional if already active in current call session).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing appointment to a new open slot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "UUID of the appointment to reschedule (optional if active in current call session).",
                    },
                    "new_time": {
                        "type": "string",
                        "description": "New ISO datetime for the appointment (e.g. 2026-11-22T14:00:00Z).",
                    },
                },
                "required": ["new_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "UUID of the appointment to cancel.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason given by customer for cancelling.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Search the business knowledge base, FAQs, policies, pricing, operating rules, directions, or doctor/staff info to answer customer questions accurately.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query or topic to look up in the business knowledge base.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": "Escalate the phone call to a human receptionist or doctor when the customer requests a human or inquiry is beyond AI capabilities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for human escalation.",
                    },
                },
                "required": ["reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "end_call",
            "description": "Gracefully end the phone call once the customer's request has been completed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Brief summary of call outcome.",
                    },
                },
            },
        },
    },
]
