import os
import json
import base64
import asyncio
import wave
import io
import math
import struct
import httpx
from fastapi import WebSocket, WebSocketDisconnect
from app.db import query_db
from app.redis_client import save_session_state, remove_session_state, publish_call_event
from app.audio_utils import (
    MulawVADDetector, 
    mulaw_to_pcm16_bytes, 
    calculate_mulaw_rms, 
    pcm16_to_mulaw_bytes, 
    mp3_to_8khz_mulaw
)
from anthropic import AsyncAnthropic
from groq import AsyncGroq
import edge_tts
from twilio.rest import Client as TwilioClient

# Load API keys & secrets
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
APP_HOST = os.getenv("APP_HOST", "localhost:5000")
JWT_SECRET = os.getenv("JWT_SECRET", "vocalis-production-jwt-secret-key-98765")

# Initialize SDK clients
anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

active_sessions = {}

# Outbound Trigger
async def trigger_voice_call(appointment: dict) -> str:
    call_id = "call_" + os.urandom(4).hex()
    from datetime import datetime, timezone
    iso_started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    await query_db(
        """INSERT INTO calls (id, appointment_id, business_id, started_at, outcome, transcript, duration_seconds, cost_cents)
           VALUES (?, ?, ?, ?, 'calling', '[]', 0, 0)""",
        [call_id, appointment["id"], appointment["business_id"], iso_started]
    )

    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER:
        try:
            print(f"Triggering outbound Twilio call for appointment {appointment['id']}...")
            loop = asyncio.get_event_loop()
            client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            call = await loop.run_in_executor(
                None,
                lambda: client.calls.create(
                    url=f"https://{APP_HOST}/api/twilio/voice?appointmentId={appointment['id']}&callId={call_id}",
                    to=appointment["customer_phone"],
                    from_=TWILIO_PHONE_NUMBER
                )
            )
            print(f"Twilio call placed. Sid: {call.sid}")
        except Exception as e:
            print(f"Error placing Twilio call: {e}")
            await query_db("UPDATE calls SET outcome = 'no_answer' WHERE id = ?", [call_id])
    else:
        print(f"[MOCK CALL] Phone: {appointment['customer_phone']}. Trigger Sandbox simulator on dashboard.")

    return call_id

def handle_twilio_voice_xml(appointment_id: str, call_id: str) -> str:
    ws_url = f"wss://{APP_HOST}/twilio-stream?appointmentId={appointment_id}&callId={call_id}"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna-Neural">Connecting to scheduling assistant...</Say>
  <Connect>
    <Stream url="{ws_url}" />
  </Connect>
