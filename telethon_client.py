from telethon import TelegramClient
from telethon.errors import UserNotParticipantError, ChatAdminRequiredError
from telethon.tl.functions.messages import GetChatJoinRequestsRequest
from telethon.tl.types import InputPeerChannel
from config import API_ID, API_HASH

client = None

async def init_telethon(bot_token):
    global client
    client = TelegramClient('bot_session', API_ID, API_HASH)
    await client.start(bot_token=bot_token)
    print("✅ Telethon client ishga tushdi")

async def check_user_in_chat_telethon(user_id, chat_identifier):
    """
    Tekshirish tartibi:
    1. get_permissions - a'zo bo'lganlarni tekshiradi
    2. GetChatJoinRequestsRequest - zayafka so'rovlarini tekshiradi
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
            
            print(f"Entity topildi: {entity.title if hasattr(entity, 'title') else entity.id}")
        except Exception as e:
            print(f"Entity olishda xatolik: {e}")
            return None
        
        if not entity:
            return None
        
        # 1-usul: get_permissions (a'zo bo'lganlar)
        try:
            await client.get_permissions(entity, user_id_int)
            print(f"✅ A'zo: user_id={user_id_int}")
            return True
        except UserNotParticipantError:
            print(f"A'zo emas, zayafka tekshiriladi...")
        except Exception as e:
            print(f"get_permissions xatolik: {e}")
        
        # 2-usul: Join Requests (zayafka so'rovlari)
        try:
            peer = InputPeerChannel(
                channel_id=entity.id,
                access_hash=entity.access_hash
            )
            
            result = await client(GetChatJoinRequestsRequest(
                peer=peer,
                limit=100,
                offset_date=None,
                offset_user=None
            ))
            
            if hasattr(result, 'participants'):
                print(f"Jami {len(result.participants)} ta zayafka so'rovi bor")
                for p in result.participants:
                    print(f"  - So'rov: user_id={p.user_id}")
                    if p.user_id == user_id_int:
                        print(f"✅ Zayafka so'rovi topildi: user_id={user_id_int}")
                        return True
                
                print(f"❌ Zayafka so'rovi topilmadi: user_id={user_id_int}")
                return False
            else:
                print(f"Zayafka so'rovlari yo'q")
                return False
                
        except ChatAdminRequiredError:
            print("❌ Bot admin emas!")
            return None
        except Exception as e:
            print(f"Join requests xatolik: {e}")
            return None
            
    except Exception as e:
        print(f"Umumiy xatolik: {e}")
        return None

async def close_telethon():
    global client
    if client:
        await client.disconnect()
        print("✅ Telethon client o'chirildi")
