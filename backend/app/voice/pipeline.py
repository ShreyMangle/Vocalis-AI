"""
app/voice/pipeline.py — Real-Time Voice WebSocket Pipeline

Orchestrates the entire sub-second conversational loop:
  1. Ingestion: 8kHz G.711 mu-law or 16kHz PCM audio frames over WebSocket
  2. VAD: Speech boundary detection and sub-millisecond barge-in interruption
  3. STT: Whisper / Deepgram voice transcription
  4. Intelligence: LLM conversational reasoning and tool execution
  5. TTS: Streaming sentence synthesis back over the WebSocket
  6. Persistence: Transactional call telemetry and analytics logging
"""

import asyncio
import base64
import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import WebSocket
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.base import LLMMessage
from app.ai.llm.factory import get_llm_provider
from app.ai.tools.definitions import VOICE_AGENT_TOOLS
from app.ai.tools.executor import ToolExecutor
from app.core.config import settings
from app.models.agent import AgentConfig
from app.models.appointment import Appointment
from app.models.business import Business, WorkingHours
from app.models.call import Call, CallDirection, CallSentiment, CallStatus
from app.models.service import Service
from app.services.prompt_compiler import compile_voice_system_prompt
from app.voice.session import CallSession
from app.voice.stt import transcribe_audio_pcm
from app.voice.tts import synthesize_speech

logger = structlog.get_logger(__name__)


def split_into_sentences(text: str) -> list[str]:
    """Split text on sentence boundaries for lower TTS time-to-first-audio latency."""
    raw = re.split(r"(?<=[.?!])\s+", text.strip())
    sentences = [s.strip() for s in raw if s.strip()]
    return sentences or [text.strip()]


