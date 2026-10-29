"""
app/services/prompt_compiler.py — Dynamic System Prompt Compiler

Compiles production-grade LLM system prompts for the AI Voice Receptionist.
Injects:
  - Spoken telephony rules (no markdown, sub-20 word sentence chunks, speech cadence)
  - Identity, business profile, timezone, contact info
  - Weekly operating schedule
  - Active services menu with durations and pricing
  - Custom organizational policies and guardrails
"""

from app.models.agent import AgentConfig
from app.models.business import Business, WorkingHours
from app.models.service import Service


def compile_voice_system_prompt(
    agent: AgentConfig,
    business: Business | None,
    working_hours: list[WorkingHours] | None = None,
    services: list[Service] | None = None,
) -> str:
    """
    Generate the complete production system prompt for runtime voice orchestration.
    """
    business_name = business.name if business else "the business"
    industry = business.industry if business else "professional services"
    timezone = business.timezone if business else "UTC"
    phone = business.phone_number if business and business.phone_number else "Not specified"
    address = business.address if business and business.address else "Not specified"

    # Format operating hours
    hours_lines = []
    if working_hours:
        for wh in working_hours:
            if wh.is_closed:
                hours_lines.append(f"  - {wh.day_of_week.value.capitalize()}: Closed")
            else:
                open_str = wh.open_time.strftime("%I:%M %p") if wh.open_time else "Open"
                close_str = wh.close_time.strftime("%I:%M %p") if wh.close_time else "Close"
                hours_lines.append(f"  - {wh.day_of_week.value.capitalize()}: {open_str} to {close_str}")
    hours_block = "\n".join(hours_lines) if hours_lines else "  - Mon-Fri: 9:00 AM to 6:00 PM (Standard)"

    # Format services
    services_lines = []
    if services:
        for s in services:
            if s.is_active:
                price_str = f"{s.price // 100} {s.currency}" if s.price > 0 else "Free"
                services_lines.append(f"  - {s.name} ({s.duration_minutes} mins, {price_str})")
    services_block = "\n".join(services_lines) if services_lines else "  - General Consultation"

    # Base spoken rules
    prompt = f"""You are {agent.name}, an AI voice receptionist for {business_name} ({industry}).
Role: {agent.role_description}.
Operating Timezone: {timezone}.
Business Phone: {phone}.
Address: {address}.

### VOICE CONVERSATION RULES:
1. You are speaking to the customer over a phone call.
2. Keep all responses very concise: 1 to 2 short sentences at a time.
3. NEVER use markdown formatting, asterisks (*), bullets, numbered lists, emojis, or URLs. The TTS audio engine will read them aloud awkwardly.
4. Speak naturally, warmly, and professionally.
5. If the caller asks to book an appointment, gather their name, preferred date and time, and the specific service they need.
6. If the caller requests something outside your scope or asks for a human, offer to transfer them to human staff.

### OPERATING HOURS:
{hours_block}

### OFFERED SERVICES & TREATMENTS:
{services_block}
"""

    if agent.transfer_phone_number:
        prompt += f"\nHuman Escalation Number: {agent.transfer_phone_number}\n"

    if agent.system_prompt:
        prompt += f"\n### SPECIFIC BUSINESS POLICIES & INSTRUCTIONS:\n{agent.system_prompt}\n"

    return prompt.strip()

