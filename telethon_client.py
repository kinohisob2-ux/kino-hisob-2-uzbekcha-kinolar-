from telethon import TelegramClient
from telethon.errors import UserNotParticipantError, ChatAdminRequiredError
from config import API_ID, API_HASH

# Telethon client - bot token bilan ishlaydi
client = None

async def init_telethon(bot_token):
    """Telethon clientni bot token bilan ishga tushirish"""
    global client
    # Bot token bilan client yaratish
    client = TelegramClient('bot_session', API_ID, API_HASH)
    await client.start(bot_token=bot_token)
    print("✅ Telethon client ishga tushdi")

async def check_user_in_chat_telethon(user_id, chat_identifier):
    """
    Telethon orqali foydalanuvchini kanal/guruhda tekshiradi.
    Zayafka yuborgan, Privacy Mode yoqilgan - hammasini tekshiradi!
    """
    global client
    if not client:
        print("❌ Telethon client ishga tushmagan")
        return None
    
    try:
        # Chat entity ni olish
        entity = None
        try:
            if chat_identifier.startswith("@"):
                entity = await client.get_entity(chat_identifier)
            elif chat_identifier.startswith("-100"):
                entity = await client.get_entity(int(chat_identifier))
            elif "t.me/" in chat_identifier:
                parts = chat_identifier.split("/")
                if len(parts) >= 2:
                    last = parts[-1]
                    if last.startswith("+"):
                        entity = await client.get_entity(chat_identifier)
                    else:
                        entity = await client.get_entity("@" + last)
            else:
                entity = await client.get_entity("@" + chat_identifier.lstrip("@"))
        except Exception as e:
            print(f"Entity olishda xatolik: {e}")
            return None
        
        if not entity:
            return None
        
        # Foydalanuvchi a'zoligini tekshirish
        try:
            # get_permissions orqali tekshiramiz
            participant = await client.get_permissions(entity, user_id)
            return True
        except UserNotParticipantError:
            return False
        except ChatAdminRequiredError:
            # Admin emas, lekin get_participants bilan tekshirib ko'ramiz
            try:
                participants = await client.get_participants(entity)
                for p in participants:
                    if p.id == user_id:
                        return True
                return False
            except:
                return None
        except Exception as e:
            print(f"Tekshirish xatolik: {e}")
            return None
            
    except Exception as e:
        print(f"Telethon tekshirish xatolik: {e}")
        return None

async def close_telethon():
    """Telethon clientni o'chirish"""
    global client
    if client:
        await client.disconnect()
        print("✅ Telethon client o'chirildi")
