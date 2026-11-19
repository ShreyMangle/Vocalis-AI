"""
app/ai/tools/executor.py — Tool Execution Engine

Safely executes tool calls initiated by the AI Voice Agent during calls.
Integrates directly with SQLAlchemy models, slot scheduling algorithms,
and database transactions.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus
from app.models.business import Business
from app.models.service import Service
from app.services.scheduler import check_slot_conflict, get_available_slots_for_date

logger = structlog.get_logger(__name__)


@dataclass
class ToolExecutionResult:
    """Standard outcome from executing a voice agent tool."""
    tool_name: str
    success: bool
    message: str
    data: dict[str, Any]
    action: str | None = None  # None | "transfer" | "hangup"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "action": self.action,
        }


class ToolExecutor:
    """Executes voice agent functions against tenant operational database."""

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        business_id: uuid.UUID,
        current_appointment_id: uuid.UUID | None = None,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.business_id = business_id
        self.current_appointment_id = current_appointment_id

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        """Route tool call to appropriate handler."""
        logger.info(
            "Executing voice agent tool",
            tool_name=tool_name,
            tenant_id=str(self.tenant_id),
            arguments=arguments,
        )

        handlers = {
            "check_availability": self._check_availability,
            "book_appointment": self._book_appointment,
            "confirm_appointment": self._confirm_appointment,
            "reschedule_appointment": self._reschedule_appointment,
            "cancel_appointment": self._cancel_appointment,
            "escalate_to_human": self._escalate_to_human,
            "end_call": self._end_call,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                message=f"Unknown tool '{tool_name}'.",
                data={},
            )

        try:
            return await handler(arguments)
        except Exception as e:
            logger.error("Error executing tool", tool_name=tool_name, error=str(e))
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                message=f"System error executing {tool_name}: {str(e)}",
                data={},
            )

    async def _get_business(self) -> Business | None:
        res = await self.session.execute(
            select(Business).where(
                Business.id == self.business_id,
                Business.is_deleted == False,  # noqa: E712
            )
        )
        return res.scalar_one_or_none()

    async def _check_availability(self, args: dict[str, Any]) -> ToolExecutionResult:
        business = await self._get_business()
        if not business:
            return ToolExecutionResult(
                tool_name="check_availability",
                success=False,
                message="Business profile not found.",
                data={},
            )

        target_date_str = args.get("target_date")
        if not target_date_str:
            return ToolExecutionResult(
                tool_name="check_availability",
                success=False,
                message="Missing target_date argument.",
                data={},
            )

        try:
            target_date = date.fromisoformat(target_date_str)
        except ValueError:
            return ToolExecutionResult(
                tool_name="check_availability",
                success=False,
                message="Invalid date format. Use YYYY-MM-DD.",
                data={},
            )

        duration = int(args.get("duration_minutes", 30))
        slots = await get_available_slots_for_date(
            session=self.session,
            business=business,
            target_date=target_date,
            duration_minutes=duration,
        )

        formatted_slots = [s["formatted_time"] for s in slots]
        if not formatted_slots:
            return ToolExecutionResult(
                tool_name="check_availability",
                success=True,
                message=f"No available slots on {target_date_str}. The business may be closed or fully booked.",
                data={"available_slots": []},
            )

        preview = ", ".join(formatted_slots[:5])
        return ToolExecutionResult(
            tool_name="check_availability",
            success=True,
            message=f"Found {len(formatted_slots)} available slots on {target_date_str}: {preview}.",
            data={"available_slots": formatted_slots},
        )

    async def _book_appointment(self, args: dict[str, Any]) -> ToolExecutionResult:
        name = args.get("customer_name", "").strip()
        phone = args.get("customer_phone", "").strip()
        time_str = args.get("scheduled_at", "").strip()

        if not name or not phone or not time_str:
            return ToolExecutionResult(
                tool_name="book_appointment",
                success=False,
                message="Customer name, phone number, and scheduled time are required.",
                data={},
            )

        try:
            scheduled_dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            if scheduled_dt.tzinfo is None:
                scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
        except Exception:
            return ToolExecutionResult(
                tool_name="book_appointment",
                success=False,
                message="Invalid scheduled_at datetime format.",
                data={},
            )

        duration = int(args.get("duration_minutes", 30))

        # Check collision
        has_conflict = await check_slot_conflict(
            session=self.session,
            tenant_id=self.tenant_id,
            business_id=self.business_id,
            start_time=scheduled_dt,
            duration_minutes=duration,
        )

        if has_conflict:
            return ToolExecutionResult(
                tool_name="book_appointment",
                success=False,
                message="Requested time slot is already booked. Please offer an alternate slot.",
                data={"conflict": True},
            )

        # Optional service lookup
        service_id = None
        service_name = args.get("service_name")
        if service_name:
            s_res = await self.session.execute(
                select(Service).where(
                    Service.business_id == self.business_id,
                    Service.is_active == True,  # noqa: E712
                    Service.name.ilike(f"%{service_name}%"),
                )
            )
            svc = s_res.scalar_one_or_none()
            if svc:
                service_id = svc.id
                duration = svc.duration_minutes

        appointment = Appointment(
            tenant_id=self.tenant_id,
            business_id=self.business_id,
            service_id=service_id,
            customer_name=name,
            customer_phone=phone,
            scheduled_at=scheduled_dt,
            duration_minutes=duration,
            status=AppointmentStatus.CONFIRMED,
            notes=args.get("notes", "Booked via AI Voice Receptionist"),
            created_by_agent=True,
        )

        self.session.add(appointment)
        await self.session.commit()
        await self.session.refresh(appointment)

        return ToolExecutionResult(
            tool_name="book_appointment",
            success=True,
            message=f"Appointment successfully confirmed for {name} on {scheduled_dt.strftime('%A, %b %d at %I:%M %p')}.",
            data={
                "appointment_id": str(appointment.id),
                "scheduled_at": appointment.scheduled_at.isoformat(),
            },
        )

    async def _resolve_appointment(self, appt_id_str: str | None) -> Appointment | None:
        target_id = None
        if appt_id_str:
            try:
                target_id = uuid.UUID(appt_id_str)
            except ValueError:
                pass
        if not target_id:
            target_id = self.current_appointment_id

        if not target_id:
            return None

        res = await self.session.execute(
            select(Appointment).where(
                Appointment.id == target_id,
                Appointment.tenant_id == self.tenant_id,
                Appointment.is_deleted == False,  # noqa: E712
            )
        )
        return res.scalar_one_or_none()

    async def _confirm_appointment(self, args: dict[str, Any]) -> ToolExecutionResult:
        appt = await self._resolve_appointment(args.get("appointment_id"))
        if not appt:
            return ToolExecutionResult(
                tool_name="confirm_appointment",
                success=False,
                message="Appointment record could not be found to confirm.",
                data={},
            )

        appt.status = AppointmentStatus.CONFIRMED
        appt.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

        return ToolExecutionResult(
            tool_name="confirm_appointment",
            success=True,
            message=f"Appointment on {appt.scheduled_at.strftime('%A, %b %d at %I:%M %p')} has been confirmed.",
            data={"appointment_id": str(appt.id), "status": "CONFIRMED"},
        )

    async def _reschedule_appointment(self, args: dict[str, Any]) -> ToolExecutionResult:
        appt = await self._resolve_appointment(args.get("appointment_id"))
        if not appt:
            return ToolExecutionResult(
                tool_name="reschedule_appointment",
                success=False,
                message="Appointment record could not be found to reschedule.",
                data={},
            )

        new_time_str = args.get("new_time", "").strip()
        try:
            new_dt = datetime.fromisoformat(new_time_str.replace("Z", "+00:00"))
            if new_dt.tzinfo is None:
                new_dt = new_dt.replace(tzinfo=timezone.utc)
        except Exception:
            return ToolExecutionResult(
                tool_name="reschedule_appointment",
                success=False,
                message="Invalid new_time format.",
                data={},
            )

        # Check collision
        has_conflict = await check_slot_conflict(
            session=self.session,
            tenant_id=self.tenant_id,
            business_id=self.business_id,
            start_time=new_dt,
            duration_minutes=appt.duration_minutes,
            exclude_appointment_id=appt.id,
        )

        if has_conflict:
            return ToolExecutionResult(
                tool_name="reschedule_appointment",
                success=False,
                message="The requested new time slot is not available. Please suggest an alternative.",
                data={"conflict": True},
            )

        appt.original_scheduled_at = appt.scheduled_at
        appt.scheduled_at = new_dt
        appt.status = AppointmentStatus.RESCHEDULED
        appt.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

        return ToolExecutionResult(
            tool_name="reschedule_appointment",
            success=True,
            message=f"Appointment successfully rescheduled to {new_dt.strftime('%A, %b %d at %I:%M %p')}.",
            data={
                "appointment_id": str(appt.id),
                "new_time": appt.scheduled_at.isoformat(),
            },
        )

    async def _cancel_appointment(self, args: dict[str, Any]) -> ToolExecutionResult:
        appt = await self._resolve_appointment(args.get("appointment_id"))
        if not appt:
            return ToolExecutionResult(
                tool_name="cancel_appointment",
                success=False,
                message="Appointment record could not be found to cancel.",
                data={},
            )

        appt.status = AppointmentStatus.CANCELLED
        reason = args.get("reason")
        if reason:
            appt.notes = f"{appt.notes or ''} [Cancelled: {reason}]".strip()
        appt.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

        return ToolExecutionResult(
            tool_name="cancel_appointment",
            success=True,
            message="Your appointment has been successfully cancelled.",
            data={"appointment_id": str(appt.id), "status": "CANCELLED"},
        )

    async def _escalate_to_human(self, args: dict[str, Any]) -> ToolExecutionResult:
        reason = args.get("reason", "Caller requested human assistance.")
        return ToolExecutionResult(
            tool_name="escalate_to_human",
            success=True,
            message="Connecting you to human staff right away. Please hold.",
            data={"reason": reason},
            action="transfer",
        )

    async def _end_call(self, args: dict[str, Any]) -> ToolExecutionResult:
        summary = args.get("summary", "Call completed.")
        return ToolExecutionResult(
            tool_name="end_call",
            success=True,
            message="Thank you for calling. Have a wonderful day!",
            data={"summary": summary},
            action="hangup",
        )
