"""
app/voice/pipeline.py — Real-Time Voice WebSocket Pipeline

Orchestrates the entire sub-second conversational loop:
  1. Ingestion: 8kHz G.711 mu-law or 16kHz PCM audio frames over WebSocket
  2. VAD: Speech boundary detection and sub-millisecond barge-in interruption
  3. STT: Whisper / Deepgram voice transcription
  4. Intelligence: Streaming multi-step ReAct LLM reasoning + tool execution loop
  5. TTS: Clause-chunked streaming synthesis overlapped with LLM generation
  6. Persistence: Transactional call telemetry and analytics logging
"""

import asyncio
import base64
import json
import re
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import WebSocket
from sqlalchemy import select

from app.ai.llm.base import BaseLLMProvider, LLMMessage, LLMResponse, LLMStreamChunk
from app.ai.llm.factory import get_llm_provider
from app.ai.tools.definitions import VOICE_AGENT_TOOLS
from app.ai.tools.executor import ToolExecutor
from app.models.agent import AgentConfig
from app.models.business import Business, WorkingHours
from app.models.call import Call, CallStatus
from app.models.service import Service
from app.services.prompt_compiler import compile_voice_system_prompt
from app.voice.session import CallSession
from app.voice.stt import transcribe_audio_pcm
from app.voice.tts import synthesize_speech

logger = structlog.get_logger(__name__)

