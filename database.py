import asyncpg
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

async def get_db():
    return asyncpg.connect(DATABASE_URL)

async def init_db():
    conn = await get_db()
    try:
        # Users jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                first_name TEXT,
                username TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                last_active TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Videos jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id SERIAL PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                file_id TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Referrals jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                name TEXT,
                code TEXT UNIQUE NOT NULL,
                count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # User referrals jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_referrals (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                referral_code TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        
        # Ads jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ads (
                id SERIAL PRIMARY KEY,
                content_type TEXT,
                file_id TEXT,
                text TEXT,
                caption TEXT,
                send_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Mandatory subscriptions jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS mandatory_subscriptions (
                id SERIAL PRIMARY KEY,
                type TEXT NOT NULL,
                identifier TEXT NOT NULL,
                limit_count INTEGER DEFAULT 0,
                current_count INTEGER DEFAULT 0,
                chat_id BIGINT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # User mandatory subscriptions jadvali
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_mandatory_subscriptions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                subscription_id INTEGER NOT NULL,
                is_completed BOOLEAN DEFAULT FALSE,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (subscription_id) REFERENCES mandatory_subscriptions(id) ON DELETE CASCADE,
                UNIQUE(user_id, subscription_id)
            )
        """)
        
        print("✅ Barcha jadvallar yaratildi")
    finally:
        await conn.close()

async def register_user_start(user_id, referral_code=None):
    conn = await get_db()
    try:
        # Foydalanuvchi mavjudligini tekshirish
        exists = await conn.fetchval(
            "SELECT 1 FROM users WHERE user_id = $1", user_id
        )
        
        if not exists:
            # Yangi foydalanuvchi qo'shish
            await conn.execute(
                """
                INSERT INTO users (user_id, first_name, username, created_at, last_active)
                VALUES ($1, $2, $3, NOW(), NOW())
                """,
                user_id, None, None
            )
            
            # Referal kodini qayta ishlash
            if referral_code:
                # Referal havola orqali kelgan bo'lsa
                referral_exists = await conn.fetchval(
                    "SELECT 1 FROM referrals WHERE code = $1", referral_code
                )
                if referral_exists:
                    await conn.execute(
                        "UPDATE referrals SET count = count + 1 WHERE code = $1",
                        referral_code
                    )
                else:
                    # Foydalanuvchi ID orqali referal
                    referrer_exists = await conn.fetchval(
                        "SELECT 1 FROM users WHERE user_id = $1", 
                        int(referral_code) if referral_code.isdigit() else 0
                    )
                    if referrer_exists:
                        await conn.execute(
                            """
                            INSERT INTO user_referrals (user_id, referral_code)
                            VALUES ($1, $2)
                            """,
                            int(referral_code), str(user_id)
                        )
        else:
            # Mavjud foydalanuvchini yangilash
            await conn.execute(
                "UPDATE users SET last_active = NOW() WHERE user_id = $1",
                user_id
            )
    finally:
        await conn.close()

async def add_video(code, file_id, description=""):
    conn = await get_db()
    try:
        await conn.execute(
            """
            INSERT INTO videos (code, file_id, description)
            VALUES ($1, $2, $3)
            ON CONFLICT (code) DO UPDATE SET file_id = $2, description = $3
            """,
            code, file_id, description
        )
    finally:
        await conn.close()

async def get_video(code):
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT file_id, description FROM videos WHERE code = $1", code
        )
        if row:
            return (row["file_id"], row["description"])
        return None
    finally:
        await conn.close()

async def delete_video(code):
    conn = await get_db()
    try:
        await conn.execute("DELETE FROM videos WHERE code = $1", code)
    finally:
        await conn.close()

async def list_all_videos():
    conn = await get_db()
    try:
        rows = await conn.fetch(
            "SELECT code, description FROM videos ORDER BY code"
        )
        return [(row["code"], row["description"]) for row in rows]
    finally:
        await conn.close()

async def get_total_users():
    conn = await get_db()
    try:
        return await conn.fetchval("SELECT COUNT(*) FROM users")
    finally:
        await conn.close()

async def get_today_users():
    conn = await get_db()
    try:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE DATE(created_at) = CURRENT_DATE"
        )
    finally:
        await conn.close()

async def get_week_users():
    conn = await get_db()
    try:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL '7 days'"
        )
    finally:
        await conn.close()

async def get_active_users_last_24h():
    conn = await get_db()
    try:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE last_active >= NOW() - INTERVAL '24 hours'"
        )
    finally:
        await conn.close()

async def get_all_user_ids():
    conn = await get_db()
    try:
        rows = await conn.fetch("SELECT user_id FROM users")
        return [row["user_id"] for row in rows]
    finally:
        await conn.close()

async def create_referral(name, code):
    conn = await get_db()
    try:
        await conn.execute(
            "INSERT INTO referrals (name, code) VALUES ($1, $2)",
            name, code
        )
    finally:
        await conn.close()

async def check_referral_code(code):
    conn = await get_db()
    try:
        return await conn.fetchval(
            "SELECT 1 FROM referrals WHERE code = $1", code
        )
    finally:
        await conn.close()

async def get_all_referrals():
    conn = await get_db()
    try:
        rows = await conn.fetch(
            "SELECT code, name, count FROM referrals ORDER BY count DESC"
        )
        return [(row["code"], row["name"], row["count"]) for row in rows]
    finally:
        await conn.close()

async def get_user_referral_count(user_id):
    conn = await get_db()
    try:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM user_referrals WHERE user_id = $1", user_id
        )
    finally:
        await conn.close()

async def set_ad(content_type, file_id=None, text=None, caption=""):
    conn = await get_db()
    try:
        # Eski reklamani o'chirish
        await conn.execute("DELETE FROM ads")
        # Yangi reklama qo'shish
        await conn.execute(
            """
            INSERT INTO ads (content_type, file_id, text, caption)
            VALUES ($1, $2, $3, $4)
            """,
            content_type, file_id, text, caption
        )
    finally:
        await conn.close()

async def get_ad():
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            "SELECT content_type, file_id, text, caption, send_count FROM ads LIMIT 1"
        )
        if row:
            return dict(row)
        return None
    finally:
        await conn.close()

async def remove_ad():
    conn = await get_db()
    try:
        await conn.execute("DELETE FROM ads")
    finally:
        await conn.close()

async def increment_ad_count():
    conn = await get_db()
    try:
        await conn.execute(
            "UPDATE ads SET send_count = send_count + 1 WHERE id = (SELECT id FROM ads LIMIT 1)"
        )
    finally:
        await conn.close()

async def add_mandatory_subscription(sub_type, identifier, limit_count, chat_id=None):
    conn = await get_db()
    try:
        await conn.execute(
            """
            INSERT INTO mandatory_subscriptions (type, identifier, limit_count, chat_id)
            VALUES ($1, $2, $3, $4)
            """,
            sub_type, identifier, limit_count, chat_id
        )
    finally:
        await conn.close()

async def remove_mandatory_subscription(sub_id):
    conn = await get_db()
    try:
        await conn.execute(
            "DELETE FROM mandatory_subscriptions WHERE id = $1", sub_id
        )
    finally:
        await conn.close()

async def list_mandatory_subscriptions():
    conn = await get_db()
    try:
        rows = await conn.fetch(
            """
            SELECT id, type, identifier, limit_count, current_count, chat_id, is_active
            FROM mandatory_subscriptions ORDER BY id
            """
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def get_active_mandatory_subs():
    conn = await get_db()
    try:
        rows = await conn.fetch(
            """
            SELECT id, type, identifier, limit_count, current_count, chat_id, is_active
            FROM mandatory_subscriptions WHERE is_active = TRUE
            """
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()

async def is_user_completed_sub(user_id, subscription_id):
    conn = await get_db()
    try:
        result = await conn.fetchval(
            """
            SELECT is_completed FROM user_mandatory_subscriptions
            WHERE user_id = $1 AND subscription_id = $2
            """,
            user_id, subscription_id
        )
        return result if result is not None else False
    finally:
        await conn.close()

async def mark_user_completed_sub(user_id, subscription_id):
    conn = await get_db()
    try:
        await conn.execute(
            """
            INSERT INTO user_mandatory_subscriptions (user_id, subscription_id, is_completed, completed_at)
            VALUES ($1, $2, TRUE, NOW())
            ON CONFLICT (user_id, subscription_id)
            DO UPDATE SET is_completed = TRUE, completed_at = NOW()
            """,
            user_id, subscription_id
        )
        # current_count ni oshirish
        await conn.execute(
            """
            UPDATE mandatory_subscriptions
            SET current_count = current_count + 1
            WHERE id = $1
            """,
            subscription_id
        )
    finally:
        await conn.close()

async def set_user_completed_sub(user_id, subscription_id, is_completed):
    conn = await get_db()
    try:
        await conn.execute(
            """
            INSERT INTO user_mandatory_subscriptions (user_id, subscription_id, is_completed, completed_at)
            VALUES ($1, $2, $3, CASE WHEN $3 THEN NOW() ELSE NULL END)
            ON CONFLICT (user_id, subscription_id)
            DO UPDATE SET is_completed = $3, completed_at = CASE WHEN $3 THEN NOW() ELSE NULL END
            """,
            user_id, subscription_id, is_completed
        )
    finally:
        await conn.close()
