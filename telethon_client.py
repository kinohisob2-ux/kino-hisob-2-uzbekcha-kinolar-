from telethon import TelegramClient
from telethon.errors import UserNotParticipantError, ChatAdminRequiredError
from config import API_ID, API_HASH

# Telethon client
client = None

async def init_telethon(bot_token):
    """Telethon clientni bot token bilan ishga tushirish"""
    global client
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
        # chat_identifier ni stringga aylantiramiz
        chat_id_str = str(chat_identifier)
        user_id_int = int(user_id)
        
        entity = None
        try:
            # Raqamli chat_id (manfiy sonlar bilan boshlanadi)
            if chat_id_str.startswith("-100"):
                entity = await client.get_entity(int(chat_id_str))
            elif chat_id_str.startswith("-"):
                entity = await client.get_entity(int(chat_id_str))
            # Username
            elif chat_id_str.startswith("@"):
                entity = await client.get_entity(chat_id_str)
            # Havola
            elif "t.me/" in chat_id_str:
                parts = chat_id_str.split("/")
                if len(parts) >= 2:
                    last = parts[-1]
                    if last.startswith("+"):
                        entity = await client.get_entity(chat_id_str)
                    else:
                        entity = await client.get_entity("@" + last)
            # Son formatda
            elif chat_id_str.lstrip("-").isdigit():
                entity = await client.get_entity(int(chat_id_str))
            # Boshqa holat - username deb hisoblaymiz
            else:
                entity = await client.get_entity("@" + chat_id_str.lstrip("@"))
                
            if not entity:
                print(f"Entity topilmadi: {chat_id_str}")
                return None
                
        except ValueError as e:
            print(f"Noto'g'ri chat_id formati: {chat_id_str}, xatolik: {e}")
            return None
        except Exception as e:
            print(f"Entity olishda xatolik ({chat_id_str}): {e}")
            return None
        
        # Foydalanuvchi a'zoligini tekshirish
        try:
            await client.get_permissions(entity, user_id_int)
            return True
        except UserNotParticipantError:
            return False
        except ChatAdminRequiredError:
            # Admin emas - get_participants bilan tekshirib ko'ramiz
            try:
                participants = await client.get_participants(entity)
                for p in participants:
                    if p.id == user_id_int:
                        return True
                return False
            except Exception as e:
                print(f"get_participants xatolik: {e}")
                return None
        except Exception as e:
            print(f"get_permissions xatolik: {e}")
            return None
            
    except Exception as e:
        print(f"Telethon umumiy xatolik: {e}")
        return None

async def close_telethon():
    """Telethon clientni o'chirish"""
    global client
    if client:
        await client.disconnect()
        print("✅ Telethon client o'chirildi")