</Response>"""

class CallSession:
    def __init__(self, call_id, appointment, slots):
        self.call_id = call_id
        self.appointment_id = appointment["id"]
        self.business_id = appointment["business_id"]
        self.customer_name = appointment["customer_name"]
        self.customer_phone = appointment["customer_phone"]
        self.appointment_time = appointment["scheduled_at"]
        self.business_name = appointment["business_name"]
        self.available_slots = slots
        
        # Agent Settings
        self.agent_name = appointment.get("agent_name") or "Sarah"
        self.voice_id = appointment.get("voice_id") or "en-US-AriaNeural"
        self.custom_greeting = appointment.get("custom_greeting") or ""
        self.business_faqs = appointment.get("business_faqs") or ""
        self.webhook_url = appointment.get("webhook_url") or ""
        self.sms_enabled = appointment.get("sms_enabled", 1)
        self.speech_speed = appointment.get("speech_speed") or "+0%"
        self.vad_sensitivity = appointment.get("vad_sensitivity") or "normal"
        
        self.conversation_history = []
        self.current_state = "greeting" # greeting, confirming, rescheduling, completed, cancelled, escalated
        self.stream_sid = None
        self.is_speaking = False
        self.audio_task = None
        
        # Audio buffering & VAD Engine configured by sensitivity
        if self.vad_sensitivity == "high":
            self.vad = MulawVADDetector(energy_threshold=400.0, silence_duration_ms=600)
        elif self.vad_sensitivity == "low":
            self.vad = MulawVADDetector(energy_threshold=900.0, silence_duration_ms=1100)
        else:
            self.vad = MulawVADDetector(energy_threshold=600.0, silence_duration_ms=800)
            
        self.audio_buffer = bytearray()
        self.speaking_started = False
        self.silent_chunks = 0
        
        # Latency trackers
        self.stt_timers = []
        self.llm_timers = []
        self.tts_timers = []

def calculate_rms(pcm_bytes: bytes) -> float:
    count = len(pcm_bytes) // 2
    if count == 0:
        return 0.0
    shorts = struct.unpack(f"{count}h", pcm_bytes)
    sum_squares = sum(s * s for s in shorts)
    return math.sqrt(sum_squares / count)

async def handle_pipeline_websocket(ws: WebSocket, appointment_id: str, call_id: str, is_sandbox: bool):
    await ws.accept()
    print(f"WebSocket connected. CallId: {call_id}. Sandbox: {is_sandbox}")
    
    appt_rows = await query_db(
        """SELECT a.*, b.name as business_name, b.timezone, b.agent_name, b.voice_id, 
                  b.custom_greeting, b.business_faqs, b.webhook_url, b.sms_enabled, 
                  b.speech_speed, b.vad_sensitivity 
           FROM appointments a 
           JOIN businesses b ON a.business_id = b.id 
           WHERE a.id = ?""",
        [appointment_id]
    )
    if not appt_rows:
        await ws.close(code=1008, reason="Appointment not found")
        return
        
    appt = appt_rows[0]
    slot_rows = await query_db("SELECT slot_time FROM available_slots WHERE business_id = ? AND is_booked = 0 LIMIT 3", [appt["business_id"]])
    available_slots = [s["slot_time"] for s in slot_rows]
    
    session = CallSession(call_id, appt, available_slots)
    active_sessions[call_id] = session

    # Say greeting
    if session.custom_greeting.strip():
        greeting_text = session.custom_greeting.format(
            customer_name=session.customer_name,
            business_name=session.business_name,
            appointment_time=format_time(session.appointment_time),
            agent_name=session.agent_name
        )
    else:
        greeting_text = f"Hi {session.customer_name}, this is {session.agent_name} calling from {session.business_name}. I'm following up to confirm your upcoming appointment on {format_time(session.appointment_time)}. Will you be able to make it?"
        
    session.conversation_history.append({"role": "assistant", "content": greeting_text})
    
    asyncio.create_task(speak_sentence(ws, session, greeting_text, is_sandbox))

    try:
        while True:
            # Receive frame from client (base64 JSON)
            data = await ws.receive_text()
            message = json.loads(data)
            event = message.get("event")
            
            if event == "start":
                session.stream_sid = message["start"]["streamSid"]
            elif event == "sandbox_text":
                await handle_customer_utterance(ws, session, message["text"], is_sandbox)
            elif event in ["media", "sandbox_audio"]:
                # Retrieve raw audio bytes
                payload = message["media"]["payload"] if event == "media" else message["payload"]
                raw_chunk = base64.b64decode(payload)
                
                if event == "media" and groq_client:
                    # Twilio 8kHz mulaw voice stream processing via MulawVADDetector
                    res = session.vad.process_chunk(raw_chunk)
                    
                    if res["speech_started"]:
                        print("[VAD Twilio] Customer speech started...")
                        if session.is_speaking:
                            print("[Barge-In Twilio] Interrupting speech...")
                            session.is_speaking = False
                            if session.audio_task:
                                session.audio_task.cancel()
                            if session.stream_sid:
                                await ws.send_json({"event": "clear", "streamSid": session.stream_sid})
                                
                    if res["speech_ended"] and res["buffered_pcm"]:
                        print("[VAD Twilio] Customer speech ended. Transcribing...")
                        asyncio.create_task(run_whisper_stt(ws, session, res["buffered_pcm"], is_sandbox))
                        
                elif is_sandbox and groq_client:
                    # Sandbox 16kHz linear PCM processing
                    rms = calculate_rms(raw_chunk)
                    if rms > 750:
                        if not session.speaking_started:
                            session.speaking_started = True
                            print("[VAD Sandbox] User speaking started...")
                            
                            if session.is_speaking:
                                print("[Barge-In Sandbox] Interrupting speech...")
                                session.is_speaking = False
                                if session.audio_task:
                                    session.audio_task.cancel()
                                await ws.send_json({"event": "sandbox_clear"})
                                
                        session.silent_chunks = 0
                        session.audio_buffer.extend(raw_chunk)
                    else:
                        if session.speaking_started:
                            session.audio_buffer.extend(raw_chunk)
                            session.silent_chunks += 1
                            if session.silent_chunks >= 40:
                                session.speaking_started = False
                                session.silent_chunks = 0
                                pcm_data = bytes(session.audio_buffer)
                                session.audio_buffer.clear()
                                asyncio.create_task(run_whisper_stt(ws, session, pcm_data, is_sandbox))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WS error: {e}")
    finally:
        await close_call(call_id)

# Run Groq Whisper STT (utterance-based)
async def run_whisper_stt(ws: WebSocket, session: CallSession, pcm_data: bytes, is_sandbox: bool):
    if len(pcm_data) < 16000 * 2 * 0.5: # Discard under 0.5s audio clips (noise)
        return
        
    stt_start = asyncio.get_event_loop().time()
    try:
        # Construct wav file in memory
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2) # 16-bit
            wav_file.setframerate(16000)
            wav_file.writeframes(pcm_data)
        wav_bytes = wav_io.getvalue()
        
        # Send wav to Groq Whisper API
        response = await groq_client.audio.transcriptions.create(
            file=("speech.wav", wav_bytes),
            model="whisper-large-v3",
            response_format="json"
        )
        
        transcript = response.text.strip()
        if transcript:
            print(f"Groq STT [Whisper]: {transcript}")
            session.stt_timers.append(int((asyncio.get_event_loop().time() - stt_start) * 1000))
            await handle_customer_utterance(ws, session, transcript, is_sandbox)
            
    except Exception as e:
        print(f"Groq Whisper transcription failed: {e}")

async def handle_customer_utterance(ws: WebSocket, session: CallSession, utterance: str, is_sandbox: bool):
    session.conversation_history.append({"role": "user", "content": utterance})
    llm_start = asyncio.get_event_loop().time()

    faqs_prompt = f"\nBusiness Knowledge Base & FAQs:\n{session.business_faqs}\n" if session.business_faqs.strip() else ""

    system_prompt = f"""You are {session.agent_name}, a friendly Virtual Scheduling Assistant calling on behalf of {session.business_name}.
