import os
from fastapi import FastAPI, Depends, HTTPException, WebSocket, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta

from app.db import init_db, query_db
from app.auth import hash_password, verify_password, create_access_token, get_current_business_id
from app.pipeline import trigger_voice_call, handle_twilio_voice_xml, handle_pipeline_websocket

app = FastAPI(title="Vocalis AI Voice Agent Platform Backend")

# Enable CORS for frontend local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    await init_db()
    print("=" * 60)
    print("VOCALIS AI VOICE PLATFORM STARTED")
    print("=" * 60)
    print("SQLite Fallback DB initialized successfully.")
    
    # Check loaded keys
    groq_ok = "LOADED (Free LLM & STT)" if os.getenv("GROQ_API_KEY") else "MISSING (Using simulated mock logic)"
    gemini_ok = "LOADED (Alternative LLM)" if os.getenv("GEMINI_API_KEY") else "MISSING"
    grok_ok = "LOADED (Alternative LLM)" if os.getenv("XAI_API_KEY") else "MISSING"
    anthropic_ok = "LOADED (Claude LLM)" if os.getenv("ANTHROPIC_API_KEY") else "MISSING"
    edge_tts_ok = "ACTIVE (Free Keyless Speech)"
    
    print(f"Groq API Key (Llama/Whisper):  {groq_ok}")
    print(f"Gemini API Key:               {gemini_ok}")
    print(f"xAI Grok API Key:             {grok_ok}")
    print(f"Anthropic API Key:            {anthropic_ok}")
    print(f"Edge Speech TTS Engine:       {edge_tts_ok}")
    print("=" * 60)

# Pydantic Schemas
class RegisterSchema(BaseModel):
    name: str
    email: str
    password: str
    industry: Optional[str] = "General"
    phone_number: Optional[str] = ""

class LoginSchema(BaseModel):
    email: str
    password: str

class AppointmentCreateSchema(BaseModel):
    customer_name: str
    customer_phone: str
    scheduled_at: str

class CsvTextSchema(BaseModel):
    csvText: str

class SlotCreateSchema(BaseModel):
    slot_time: str

class PlanUpgradeSchema(BaseModel):
    plan: str

class SettingsUpdateSchema(BaseModel):
    agent_name: Optional[str] = "Sarah"
    voice_id: Optional[str] = "en-US-AriaNeural"
    custom_greeting: Optional[str] = ""
    business_faqs: Optional[str] = ""
    webhook_url: Optional[str] = ""
    sms_enabled: Optional[int] = 1

# ==========================================
# WEB WEBHOOK & WEBSOCKET ROUTES
# ==========================================

from fastapi.responses import HTMLResponse, Response

@app.post("/api/twilio/voice")
async def twilio_voice_post(appointmentId: Optional[str] = None, callId: Optional[str] = None):
    if not appointmentId or not callId:
        raise HTTPException(status_code=400, detail="Missing appointmentId or callId")
    twiml = handle_twilio_voice_xml(appointmentId, callId)
    return Response(content=twiml, media_type="text/xml")

@app.get("/api/twilio/voice")
async def twilio_voice_get(appointmentId: str, callId: str):
    twiml = handle_twilio_voice_xml(appointmentId, callId)
    return Response(content=twiml, media_type="text/xml")

@app.websocket("/twilio-stream")
async def twilio_websocket_stream(websocket: WebSocket, appointmentId: str, callId: str, sandbox: Optional[str] = "false"):
    is_sandbox = sandbox == "true"
    await handle_pipeline_websocket(websocket, appointmentId, callId, is_sandbox)

# ==========================================
# REST API ROUTES
# ==========================================

api_router = APIRouter(prefix="/api")

# --- AUTH ---
@api_router.post("/auth/register")
async def register(payload: RegisterSchema):
    existing = await query_db("SELECT id FROM businesses WHERE email = ?", [payload.email])
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    business_id = "bus_" + os.urandom(4).hex()
    password_hash = hash_password(payload.password)
    
    await query_db(
        """INSERT INTO businesses (id, name, industry, timezone, phone_number, email, password_hash, plan)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'free')""",
        [business_id, payload.name, payload.industry, "UTC", payload.phone_number, payload.email, password_hash]
    )
    
    # Create 3 default reschedule slots for demo
    tomorrow = datetime.utcnow() + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")
    default_slots = [
        f"{tomorrow_str}T09:00:00Z",
        f"{tomorrow_str}T11:00:00Z",
        f"{tomorrow_str}T14:30:00Z"
    ]
    for slot in default_slots:
        slot_id = "slot_" + os.urandom(4).hex()
        await query_db("INSERT INTO available_slots (id, business_id, slot_time, is_booked) VALUES (?, ?, ?, 0)", [slot_id, business_id, slot])
        
    token = create_access_token(business_id)
    return {"token": token, "business": {"id": business_id, "name": payload.name, "email": payload.email, "plan": "free"}}