class VoicePipeline:
    """Manages full duplex voice streaming over a live WebSocket connection."""

    def __init__(
        self,
        websocket: WebSocket,
        session: CallSession,
        session_factory: Any,
    ):
        self.ws = websocket
        self.session = session
        self.session_factory = session_factory
        self._is_active = True

    async def send_greeting(self, greeting_text: str | None = None) -> None:
        """Deliver initial opening receptionist greeting."""
        text = greeting_text or f"Hello, thank you for calling {self.session.business_name}. How can I assist you today?"
        self.session.conversation_history.append({"role": "assistant", "content": text})
        await self.speak_text(text)

    async def handle_audio_chunk(self, raw_chunk: bytes) -> None:
        """Process incoming 8kHz mu-law audio frame from telephony carrier."""
        vad_res = self.session.vad.process_chunk(raw_chunk)

        # ── Barge-In: User started speaking while AI was playing audio ────────
        if vad_res["speech_started"]:
            if self.session.is_speaking:
                logger.info("Barge-in interruption detected — silencing AI playback", call_id=str(self.session.call_id))
                self.session.interrupt_playback()
                if self.session.is_sandbox:
                    await self.ws.send_json({"event": "sandbox_clear"})
                elif self.session.stream_sid:
                    await self.ws.send_json({"event": "clear", "streamSid": self.session.stream_sid})

        # ── Speech Ended: Transcribe buffered PCM and process utterance ──────
        if vad_res["speech_ended"] and vad_res["buffered_pcm"]:
            transcript, stt_ms = await transcribe_audio_pcm(
                vad_res["buffered_pcm"],
                sample_rate=8000,
            )
            if transcript:
                self.session.stt_latencies.append(stt_ms)
                logger.info("User speech recognized", transcript=transcript, latency_ms=stt_ms)
                asyncio.create_task(self.process_utterance(transcript))

    async def process_utterance(self, utterance: str) -> None:
        """Feed recognized utterance into LLM with tool calling capabilities."""
        self.session.conversation_history.append({"role": "user", "content": utterance})

        # Load business context from DB for prompt
        system_prompt = await self._compile_prompt()

        llm_start = time.perf_counter()
        messages = [LLMMessage(role="system", content=system_prompt)]
        for turn in self.session.conversation_history:
            messages.append(LLMMessage(role=turn["role"], content=turn["content"]))

        llm_provider = get_llm_provider(
            provider_name=self.session.agent_config.llm_provider if hasattr(self.session, "agent_config") and self.session.agent_config else "groq",
            temperature=0.3,
        )

        response_text = ""
        try:
            llm_resp = await llm_provider.complete(messages=messages, tools=VOICE_AGENT_TOOLS)
            llm_latency_ms = int((time.perf_counter() - llm_start) * 1000)
            self.session.llm_latencies.append(llm_latency_ms)

            response_text = llm_resp.content or ""

            # ── Tool Calling Execution Loop ──────────────────────────────────
            if llm_resp.tool_calls:
                async with self.session_factory() as db:
                    executor = ToolExecutor(
                        session=db,
                        tenant_id=self.session.tenant_id,
                        business_id=self.session.business_id,
                        current_appointment_id=self.session.appointment_id,
                    )
                    for tc in llm_resp.tool_calls:
                        tool_name = tc["function"]["name"]
                        raw_args = tc["function"].get("arguments", "{}")
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args

                        tool_res = await executor.execute(tool_name, args)
                        if tool_res.action:
                            self.session.call_action = tool_res.action

                        # If tool provides conversational feedback, prioritize it
                        if not response_text or tool_res.message:
                            response_text = tool_res.message

        except Exception as e:
            logger.error("LLM reasoning error", error=str(e))
            response_text = "I apologize, I am experiencing a brief connection glitch. Could you repeat that?"

        if response_text:
            self.session.conversation_history.append({"role": "assistant", "content": response_text})
            await self.speak_text(response_text)

        # ── Handle End of Call or Transfer ───────────────────────────────────
        if self.session.call_action in ("hangup", "transfer"):
            await asyncio.sleep(2.0)
            self._is_active = False
            await self.ws.close()

    async def speak_text(self, text: str) -> None:
        """Synthesize sentences into audio frames and stream over WebSocket."""
        self.session.is_speaking = True
        sentences = split_into_sentences(text)

        async def _stream_sentences():
            try:
                for s in sentences:
                    if not self.session.is_speaking:
                        break  # Interrupted by barge-in

                    audio_bytes, tts_ms = await synthesize_speech(
                        text=s,
                        voice_id=self.session.voice_id,
                        provider=self.session.voice_provider,
                        speech_speed=self.session.speech_speed,
                    )
                    self.session.tts_latencies.append(tts_ms)

                    if not self.session.is_speaking:
                        break

                    b64_audio = base64.b64encode(audio_bytes).decode("ascii")

                    if self.session.is_sandbox:
                        await self.ws.send_json(
                            {
                                "event": "sandbox_audio",
                                "payload": b64_audio,
                                "text": s,
                            }
                        )
                    else:
                        # Twilio / VoBiz PSTN stream format
                        if self.session.stream_sid:
                            await self.ws.send_json(
                                {
                                    "event": "media",
                                    "streamSid": self.session.stream_sid,
                                    "media": {"payload": b64_audio},
                                }
                            )

                    # Spacing between sentence chunks
                    await asyncio.sleep(len(audio_bytes) / 8000.0 * 0.8)
            finally:
                self.session.is_speaking = False

        self.session.current_playback_task = asyncio.create_task(_stream_sentences())
        await self.session.current_playback_task

    async def _compile_prompt(self) -> str:
        """Compile live business hours and services into conversational instructions."""
        business = None
        working_hours = []
        services = []

        try:
            async with self.session_factory() as db:
                b_res = await db.execute(
                    select(Business).where(Business.id == self.session.business_id)
                )
                business = b_res.scalar_one_or_none()

                wh_res = await db.execute(
                    select(WorkingHours)
                    .where(WorkingHours.business_id == self.session.business_id)
                    .order_by(WorkingHours.day_of_week)
                )
                working_hours = list(wh_res.scalars().all())

                s_res = await db.execute(
                    select(Service).where(
                        Service.business_id == self.session.business_id,
                        Service.is_active == True,  # noqa: E712
                        Service.is_deleted == False,  # noqa: E712
                    )
                )
                services = list(s_res.scalars().all())
        except Exception as e:
            logger.warning("Could not load full business context from DB for prompt", error=str(e))

        agent = AgentConfig(
            tenant_id=self.session.tenant_id,
            business_id=self.session.business_id,
            name=self.session.agent_name,
            role_description="Voice receptionist and scheduling coordinator",
        )

        return compile_voice_system_prompt(
            agent=agent,
            business=business,
            working_hours=working_hours,
            services=services,
        )

    async def finalize_call(self) -> None:
        """Persist final Call record, compute latency metrics, and dispatch hooks."""
        if self.session.is_ended:
            return
        self.session.is_ended = True

        ended_at = datetime.now(timezone.utc)
        duration_sec = int((ended_at - self.session.started_at).total_seconds())

        avg_stt = (
            int(sum(self.session.stt_latencies) / len(self.session.stt_latencies))
            if self.session.stt_latencies
            else 0
        )
        avg_llm = (
            int(sum(self.session.llm_latencies) / len(self.session.llm_latencies))
            if self.session.llm_latencies
            else 0
        )
        avg_tts = (
            int(sum(self.session.tts_latencies) / len(self.session.tts_latencies))
            if self.session.tts_latencies
            else 0
        )

        # Estimate carrier + compute cost: ~$0.015 / minute
        cost_cents = max(1, int((duration_sec / 60.0) * 1.5))
        status = CallStatus.COMPLETED

        try:
            async with self.session_factory() as db:
                call_res = await db.execute(
                    select(Call).where(Call.id == self.session.call_id)
                )
                call = call_res.scalar_one_or_none()

                if call:
                    call.ended_at = ended_at
                    call.duration_seconds = duration_sec
                    call.status = status
                    call.transcript = self.session.conversation_history
                    call.stt_latency_ms = avg_stt
                    call.llm_latency_ms = avg_llm
                    call.tts_latency_ms = avg_tts
                    call.cost_cents = cost_cents
                    call.sentiment = self.session.sentiment
                    call.intent = self.session.intent or "General Inquiry"
                    call.notes = self.session.call_summary or "Voice call completed successfully."
                    call.updated_at = ended_at
                else:
                    call = Call(
                        id=self.session.call_id,
                        tenant_id=self.session.tenant_id,
                        business_id=self.session.business_id,
                        appointment_id=self.session.appointment_id,
                        caller_phone=self.session.customer_phone,
                        direction=self.session.direction,
                        status=status,
                        started_at=self.session.started_at,
                        ended_at=ended_at,
                        duration_seconds=duration_sec,
                        transcript=self.session.conversation_history,
                        stt_latency_ms=avg_stt,
                        llm_latency_ms=avg_llm,
                        tts_latency_ms=avg_tts,
                        cost_cents=cost_cents,
                        sentiment=self.session.sentiment,
                        intent=self.session.intent or "General Inquiry",
                        notes=self.session.call_summary or "Voice call completed successfully.",
                    )
                    db.add(call)

                await db.commit()
        except Exception as e:
            logger.warning("Could not persist final Call record to database", error=str(e))

        logger.info(
            "Call finalized and stored",
            call_id=str(self.session.call_id),
            duration=duration_sec,
            avg_stt=avg_stt,
            avg_llm=avg_llm,
            avg_tts=avg_tts,
        )