MAX_TOOL_ITERATIONS = 4
CLAUSE_SPLIT_CHAR_LIMIT = 80
_ABBREVIATION_DOT_TOKEN = "<DOT>"
_ABBREVIATIONS = ("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "Sr.", "Jr.", "St.", "No.", "Rs.", "a.m.", "p.m.")


def _mask_non_splitting_dots(text: str) -> str:
    masked = text
    for abbr in _ABBREVIATIONS:
        masked = masked.replace(abbr, abbr.replace(".", _ABBREVIATION_DOT_TOKEN))
    # Protect decimal numbers such as 10.5 or 99.9
    masked = re.sub(r"(\d)\.(\d)", rf"\1{_ABBREVIATION_DOT_TOKEN}\2", masked)
    return masked


def _unmask_dots(text: str) -> str:
    return text.replace(_ABBREVIATION_DOT_TOKEN, ".")


def extract_speakable_clauses(buffer: str, flush: bool = False) -> tuple[list[str], str]:
    """
    Extract complete sentence/clause chunks ready for low-latency TTS synthesis.
    Returns: (ready_clauses, remaining_buffer)
    """
    if not buffer:
        return [], ""

    working = _mask_non_splitting_dots(buffer)
    clauses: list[str] = []

    # First emit complete sentences terminated by punctuation or newline + whitespace
    while True:
        match = re.search(r"(.+?[.?!।]+(?:\s+|$)|.+?\n+)", working, flags=re.DOTALL)
        if not match:
            break
        if not flush and match.end() == len(working) and not re.search(r"\s$", working):
            # Wait for trailing whitespace or end-of-stream so abbreviations/numbers don't split early
            break
        segment = _unmask_dots(match.group(1)).strip()
        if segment:
            clauses.append(segment)
        working = working[match.end():]

    # Split long clauses at comma/semicolon/colon boundaries so TTS starts early
    if len(working.strip()) >= CLAUSE_SPLIT_CHAR_LIMIT:
        comma_matches = list(re.finditer(r"[,;:]\s+", working))
        if comma_matches:
            split_idx = comma_matches[-1].end()
            head = _unmask_dots(working[:split_idx]).strip()
            if head:
                clauses.append(head)
            working = working[split_idx:]

    remaining = _unmask_dots(working)
    if flush:
        tail = remaining.strip()
        if tail:
            clauses.append(tail)
        remaining = ""

    return clauses, remaining


def split_into_sentences(text: str) -> list[str]:
    """Split text on sentence boundaries for lower TTS time-to-first-audio latency."""
    stripped = text.strip()
    if not stripped:
        return []
    clauses, _ = extract_speakable_clauses(stripped, flush=True)
    return clauses or [stripped]


def _parse_tool_arguments(raw_args: Any) -> dict[str, Any]:
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str) and raw_args.strip():
        try:
            parsed = json.loads(raw_args)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


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

    def _is_turn_current(self, turn_id: int) -> bool:
        return self._is_active and turn_id == self.session.active_turn_id

    async def _safe_send_json(self, payload: dict[str, Any]) -> None:
        try:
            await self.ws.send_json(payload)
        except Exception:
            # Socket closed mid-turn (e.g., caller hung up); fail silently so background cleanup completes.
            pass

    async def send_greeting(self, greeting_text: str | None = None) -> None:
        """Deliver initial opening receptionist greeting."""
        text = greeting_text or self.session.greeting_message or (
            f"Hello, thank you for calling {self.session.business_name}. How can I assist you today?"
        )
        self.session.conversation_history.append({"role": "assistant", "content": text})
        await self.speak_text(text)

    async def _clear_remote_audio_buffer(self) -> None:
        if self.session.is_sandbox:
            await self._safe_send_json({"event": "sandbox_clear"})
        elif self.session.stream_sid:
            await self._safe_send_json({"event": "clear", "streamSid": self.session.stream_sid})

    async def handle_audio_chunk(self, raw_chunk: bytes) -> None:
        """Process incoming 8kHz mu-law audio frame from telephony carrier."""
        vad_res = self.session.vad.process_chunk(raw_chunk)

        # ── Barge-In: User started speaking while AI was playing audio ────────
        if vad_res["speech_started"] and self.session.barge_in_enabled:
            if self.session.is_speaking or (self.session.current_turn_task and not self.session.current_turn_task.done()):
                logger.info(
                    "Barge-in interruption detected — silencing AI playback",
                    call_id=str(self.session.call_id),
                )
                self.session.cancel_active_turn()
                await self._clear_remote_audio_buffer()

        # ── Speech Ended: Transcribe buffered PCM and schedule utterance turn ──
        if vad_res["speech_ended"] and vad_res["buffered_pcm"]:
            transcript, stt_ms = await transcribe_audio_pcm(
                vad_res["buffered_pcm"],
                sample_rate=8000,
                language=self.session.primary_language,
            )
            if transcript:
                self.session.stt_latencies.append(stt_ms)
                logger.info("User speech recognized", transcript=transcript, latency_ms=stt_ms)
                self.schedule_utterance(transcript)

    def schedule_utterance(self, utterance: str) -> asyncio.Task:
        """Cancel any stale in-flight turn and schedule a fresh turn safely."""
        self.session.cancel_active_turn()
        task = asyncio.create_task(self.process_utterance(utterance))
        self.session.current_turn_task = task
        return task

    async def _consume_tts_queue(self, tts_queue: asyncio.Queue[str | None], turn_id: int | None = None) -> None:
        """Continuously synthesize queued text clauses and stream audio frames over WebSocket."""
        try:
            while True:
                if not self.session.is_speaking:
                    break
                if turn_id is not None and turn_id != self.session.active_turn_id:
                    break

                clause = await tts_queue.get()
                if clause is None:
                    break

                cleaned = clause.strip()
                if not cleaned or not self.session.is_speaking:
                    continue

                audio_bytes, tts_ms = await synthesize_speech(
                    text=cleaned,
                    voice_id=self.session.voice_id,
                    provider=self.session.voice_provider,
                    speech_speed=self.session.speech_speed,
                )
                self.session.tts_latencies.append(tts_ms)

                if not self.session.is_speaking:
                    break
                if turn_id is not None and turn_id != self.session.active_turn_id:
                    break

                b64_audio = base64.b64encode(audio_bytes).decode("ascii")
                if self.session.is_sandbox:
                    await self._safe_send_json(
                        {
                            "event": "sandbox_audio",
                            "payload": b64_audio,
                            "text": cleaned,
                        }
                    )
                elif self.session.stream_sid:
                    await self._safe_send_json(
                        {
                            "event": "media",
                            "streamSid": self.session.stream_sid,
                            "media": {"payload": b64_audio},
                        }
                    )

                if audio_bytes and not self.session.is_sandbox:
                    await asyncio.sleep(len(audio_bytes) / 8000.0 * 0.8)
        except asyncio.CancelledError:
            raise
        finally:
            self.session.is_speaking = False

    async def speak_text(self, text: str) -> None:
        """Synthesize sentences into audio frames and stream over WebSocket."""
        sentences = split_into_sentences(text)
        if not sentences:
            return

        tts_queue: asyncio.Queue[str | None] = asyncio.Queue()
        for sentence in sentences:
            tts_queue.put_nowait(sentence)
        tts_queue.put_nowait(None)

        self.session.is_speaking = True
        playback_task = asyncio.create_task(self._consume_tts_queue(tts_queue))
        self.session.current_playback_task = playback_task
        try:
            await playback_task
        except asyncio.CancelledError:
            self.session.is_speaking = False

    async def _iter_llm_step(
        self,
        llm_provider: BaseLLMProvider,
        messages: list[LLMMessage],
    ) -> AsyncIterator[LLMStreamChunk]:
        """Yield LLMStreamChunk objects regardless of whether provider is real or test mock."""
        if isinstance(llm_provider, BaseLLMProvider):
            async for chunk in llm_provider.stream_events(messages=messages, tools=VOICE_AGENT_TOOLS):
                yield chunk
            return

        # Support plain AsyncMock / MagicMock test doubles cleanly
        stream_attr = getattr(llm_provider, "stream_events", None)
        if callable(stream_attr):
            maybe_iter = stream_attr(messages=messages, tools=VOICE_AGENT_TOOLS)
            if hasattr(maybe_iter, "__aiter__"):
                async for chunk in maybe_iter:
                    yield chunk
                return

        resp: LLMResponse = await llm_provider.complete(messages=messages, tools=VOICE_AGENT_TOOLS)
        if resp.content:
            yield LLMStreamChunk(text_delta=resp.content, provider=resp.provider, model=resp.model)
        yield LLMStreamChunk(
            done=True,
            tool_calls=resp.tool_calls or [],
            provider=resp.provider,
            model=resp.model,
            latency_ms=resp.latency_ms,
        )

    async def process_utterance(self, utterance: str) -> None:
        """Feed recognized utterance into a turn-locked streaming ReAct loop with tool calling."""
        turn_id = self.session.begin_turn()

        async with self.session.turn_lock:
            if not self._is_turn_current(turn_id):
                return

            self.session.conversation_history.append({"role": "user", "content": utterance})
            system_prompt = await self._compile_prompt()

            working_messages: list[LLMMessage] = [LLMMessage(role="system", content=system_prompt)]
            for turn in self.session.conversation_history:
                working_messages.append(
                    LLMMessage(
                        role=turn["role"],
                        content=turn.get("content", ""),
                    )
                )

            llm_provider = get_llm_provider(
                provider_name=self.session.llm_provider,
                model=self.session.llm_model,
                temperature=self.session.temperature,
            )

            tts_queue: asyncio.Queue[str | None] = asyncio.Queue()
            playback_task: asyncio.Task | None = None
            spoken_segments: list[str] = []
            last_tool_message = ""

            def _ensure_playback_started() -> None:
                nonlocal playback_task
                if playback_task is None:
                    self.session.is_speaking = True
                    playback_task = asyncio.create_task(self._consume_tts_queue(tts_queue, turn_id=turn_id))
                    self.session.current_playback_task = playback_task

            def _enqueue_clauses(clauses: list[str]) -> None:
                if not clauses:
                    return
                _ensure_playback_started()
                for clause in clauses:
                    tts_queue.put_nowait(clause)

            try:
                for _iteration in range(MAX_TOOL_ITERATIONS):
                    if not self._is_turn_current(turn_id):
                        break

                    step_start = time.perf_counter()
                    token_buffer = ""
                    step_text_parts: list[str] = []
                    step_tool_calls: list[dict[str, Any]] = []
                    reported_latency: int | None = None

                    async for chunk in self._iter_llm_step(llm_provider, working_messages):
                        if not self._is_turn_current(turn_id):
                            break
                        if chunk.text_delta:
                            step_text_parts.append(chunk.text_delta)
                            token_buffer += chunk.text_delta
                            ready_clauses, token_buffer = extract_speakable_clauses(token_buffer, flush=False)
                            _enqueue_clauses(ready_clauses)
                        if chunk.done:
                            if chunk.tool_calls:
                                step_tool_calls = chunk.tool_calls
                            if chunk.latency_ms:
                                reported_latency = chunk.latency_ms

                    if not self._is_turn_current(turn_id):
                        break

                    step_latency = reported_latency if reported_latency is not None else int((time.perf_counter() - step_start) * 1000)
                    self.session.llm_latencies.append(step_latency)

                    step_full_text = "".join(step_text_parts).strip()
                    if step_full_text:
                        spoken_segments.append(step_full_text)

                    # Flush any remaining tokens buffered in this step
                    remaining_clauses, token_buffer = extract_speakable_clauses(token_buffer, flush=True)
                    _enqueue_clauses(remaining_clauses)

                    if not step_tool_calls:
                        break

                    # Feed assistant tool call + serialized tool results back for next ReAct reasoning turn
                    working_messages.append(
                        LLMMessage(
                            role="assistant",
                            content=step_full_text or None,
                            tool_calls=step_tool_calls,
                        )
                    )

                    self.session.in_db_io = True
                    try:
                        async with self.session_factory() as db:
                            executor = ToolExecutor(
                                session=db,
                                tenant_id=self.session.tenant_id,
                                business_id=self.session.business_id,
                                current_appointment_id=self.session.appointment_id,
                            )
                            for idx, tc in enumerate(step_tool_calls):
                                if not self._is_turn_current(turn_id):
                                    break
                                fn = tc.get("function", {})
                                tool_name = fn.get("name", "")
                                args = _parse_tool_arguments(fn.get("arguments", "{}"))
                                tool_call_id = tc.get("id") or f"call_{idx}"

                                tool_res = await executor.execute(tool_name, args)
                                if tool_res.action:
                                    self.session.call_action = tool_res.action
                                if tool_name == "end_call" and args.get("summary"):
                                    self.session.call_summary = str(args["summary"])
                                if tool_res.message:
                                    last_tool_message = tool_res.message

                                if self.session.is_sandbox:
                                    await self._safe_send_json(
                                        {
                                            "event": "tool_call",
                                            "tool": tool_name,
                                            "arguments": args,
                                            "success": tool_res.success,
                                            "message": tool_res.message,
                                            "data": tool_res.data,
                                            "action": tool_res.action,
                                        }
                                    )

                                working_messages.append(
                                    LLMMessage(
                                        role="tool",
                                        tool_call_id=tool_call_id,
                                        name=tool_name,
                                        content=json.dumps(tool_res.to_dict()),
                                    )
                                )
                    finally:
                        self.session.in_db_io = False

                if self._is_turn_current(turn_id) and not spoken_segments:
                    fallback_reply = last_tool_message or self.session.fallback_message
                    spoken_segments.append(fallback_reply)
                    _enqueue_clauses(split_into_sentences(fallback_reply))

            except asyncio.CancelledError:
                self.session.interrupt_playback()
                return
            except Exception as e:
                logger.error("LLM reasoning error", error=str(e))
                if not spoken_segments and self._is_turn_current(turn_id):
                    spoken_segments.append(self.session.fallback_message)
                    _enqueue_clauses(split_into_sentences(self.session.fallback_message))

            if playback_task is not None:
                tts_queue.put_nowait(None)
                try:
                    await playback_task
                except asyncio.CancelledError:
                    self.session.is_speaking = False

            final_assistant_text = " ".join(part.strip() for part in spoken_segments if part.strip())
            if final_assistant_text:
                self.session.conversation_history.append({"role": "assistant", "content": final_assistant_text})

            # ── Handle End of Call or Transfer ───────────────────────────────
            if self._is_turn_current(turn_id) and self.session.call_action in ("hangup", "transfer"):
                await asyncio.sleep(0.3)
                self._is_active = False
                try:
                    await self.ws.close()
                except Exception:
                    pass

    async def _compile_prompt(self) -> str:
        """Compile live business hours, services, and hydrated AgentConfig into instructions."""
        business = None
        working_hours = []
        services = []
        db_agent = None

        try:
            self.session.in_db_io = True
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

                a_res = await db.execute(
                    select(AgentConfig).where(AgentConfig.tenant_id == self.session.tenant_id)
                )
                db_agent = a_res.scalar_one_or_none()
        except Exception as e:
            logger.warning("Could not load full business context from DB for prompt", error=str(e))
        finally:
            self.session.in_db_io = False

        if isinstance(db_agent, AgentConfig):
            self.session.apply_agent_config(db_agent)
            agent = db_agent
        else:
            agent = AgentConfig(
                tenant_id=self.session.tenant_id,
                business_id=self.session.business_id,
                name=self.session.agent_name,
                role_description=self.session.role_description,
                system_prompt=self.session.custom_system_prompt,
                greeting_message=self.session.greeting_message,
                fallback_message=self.session.fallback_message,
                voice_provider=self.session.voice_provider,
                voice_id=self.session.voice_id,
                speech_speed=self.session.speech_speed,
                llm_provider=self.session.llm_provider,
                llm_model=self.session.llm_model,
                temperature=self.session.temperature,
                vad_sensitivity=self.session.vad_sensitivity,
                primary_language=self.session.primary_language,
                supported_languages=list(self.session.supported_languages),
                transfer_phone_number=self.session.transfer_phone,
                webhook_url=self.session.webhook_url,
                sms_enabled=self.session.sms_enabled,
            )

        return compile_voice_system_prompt(
            agent=agent,
            business=business,
            working_hours=working_hours,
            services=services,
        )

    async def finalize_call(self) -> None:
        """Persist final Call record, compute latency metrics, and clean up active tasks."""
        if self.session.is_ended:
            return
        self.session.is_ended = True
        self._is_active = False

        prev_turn = self.session.current_turn_task
        prev_playback = self.session.current_playback_task
        self.session.cancel_active_turn()
        current = asyncio.current_task()
        for task in (prev_turn, prev_playback):
            if task and not task.done() and task is not current:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

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