@api_router.post("/auth/login")
async def login(payload: LoginSchema):
    rows = await query_db("SELECT * FROM businesses WHERE email = ?", [payload.email])
    if not rows:
        raise HTTPException(status_code=400, detail="Invalid email or password")
        
    business = rows[0]
    if not verify_password(payload.password, business["password_hash"]):
        raise HTTPException(status_code=400, detail="Invalid email or password")
        
    token = create_access_token(business["id"])
    return {
        "token": token,
        "business": {
            "id": business["id"],
            "name": business["name"],
            "email": business["email"],
            "plan": business["plan"],
            "industry": business["industry"],
            "timezone": business["timezone"],
            "phone_number": business["phone_number"]
        }
    }

@api_router.get("/auth/me")
async def get_me(business_id: str = Depends(get_current_business_id)):
    rows = await query_db("SELECT id, name, industry, timezone, phone_number, email, plan, stripe_customer_id FROM businesses WHERE id = ?", [business_id])
    if not rows:
        raise HTTPException(status_code=404, detail="Business not found")
    return rows[0]

# --- APPOINTMENTS ---
@api_router.get("/appointments")
async def get_appointments(business_id: str = Depends(get_current_business_id)):
    rows = await query_db("SELECT * FROM appointments WHERE business_id = ? ORDER BY scheduled_at ASC", [business_id])
    return rows

@api_router.post("/appointments")
async def create_appointment(payload: AppointmentCreateSchema, business_id: str = Depends(get_current_business_id)):
    appt_id = "appt_" + os.urandom(4).hex()
    await query_db(
        """INSERT INTO appointments (id, business_id, customer_name, customer_phone, scheduled_at, status)
           VALUES (?, ?, ?, ?, ?, 'pending')""",
        [appt_id, business_id, payload.customer_name, payload.customer_phone, payload.scheduled_at]
    )
    return {"id": appt_id, "customer_name": payload.customer_name, "customer_phone": payload.customer_phone, "scheduled_at": payload.scheduled_at, "status": "pending"}

@api_router.post("/appointments/upload")
async def upload_appointments(payload: CsvTextSchema, business_id: str = Depends(get_current_business_id)):
    lines = payload.csvText.split("\n")
    imported = []
    
    start_idx = 0
    if lines and ("name" in lines[0].lower() or "phone" in lines[0].lower()):
        start_idx = 1
        
    for line in lines[start_idx:]:
        line = line.strip()
        if not line:
            continue
        parts = [p.strip().replace('"', '') for p in line.split(",")]
        if len(parts) >= 3:
            appt_id = "appt_" + os.urandom(4).hex()
            await query_db(
                """INSERT INTO appointments (id, business_id, customer_name, customer_phone, scheduled_at, status)
                   VALUES (?, ?, ?, ?, ?, 'pending')""",
                [appt_id, business_id, parts[0], parts[1], parts[2]]
            )
            imported.append({"id": appt_id, "customer_name": parts[0], "customer_phone": parts[1], "scheduled_at": parts[2], "status": "pending"})
            
    return {"success": True, "count": len(imported), "data": imported}

@api_router.delete("/appointments/{appt_id}")
async def delete_appointment(appt_id: str, business_id: str = Depends(get_current_business_id)):
    await query_db("DELETE FROM appointments WHERE id = ? AND business_id = ?", [appt_id, business_id])
    return {"success": True}

@api_router.post("/appointments/{appt_id}/trigger")
async def trigger_call(appt_id: str, business_id: str = Depends(get_current_business_id)):
    rows = await query_db("SELECT * FROM appointments WHERE id = ? AND business_id = ?", [appt_id, business_id])
    if not rows:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appt = rows[0]
    call_id = await trigger_voice_call(appt)
    return {"success": True, "callId": call_id}

# --- AVAILABLE SLOTS ---
@api_router.get("/slots")
async def get_slots(business_id: str = Depends(get_current_business_id)):
    rows = await query_db("SELECT * FROM available_slots WHERE business_id = ? AND is_booked = 0 ORDER BY slot_time ASC", [business_id])
    return rows

@api_router.post("/slots")
async def create_slot(payload: SlotCreateSchema, business_id: str = Depends(get_current_business_id)):
    slot_id = "slot_" + os.urandom(4).hex()
    await query_db("INSERT INTO available_slots (id, business_id, slot_time, is_booked) VALUES (?, ?, ?, 0)", [slot_id, business_id, payload.slot_time])
    return {"id": slot_id, "slot_time": payload.slot_time, "is_booked": 0}

@api_router.delete("/slots/{slot_id}")
async def delete_slot(slot_id: str, business_id: str = Depends(get_current_business_id)):
    await query_db("DELETE FROM available_slots WHERE id = ? AND business_id = ?", [slot_id, business_id])
    return {"success": True}

