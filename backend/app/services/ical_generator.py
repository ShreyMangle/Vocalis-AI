"""
app/services/ical_generator.py — RFC 5545 iCalendar Feed Generator

Enables calendar synchronization with Google Calendar, Apple Calendar, and Outlook.
Generates compliant .ics text payloads.
"""

from datetime import datetime, timedelta, timezone

from app.models.appointment import Appointment, AppointmentStatus


def generate_ical_feed(
    appointments: list[Appointment],
    calendar_name: str = "VoxAI Appointments",
) -> str:
    """
    Generate an RFC 5545 compliant iCalendar string for a list of appointments.
    """
    now_utc_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//VoxAI//AI Voice Operations Platform//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{calendar_name}",
    ]

    for appt in appointments:
        start_utc = appt.scheduled_at.astimezone(timezone.utc)
        end_utc = start_utc + timedelta(minutes=appt.duration_minutes)

        start_str = start_utc.strftime("%Y%m%dT%H%M%SZ")
        end_str = end_utc.strftime("%Y%m%dT%H%M%SZ")

        service_title = appt.service.name if appt.service else "Appointment"
        summary = f"{appt.customer_name} — {service_title}"
        description = (appt.notes or "").replace("\n", " ")

        status_str = "CONFIRMED"
        if appt.status == AppointmentStatus.CANCELLED:
            status_str = "CANCELLED"

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{appt.id}@voxai.com",
                f"DTSTAMP:{now_utc_str}",
                f"DTSTART:{start_str}",
                f"DTEND:{end_str}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{description}",
                f"STATUS:{status_str}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"

