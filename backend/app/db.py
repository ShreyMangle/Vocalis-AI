import os
import asyncio
import aiosqlite
try:
    import asyncpg
    has_asyncpg = True
except ImportError:
    has_asyncpg = False
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "")

is_postgres = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")
pg_pool = None
sqlite_db_path = None

async def init_db():
    global pg_pool, sqlite_db_path
    
    if is_postgres:
        if not has_asyncpg:
            raise ImportError("asyncpg is required to connect to PostgreSQL. Run 'pip install asyncpg' to install.")
        print("Database: Using PostgreSQL")
        pg_pool = await asyncpg.create_pool(DATABASE_URL)
    else:
        print("Database: Using SQLite (Fallback)")
        data_dir = Path(__file__).resolve().parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        sqlite_db_path = data_dir / "database.sqlite"
        
    await create_tables()

async def create_tables():
    schema = [
        """CREATE TABLE IF NOT EXISTS businesses (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            industry TEXT,
            timezone TEXT,
            phone_number TEXT,
            stripe_customer_id TEXT,
            plan TEXT DEFAULT 'free',
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            agent_name TEXT DEFAULT 'Sarah',
            voice_id TEXT DEFAULT 'en-US-AriaNeural',
            custom_greeting TEXT,
            business_faqs TEXT,
            webhook_url TEXT,
            sms_enabled INTEGER DEFAULT 1,
            supported_languages TEXT DEFAULT '["English", "Hindi"]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS appointments (
            id TEXT PRIMARY KEY,
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            scheduled_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            supported_languages TEXT DEFAULT '["English", "Hindi"]',
            original_scheduled_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS calls (
            id TEXT PRIMARY KEY,
            appointment_id TEXT REFERENCES appointments(id) ON DELETE CASCADE,
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            outcome TEXT,
            transcript TEXT, -- JSON string list
            duration_seconds INTEGER DEFAULT 0,
            cost_cents INTEGER DEFAULT 0,
            recording_url TEXT,
            stt_latency_ms INTEGER DEFAULT 0,
            llm_latency_ms INTEGER DEFAULT 0,
            tts_latency_ms INTEGER DEFAULT 0,
            sentiment TEXT DEFAULT 'Neutral',
            intent TEXT DEFAULT 'Confirmation',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS available_slots (
            id TEXT PRIMARY KEY,
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            slot_time TEXT NOT NULL,
            is_booked INTEGER DEFAULT 0
        )"""
    ]

    for query in schema:
        try:
            await query_db(query)
        except Exception as e:
            print(f"Error creating table: {e}")

    # Migrations for existing databases
    migrations = [
        "ALTER TABLE businesses ADD COLUMN agent_name TEXT DEFAULT 'Sarah'",
        "ALTER TABLE businesses ADD COLUMN voice_id TEXT DEFAULT 'en-US-AriaNeural'",
        "ALTER TABLE businesses ADD COLUMN custom_greeting TEXT",
        "ALTER TABLE businesses ADD COLUMN business_faqs TEXT",
        "ALTER TABLE businesses ADD COLUMN webhook_url TEXT",
        "ALTER TABLE businesses ADD COLUMN sms_enabled INTEGER DEFAULT 1",
        "ALTER TABLE businesses ADD COLUMN speech_speed TEXT DEFAULT '+0%'",
        "ALTER TABLE businesses ADD COLUMN vad_sensitivity TEXT DEFAULT 'normal'",
        "ALTER TABLE businesses ADD COLUMN supported_languages TEXT DEFAULT '[\"English\", \"Hindi\"]'",
        "ALTER TABLE appointments ADD COLUMN supported_languages TEXT DEFAULT '[\"English\", \"Hindi\"]'",
        "ALTER TABLE calls ADD COLUMN sentiment TEXT DEFAULT 'Neutral'",
        "ALTER TABLE calls ADD COLUMN intent TEXT DEFAULT 'Confirmation'",
        "ALTER TABLE calls ADD COLUMN notes TEXT"
    ]
    for m in migrations:
        try:
            await query_db(m)
        except Exception:
            pass # Column already exists

async def query_db(sql: str, params: list = []):
    global pg_pool, sqlite_db_path
    
    if is_postgres:
        # Translate '?' parameters to '$1, $2' parameters for PostgreSQL
        pg_sql = sql
        param_count = 1
        while '?' in pg_sql:
            pg_sql = pg_sql.replace('?', f"${param_count}", 1)
            param_count += 1
            
        async with pg_pool.acquire() as conn:
            # asyncpg's fetch handles SELECT and return lists of records.
            # Execute handles mutations.
            is_select = sql.strip().lower().startswith("select")
            if is_select:
                rows = await conn.fetch(pg_sql, *params)
                # Convert Record object to standard dictionaries
                return [dict(r) for r in rows]
            else:
                res = await conn.execute(pg_sql, *params)
                return res
    else:
        # SQLite
        async with aiosqlite.connect(sqlite_db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(sql, params) as cursor:
                is_select = sql.strip().lower().startswith("select")
                if is_select:
                    rows = await cursor.fetchall()
                    return [dict(r) for r in rows]
                else:
                    await conn.commit()
                    return {"lastrowid": cursor.lastrowid, "rowcount": cursor.rowcount}