# --- CALLS & HISTORY ---
@api_router.get("/calls")
async def get_calls(business_id: str = Depends(get_current_business_id)):
    rows = await query_db(
        """SELECT c.*, a.customer_name, a.customer_phone, a.scheduled_at 
           FROM calls c
           JOIN appointments a ON c.appointment_id = a.id
           WHERE c.business_id = ?
           ORDER BY c.created_at DESC""",
        [business_id]
    )
    return rows

@api_router.get("/stats")
async def get_stats(business_id: str = Depends(get_current_business_id)):
    # Counts
    appts = await query_db("SELECT status, count(*) as count FROM appointments WHERE business_id = ? GROUP BY status", [business_id])
    counts = {"pending": 0, "confirmed": 0, "rescheduled": 0, "cancelled": 0, "no_show": 0}
    for row in appts:
        counts[row["status"]] = int(row["count"])
        
    # Latency aggregates
    call_stats = await query_db(
        """SELECT 
            AVG(stt_latency_ms) as avg_stt,
            AVG(llm_latency_ms) as avg_llm,
            AVG(tts_latency_ms) as avg_tts,
            SUM(cost_cents) as total_cost,
            AVG(duration_seconds) as avg_duration,
            COUNT(*) as total_calls
           FROM calls WHERE business_id = ?""",
        [business_id]
    )
    stats = call_stats[0] if call_stats else {}
    
    # Financial metrics
    avg_appt_value = 150
    base_no_show_rate = 0.18
    recovered_count = round((counts["confirmed"] + counts["rescheduled"]) * base_no_show_rate, 1)
    recovered_rev = int(recovered_count * avg_appt_value)
    
    # Outcomes mapping
    outcomes = await query_db("SELECT outcome, count(*) as count FROM calls WHERE business_id = ? GROUP BY outcome", [business_id])
    outcome_data = [{"name": o["outcome"], "value": int(o["count"])} for o in outcomes]
    
    return {
        "appointments": counts,
        "performance": {
            "avgStt": round(stats.get("avg_stt") or 0),
            "avgLlm": round(stats.get("avg_llm") or 0),
            "avgTts": round(stats.get("avg_tts") or 0),
            "avgTotal": round((stats.get("avg_stt") or 0) + (stats.get("avg_llm") or 0) + (stats.get("avg_tts") or 0)),
            "totalCostCents": stats.get("total_cost") or 0,
            "avgDuration": round(stats.get("avg_duration") or 0),
            "totalCalls": stats.get("total_calls") or 0
        },
        "roi": {
            "preventedNoShows": recovered_count,
            "recoveredRevenue": recovered_rev,
            "avgAppointmentValue": avg_appt_value
        },
        "outcomes": outcome_data
    }

# --- BILLING ---
@api_router.get("/billing/status")
async def billing_status(business_id: str = Depends(get_current_business_id)):
    rows = await query_db("SELECT plan, stripe_customer_id FROM businesses WHERE id = ?", [business_id])
    if not rows:
        raise HTTPException(status_code=404, detail="Business not found")
    return rows[0]

@api_router.post("/billing/checkout")
async def billing_checkout(payload: PlanUpgradeSchema, business_id: str = Depends(get_current_business_id)):
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    is_mock = not stripe_key
    checkout_url = f"/billing/success?plan={payload.plan}" if is_mock else "https://checkout.stripe.com/pay/mock"
    return {"url": checkout_url, "isMock": is_mock}

@api_router.post("/billing/success-callback")
async def billing_success(payload: PlanUpgradeSchema, business_id: str = Depends(get_current_business_id)):
    await query_db("UPDATE businesses SET plan = ? WHERE id = ?", [payload.plan, business_id])
    return {"success": True, "plan": payload.plan}

# --- SETTINGS ---
@api_router.get("/settings")
async def get_settings(business_id: str = Depends(get_current_business_id)):
    rows = await query_db("SELECT agent_name, voice_id, custom_greeting, business_faqs, webhook_url, sms_enabled FROM businesses WHERE id = ?", [business_id])
    if not rows:
        raise HTTPException(status_code=404, detail="Business settings not found")
    return rows[0]

@api_router.put("/settings")
async def update_settings(payload: SettingsUpdateSchema, business_id: str = Depends(get_current_business_id)):
    await query_db(
        """UPDATE businesses SET
            agent_name = ?,
            voice_id = ?,
            custom_greeting = ?,
            business_faqs = ?,
            webhook_url = ?,
            sms_enabled = ?
           WHERE id = ?""",
        [
            payload.agent_name or "Sarah",
            payload.voice_id or "en-US-AriaNeural",
            payload.custom_greeting or "",
            payload.business_faqs or "",
            payload.webhook_url or "",
            1 if payload.sms_enabled else 0,
            business_id
        ]
    )
    return {"success": True, "message": "Agent settings updated successfully"}

app.include_router(api_router)
