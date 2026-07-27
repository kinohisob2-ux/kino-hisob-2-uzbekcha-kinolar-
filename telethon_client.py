from telethon import TelegramClient
from telethon.errors import UserNotParticipantError, ChatAdminRequiredError
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsKicked, InputPeerChannel
from config import API_ID, API_HASH

client = None

async def init_telethon(bot_token):
    """Telethon clientni bot token bilan ishga tushirish"""
    global client
    client = TelegramClient('bot_session', API_ID, API_HASH)
    await client.start(bot_token=bot_token)
    print("✅ Telethon client ishga tushdi")

async def check_user_in_chat_telethon(user_id, chat_identifier):
    """
    Tekshirish tartibi:
    1. get_permissions - a'zo bo'lganlarni tekshiradi
    2. get_participants - barcha ishtirokchilarni tekshiradi (zayafka + a'zo)
    """
    global client
    if not client:
        print("❌ Telethon client ishga tushmagan")
        return None
    
    try:
        chat_id_str = str(chat_identifier)
        user_id_int = int(user_id)
        
        # Entity olish
        entity = None
        try:
            if chat_id_str.startswith("-100"):
                entity = await client.get_entity(int(chat_id_str))
            elif chat_id_str.startswith("-"):
                entity = await client.get_entity(int(chat_id_str))
            elif chat_id_str.startswith("@"):
                entity = await client.get_entity(chat_id_str)
            elif "t.me/" in chat_id_str:
                entity = await client.get_entity(chat_id_str)
            elif chat_id_str.lstrip("-").isdigit():
                entity = await client.get_entity(int(chat_id_str))
            else:
                entity = await client.get_entity("@" + chat_id_str.lstrip("@"))
        except Exception as e:
            print(f"Entity olishda xatolik: {e}")
            return None
        
        if not entity:
            print(f"Entity topilmadi: {chat_id_str}")
            return None
        
        print(f"Entity: {entity.title if hasattr(entity, 'title') else entity.id}")
        
        # 1-usul: get_permissions (a'zo bo'lganlar)
        try:
            await client.get_permissions(entity, user_id_int)
            print(f"✅ A'zo: user_id={user_id_int}")
            return True
        except UserNotParticipantError:
            print(f"A'zo emas: {user_id_int}")
        except Exception as e:
            print(f"get_permissions xatolik: {e}")
        
        # 2-usul: get_participants (barcha: a'zo + admin + zayafka)
        try:
            print("get_participants orqali tekshirilmoqda...")
            participants = await client.get_participants(entity, limit=200)
            
            for p in participants:
                if p.id == user_id_int:
                    print(f"✅ Topildi (get_participants): user_id={user_id_int}")
                    return True
            
            print(f"❌ Topilmadi: user_id={user_id_int}")
            return False
            
        except ChatAdminRequiredError:
            print("❌ Bot admin emas!")
            return None
        except Exception as e:
            print(f"get_participants xatolik: {e}")
            return None
            
    except Exception as e:
        print(f"Umumiy xatolik: {e}")
        return None

async def close_telethon():
    """Telethon clientni o'chirish"""
    global client
    if client:
        await client.disconnect()
        print("✅ Telethon client o'chirildi")
