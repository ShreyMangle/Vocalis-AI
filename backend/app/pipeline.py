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
from anthropic import AsyncAnthropic
from groq import AsyncGroq
import edge_tts
from twilio.rest import Client as TwilioClient

# Load API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
APP_HOST = os.getenv("APP_HOST", "localhost:5000")

# Initialize SDK clients
anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

active_sessions = {}

# Outbound Trigger
async def trigger_voice_call(appointment: dict) -> str:
    call_id = "call_" + os.urandom(4).hex()
    from datetime import datetime
    iso_started = datetime.utcnow().isoformat() + "Z"
    
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
        
        self.conversation_history = []
        self.current_state = "greeting" # greeting, confirming, rescheduling, completed, cancelled, escalated
        self.stream_sid = None
        self.is_speaking = False
        self.audio_task = None
        
        # Audio buffering for Voice Activity Detection (VAD) / Whisper STT
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
        """SELECT a.*, b.name as business_name, b.timezone 
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
    greeting_text = f"Hi {session.customer_name}, this is the scheduling assistant for {session.business_name}. I'm calling to confirm your upcoming appointment scheduled for {format_time(session.appointment_time)}. Will you be able to make it?"
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
                
                # VAD & Buffer process (only in sandbox linear16 mic streaming or if Groq Whisper is active)
                # Twilio mulaw requires conversion to PCM for VAD calculation.
                # In sandbox mode, audio is 16kHz linear16 (2 bytes per sample) which is natively supported by Whisper.
                if is_sandbox and groq_client:
                    rms = calculate_rms(raw_chunk)
                    
                    # VAD energy threshold: 750 (adjust based on noise)
                    if rms > 750:
                        if not session.speaking_started:
                            session.speaking_started = True
                            print("[VAD] User speaking started...")
                            
                            # Barge-In interruption: Stop AI playback if it is speaking
                            if session.is_speaking:
                                print("[Barge-In] Interrupting speech...")
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
                            
                            # 40 chunks * 20ms = 800ms of consecutive silence
                            if session.silent_chunks >= 40:
                                session.speaking_started = False
                                session.silent_chunks = 0
                                pcm_data = bytes(session.audio_buffer)
                                session.audio_buffer.clear()
                                
                                # Trigger background Whisper STT
                                asyncio.create_task(run_whisper_stt(ws, session, pcm_data, is_sandbox))
                else:
                    # In Twilio or when no Groq client is configured, we fall back to sandbox text input or standard streams
                    pass

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

    system_prompt = f"""You are a friendly scheduling assistant calling on behalf of {session.business_name}.
Your ONLY goal on this call is to confirm, reschedule, or cancel the customer's upcoming appointment.
Current customer name: {session.customer_name}
Current appointment details: {format_time(session.appointment_time)}

Rules:
1. Keep responses short and conversational. Focus on one or two sentences.
2. If they confirm: say thank you and end the call. Execute the 'confirm_appointment' tool.
3. If they want to reschedule: offer these available slots: {' or '.join([format_time(s) for s in session.available_slots])}. Ask if any work.
4. If they pick a rescheduled slot: confirm the time, update using the 'reschedule_appointment' tool, and close.
5. If they cancel: mark using the 'cancel_appointment' tool, express regret, and close.
6. If intent is unclear: escalate using the 'escalate_to_human' tool, say a human staff will follow up, and close.
Always execute the corresponding tool when a decision is reached."""

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

    # If sandbox is active, stream edge-tts (MP3 base64). 
    # Edge-tts requires zero keys and sounds premium!
    try:
        # Microsoft Edge voice Aria Neural
        voice = "en-US-AriaNeural"
        communicate = edge_tts.Communicate(text, voice)
        
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
                        pass
                            
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

async def close_call(call_id: str):
    if call_id not in active_sessions:
        return
        
    session = active_sessions.pop(call_id)
    from datetime import datetime
    iso_ended = datetime.utcnow().isoformat() + "Z"
    
    avg_stt = int(sum(session.stt_timers) / len(session.stt_timers)) if session.stt_timers else 150
    avg_llm = int(sum(session.llm_timers) / len(session.llm_timers)) if session.llm_timers else 450
    avg_tts = int(sum(session.tts_timers) / len(session.tts_timers)) if session.tts_timers else 250
    
    # Free tier API costs = $0.00!
    cost = 0
    duration = len(session.stt_timers) * 6 or 15
    
    outcome = session.current_state
    if outcome == "completed":
        outcome = "confirmed"
        
    await query_db(
        """UPDATE calls SET 
            ended_at = ?,
            outcome = ?,
            transcript = ?,
            duration_seconds = ?,
            cost_cents = ?,
            stt_latency_ms = ?,
            llm_latency_ms = ?,
            tts_latency_ms = ?
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
            call_id
        ]
    )
    print(f"Call {call_id} closed and stored.")

def format_time(iso_str: str) -> str:
    try:
        from datetime import datetime
        d = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return d.strftime("%a, %b %d at %I:%M %p")
    except Exception:
        return iso_str