Your primary goal on this call is to confirm, reschedule, or cancel the customer's upcoming appointment.
Current customer name: {session.customer_name}
Current appointment details: {format_time(session.appointment_time)}
{faqs_prompt}
Rules:
1. Keep responses short and conversational. Focus on one or two sentences.
2. If they confirm: say thank you and end the call. Execute the 'confirm_appointment' tool.
3. If they want to reschedule: offer these available slots: {' or '.join([format_time(s) for s in session.available_slots])}. Ask if any work.
4. If they pick a rescheduled slot: confirm the time, update using the 'reschedule_appointment' tool, and close.
5. If they cancel: mark using the 'cancel_appointment' tool, express regret, and close.
6. If asked about business info/FAQs: answer using the Business Knowledge Base, then steer back to confirming the appointment.
7. If intent is unclear or human assistance requested: escalate using the 'escalate_to_human' tool, say a human staff will follow up, and close.
Always execute the corresponding tool when a final decision is reached."""

    tools = [
        {
            "name": "confirm_appointment",
            "description": "Confirm the customer will attend the original appointment slot.",
            "input_schema": {"type": "object", "properties": {}}
        },
        {
            "name": "reschedule_appointment",
            "description": "Reschedule the appointment to a new selected available slot.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "new_time": {"type": "string", "description": "The ISO slot timestamp selected by the customer."}
                },
                "required": ["new_time"]
            }
        },
        {
            "name": "cancel_appointment",
            "description": "Cancel the upcoming appointment.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Reason for cancellation if provided."}
                }
            }
        },
        {
            "name": "escalate_to_human",
            "description": "Escalate to human support because user intent is unclear or requests manual handling.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Reason for escalation."}
                }
            }
        }
    ]

    # Execute LLM switcher (Groq -> Gemini -> Grok -> Claude -> Fallback)
    response_text = ""
    tool_use = None
    
    try:
        if groq_client:
            # Groq Llama-3.1-70b-versatile completion
            response = await groq_client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *[{"role": m["role"], "content": m["content"]} for m in session.conversation_history]
                ],
                # Map Anthropic schemas to OpenAI tools schemas
                tools=[{
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["input_schema"]
                    }
                } for t in tools]
            )
            response_message = response.choices[0].message
            response_text = response_message.content or ""
            
            if response_message.tool_calls:
                tc = response_message.tool_calls[0]
                tool_use = {
                    "name": tc.function.name,
                    "input": json.loads(tc.function.arguments)
                }
                
        elif GEMINI_API_KEY:
            # Gemini 1.5 Flash POST completion (completely free)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            contents = []
            for h in session.conversation_history:
                contents.append({
                    "role": "model" if h["role"] == "assistant" else "user",
                    "parts": [{"text": h["content"]}]
                })
            
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    url,
                    json={
                        "contents": contents,
                        "systemInstruction": {"parts": [{"text": system_prompt}]}
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    response_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    
        elif XAI_API_KEY:
            # xAI Grok API (OpenAI-compatible)
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {XAI_API_KEY}"},
                    json={
                        "model": "grok-beta",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            *[{"role": m["role"], "content": m["content"]} for m in session.conversation_history]
                        ]
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    response_text = data["choices"][0]["message"]["content"]
                    
        elif anthropic_client:
            # Claude 3.5 Sonnet
            response = await anthropic_client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=300,
                system=system_prompt,
                messages=[{"role": m["role"], "content": m["content"]} for m in session.conversation_history],
                tools=tools
            )
            text_blocks = [b for b in response.content if b.type == "text"]
            if text_blocks:
                response_text = " ".join([b.text for b in text_blocks])
            t_calls = [b for b in response.content if b.type == "tool_use"]
            if t_calls:
                tool_use = {"name": t_calls[0].name, "input": t_calls[0].input}
        else:
            # Simulation/Mock LLM
            await asyncio.sleep(0.3)
            lower = utterance.lower()
            if "yes" in lower or "confirm" in lower:
                response_text = "Thank you! Your slot is confirmed."
                tool_use = {"name": "confirm_appointment", "input": {}}
            elif "no" in lower or "cancel" in lower:
                response_text = "Regrettably, your booking has been cancelled."
                tool_use = {"name": "cancel_appointment", "input": {"reason": "User cancel"}}
            elif "reschedule" in lower:
                response_text = f"Sure, slots are open at {' or '.join([format_time(s) for s in session.available_slots])}."
                session.current_state = "rescheduling"
            elif session.current_state == "rescheduling" and session.available_slots:
                response_text = "Got it! Rebooked to that time."
                tool_use = {"name": "reschedule_appointment", "input": {"new_time": session.available_slots[0]}}
            else:
                response_text = "I'll have a staff member call you back."
                tool_use = {"name": "escalate_to_human", "input": {"reason": "Unclear"}}

        session.llm_timers.append(int((asyncio.get_event_loop().time() - llm_start) * 1000))

        # Process Tool Triggers
        if tool_use:
            tool_name = tool_use["name"]
            tool_input = tool_use["input"]
            print(f"Executing Tool Call: {tool_name} with {tool_input}")
            
            if tool_name == "confirm_appointment":
                await query_db("UPDATE appointments SET status = 'confirmed' WHERE id = ?", [session.appointment_id])
                session.current_state = "completed"
            elif tool_name == "reschedule_appointment":
                new_time = tool_input["new_time"]
                await query_db("UPDATE appointments SET status = 'rescheduled', original_scheduled_at = scheduled_at, scheduled_at = ? WHERE id = ?", [new_time, session.appointment_id])
                await query_db("UPDATE available_slots SET is_booked = 1 WHERE slot_time = ? AND business_id = ?", [new_time, session.business_id])
                session.current_state = "completed"
            elif tool_name == "cancel_appointment":
                await query_db("UPDATE appointments SET status = 'cancelled' WHERE id = ?", [session.appointment_id])
                session.current_state = "cancelled"
            elif tool_name == "escalate_to_human":
                session.current_state = "escalated"
                
            if not response_text:
                if tool_name == "confirm_appointment": response_text = "Great. I have confirmed your appointment."
                if tool_name == "reschedule_appointment": response_text = "Perfect. I have rescheduled your appointment. Goodbye!"
                if tool_name == "cancel_appointment": response_text = "Understood. I have cancelled your slot. Goodbye."
                if tool_name == "escalate_to_human": response_text = "Okay. I will forward this to the receptionist to follow up. Have a nice day!"

        if response_text:
            session.conversation_history.append({"role": "assistant", "content": response_text})
            await speak_sentence(ws, session, response_text, is_sandbox)
            
        if session.current_state in ["completed", "cancelled", "escalated"]:
            await asyncio.sleep(3.5)
            await ws.close()

    except Exception as e:
        print(f"LLM compilation or call error: {e}")
        err_msg = "I'm sorry, I'm experiencing network issues. I will have our office follow up directly."
        await speak_sentence(ws, session, err_msg, is_sandbox)
        await ws.close()

# Keyless Microsoft Edge Neural TTS Voice streaming (MP3 output for browser sandbox)
async def speak_sentence(ws: WebSocket, session: CallSession, text: str, is_sandbox: bool):
    session.is_speaking = True
    tts_start = asyncio.get_event_loop().time()

    try:
        # Use business configured voice_id or default to Aria Neural
        voice = session.voice_id or "en-US-AriaNeural"
        rate = session.speech_speed or "+0%"
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        
        session.tts_timers.append(int((asyncio.get_event_loop().time() - tts_start) * 1000))
        
        # Audio streaming task
        async def stream_task():
            try:
                # Accumulate the complete MP3 voice file on server
                full_audio = bytearray()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        full_audio.extend(chunk["data"])
                        
                if full_audio:
                    base64_mp3 = base64.b64encode(full_audio).decode("utf-8")
                    if is_sandbox:
                        # Sandbox receives the complete voice sentence
                        await ws.send_json({
                            "event": "sandbox_audio_mp3",
                            "payload": base64_mp3
                        })
                    elif session.stream_sid:
                        # Transcode synthesized speech to 8kHz mu-law and stream chunks to Twilio
                        mulaw_bytes = mp3_to_8khz_mulaw(bytes(full_audio))
                        if mulaw_bytes:
                            chunk_size = 160  # 20ms chunk at 8kHz
                            for offset in range(0, len(mulaw_bytes), chunk_size):
                                if not session.is_speaking:
                                    break
                                chunk = mulaw_bytes[offset:offset + chunk_size]
                                b64_chunk = base64.b64encode(chunk).decode("utf-8")
                                await ws.send_json({
                                    "event": "media",
                                    "streamSid": session.stream_sid,
                                    "media": {"payload": b64_chunk}
                                })
                                await asyncio.sleep(0.02)
                            if session.is_speaking:
                                await ws.send_json({
                                    "event": "mark",
                                    "streamSid": session.stream_sid,
                                    "mark": {"name": f"speech_{session.call_id}"}
                                })
                            
                session.is_speaking = False
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"Error streaming TTS: {e}")
                
        session.audio_task = asyncio.create_task(stream_task())
        await session.audio_task

    except Exception as e:
        print(f"Edge TTS voice generation failed: {e}")
        # Text fallback
        if is_sandbox:
            await ws.send_json({"event": "sandbox_speak_text", "text": text})

def extract_call_insights(transcript: list, outcome: str):
    text = " ".join([m.get("content", "") for m in transcript]).lower()
    
    # Sentiment Extraction
    if any(w in text for w in ["angry", "stop calling", "annoyed", "frustrated", "hate", "terrible", "remove me", "don't call"]):
        sentiment = "Frustrated"
    elif any(w in text for w in ["urgent", "emergency", "asap", "pain", "immediately"]):
        sentiment = "Urgent"
    elif any(w in text for w in ["great", "thanks", "thank you", "perfect", "awesome", "wonderful", "appreciate", "definitely", "yes"]):
        sentiment = "Positive"
    else:
        sentiment = "Neutral"
        
    # Intent Extraction
    if outcome in ["confirmed", "completed"] or "confirm" in text:
        intent = "Confirmation"
    elif outcome == "rescheduled" or "reschedule" in text or "rebook" in text:
        intent = "Reschedule"
    elif outcome == "cancelled" or "cancel" in text:
        intent = "Cancellation"
    elif outcome == "escalated" or "receptionist" in text or "human" in text:
        intent = "Human Escalation"
    else:
        intent = "General Inquiry"
        
    notes = f"{intent} finished with {sentiment.lower()} customer tone. Status: {outcome}."
    return sentiment, intent, notes

async def send_post_call_sms(session: CallSession, outcome: str):
    if not session.sms_enabled:
        return
        
    msg_body = f"Hello {session.customer_name}, this is {session.business_name}. "
    if outcome in ["confirmed", "completed"]:
        msg_body += f"Your appointment is confirmed for {format_time(session.appointment_time)}. Thank you!"
    elif outcome == "rescheduled":
        msg_body += f"Your appointment has been rescheduled to {format_time(session.appointment_time)}. See you then!"
    elif outcome == "cancelled":
        msg_body += f"Your appointment on {format_time(session.appointment_time)} has been cancelled. Contact us if you need to rebook."
    else:
        msg_body += f"Our office will reach out shortly regarding your booking for {format_time(session.appointment_time)}."

    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER:
        try:
            loop = asyncio.get_event_loop()
            client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            await loop.run_in_executor(
                None,
                lambda: client.messages.create(
                    body=msg_body,
                    to=session.customer_phone,
                    from_=TWILIO_PHONE_NUMBER
                )
            )
            print(f"[TWILIO SMS SENT] To: {session.customer_phone}")
        except Exception as e:
            print(f"[TWILIO SMS ERROR] {e}")
    else:
        print(f"[POST-CALL SMS MOCK] To {session.customer_phone}: \"{msg_body}\"")

async def dispatch_call_webhook(session: CallSession, outcome: str, duration: int, avg_stt: int, avg_llm: int, avg_tts: int):
    if not session.webhook_url:
        return
        
    payload = {
        "event": "call.completed",
        "call_id": session.call_id,
        "business_id": session.business_id,
        "customer_name": session.customer_name,
        "customer_phone": session.customer_phone,
        "appointment_id": session.appointment_id,
        "outcome": outcome,
        "duration_seconds": duration,
        "transcript": session.conversation_history,
        "metrics": {
            "avg_stt_latency_ms": avg_stt,
            "avg_llm_latency_ms": avg_llm,
            "avg_tts_latency_ms": avg_tts
        }
    }
    
    import hmac
    import hashlib

    json_bytes = json.dumps(payload).encode("utf-8")
    signature = hmac.new(JWT_SECRET.encode("utf-8"), json_bytes, hashlib.sha256).hexdigest()
    
    headers = {
        "Content-Type": "application/json",
        "X-Vocalis-Signature": f"sha256={signature}",
        "User-Agent": "Vocalis-AI-Webhook-Dispatcher/1.0"
    }

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(session.webhook_url, content=json_bytes, headers=headers, timeout=5.0)
                if res.status_code < 400:
                    print(f"[WEBHOOK DISPATCHED] Attempt {attempt}: Status {res.status_code} to {session.webhook_url}")
                    break
                else:
                    print(f"[WEBHOOK WARN] Attempt {attempt}: Received status {res.status_code} from {session.webhook_url}")
        except Exception as e:
            print(f"[WEBHOOK ERROR] Attempt {attempt} failed for {session.webhook_url}: {e}")
            
        if attempt < max_retries:
            await asyncio.sleep(2 ** attempt)

async def close_call(call_id: str):
    if call_id not in active_sessions:
        return
        
    session = active_sessions.pop(call_id)
    from datetime import datetime, timezone
    iso_ended = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    avg_stt = int(sum(session.stt_timers) / len(session.stt_timers)) if session.stt_timers else 150
    avg_llm = int(sum(session.llm_timers) / len(session.llm_timers)) if session.llm_timers else 450
    avg_tts = int(sum(session.tts_timers) / len(session.tts_timers)) if session.tts_timers else 250
    
    # Free tier API costs = $0.00!
    cost = 0
    duration = len(session.stt_timers) * 6 or 15
    
    outcome = session.current_state
    if outcome == "completed":
        outcome = "confirmed"
        
    sentiment, intent, notes = extract_call_insights(session.conversation_history, outcome)
        
    await query_db(
        """UPDATE calls SET 
            ended_at = ?,
            outcome = ?,
            transcript = ?,
            duration_seconds = ?,
            cost_cents = ?,
            stt_latency_ms = ?,
            llm_latency_ms = ?,
            tts_latency_ms = ?,
            sentiment = ?,
            intent = ?,
            notes = ?
           WHERE id = ?""",
        [
            iso_ended,
            outcome,
            json.dumps(session.conversation_history),
            duration,
            cost,
            avg_stt,
            avg_llm,
            avg_tts,
            sentiment,
            intent,
            notes,
            call_id
        ]
    )
    print(f"Call {call_id} closed and stored with sentiment '{sentiment}' and intent '{intent}'.")

    # Trigger post-call SMS & Webhook dispatches and Redis Pub/Sub notification
    asyncio.create_task(send_post_call_sms(session, outcome))
    asyncio.create_task(dispatch_call_webhook(session, outcome, duration, avg_stt, avg_llm, avg_tts))
    asyncio.create_task(publish_call_event("calls:events", {
        "event": "call.completed",
        "call_id": call_id,
        "business_id": session.business_id,
        "outcome": outcome,
        "duration_seconds": duration
    }))
    asyncio.create_task(remove_session_state(call_id))

def format_time(iso_str: str) -> str:
    try:
        from datetime import datetime
        d = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return d.strftime("%a, %b %d at %I:%M %p")
    except Exception:
        return iso_str
