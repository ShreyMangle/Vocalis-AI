import sys
from pathlib import Path

# Add backend directory to python path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

import asyncio
from app.db import init_db, query_db
from app.pipeline import trigger_voice_call

async def main():
    await init_db()
    appts = await query_db("SELECT * FROM appointments WHERE customer_phone LIKE '%9028525745%' ORDER BY created_at DESC LIMIT 1")
    if not appts:
        print("[Error] No appointment found for +919028525745")
        return
    appt = appts[0]
    print(f"Triggering outbound call to {appt['customer_phone']} for {appt['customer_name']}...")
    call_id = await trigger_voice_call(appt)
    print(f"[OK] Call successfully dispatched! Call ID: {call_id}")

if __name__ == "__main__":
    asyncio.run(main())
