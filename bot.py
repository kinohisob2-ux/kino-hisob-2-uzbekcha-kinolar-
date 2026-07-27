import os
import asyncio
import secrets
import time
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.requests import Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, CallbackContext, CallbackQueryHandler
)
from dotenv import load_dotenv

from config import BOT_TOKEN, ADMIN_ID
from database import (
    init_db, add_video, get_video, delete_video, list_all_videos,
    register_user_start, get_total_users, get_today_users,
    get_week_users, get_active_users_last_24h,
    get_all_user_ids, create_referral, check_referral_code, get_all_referrals,
    set_ad, get_ad, remove_ad, increment_ad_count,
    get_active_mandatory_subs, is_user_completed_sub, mark_user_completed_sub,
    add_mandatory_subscription, remove_mandatory_subscription, list_mandatory_subscriptions,
    set_user_completed_sub
)

load_dotenv()

# ======================== Holatlar ========================
WAITING_FOR_VIDEO, WAITING_FOR_CUSTOM_CODE, WAITING_FOR_DESCRIPTION = range(3)
WAITING_BROADCAST = 3
WAITING_REF_NAME = 4
WAITING_AD_CONTENT = 5

# ======================== Webhook ========================
WEBHOOK_PATH = "/webhook"
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if not RENDER_EXTERNAL_HOSTNAME:
    raise ValueError("RENDER_EXTERNAL_HOSTNAME topilmadi")
WEBHOOK_URL = f"https://{RENDER_EXTERNAL_HOSTNAME}{WEBHOOK_PATH}"

# ======================== Reklama ========================
async def send_ad(bot, chat_id):
    ad = await get_ad()
    if not ad:
        return
    content_type = ad["content_type"]
    file_id = ad["file_id"]
    text = ad["text"]
    caption = ad["caption"] or ""
    try:
        if content_type == "text":
            await bot.send_message(chat_id=chat_id, text=text)
        elif content_type == "photo":
            await bot.send_photo(chat_id=chat_id, photo=file_id, caption=caption)
        elif content_type == "video":
            await bot.send_video(chat_id=chat_id, video=file_id, caption=caption)
        elif content_type == "document":
            await bot.send_document(chat_id=chat_id, document=file_id, caption=caption)
        elif content_type == "audio":
            await bot.send_audio(chat_id=chat_id, audio=file_id, caption=caption)
        elif content_type == "voice":
            await bot.send_voice(chat_id=chat_id, voice=file_id, caption=caption)
        elif content_type == "animation":
            await bot.send_animation(chat_id=chat_id, animation=file_id, caption=caption)
        await increment_ad_count()
    except Exception as e:
        print(f"Reklama yuborishda xatolik: {e}")


# ======================== Telegram a'zolik tekshiruvi ========================
async def check_telegram_membership(bot, user_id, chat_identifier):
    """Kanal/guruh/bot a'zoligini tekshiradi"""
    try:
        chat_id = chat_identifier
        if not chat_id.startswith("@"):
            if "t.me/" in chat_id:
                parts = chat_id.split("/")
                if len(parts) >= 2:
                    username = parts[-1]
                    if not username.startswith("+") and "joinchat" not in username:
                        chat_id = "@" + username
                    else:
                        return False
            else:
                chat_id = "@" + chat_id.lstrip("@")
        
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Membership check error for {chat_identifier}: {e}")
        return False


# ======================== Majburiy obuna interfeysi ========================
async def show_mandatory_subs(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    subs = await get_active_mandatory_subs()
    if not subs:
        return True

    incomplete = []
    for sub in subs:
        if not await is_user_completed_sub(user_id, sub["id"]):
            incomplete.append(sub)

    if not incomplete:
        return True

    type_icons = {
        "telegram": "📢",
        "group": "👥",
        "invite": "🔗",
        "bot": "🤖",
        "youtube": "▶️",
        "instagram": "📷",
        "website": "🌐"
    }

    text = "🔔 <b>Botdan foydalanish uchun quyidagilarni bajaring:</b>\n\n"
    url_buttons = []

    for idx, sub in enumerate(incomplete, start=1):
        sub_type = sub["type"]
        identifier = sub["identifier"]
        icon = type_icons.get(sub_type, "📌")

        if sub_type == "telegram":
            button_text = f"{icon} {idx}-kanalga obuna bo'lish"
            url = f"https://t.me/{identifier.lstrip('@')}" if identifier.startswith("@") else identifier
        elif sub_type == "group":
            button_text = f"{icon} {idx}-guruhga qo'shilish"
            url = f"https://t.me/{identifier.lstrip('@')}" if identifier.startswith("@") else identifier
        elif sub_type == "invite":
            button_text = f"{icon} {idx}-guruhga qo'shilish (zayafka)"
            url = identifier
        elif sub_type == "bot":
            button_text = f"{icon} {idx}-botni ishga tushirish"
            url = f"https://t.me/{identifier.lstrip('@')}" if identifier.startswith("@") else identifier
        elif sub_type == "youtube":
            button_text = f"{icon} {idx}-YouTube kanali"
            url = identifier
        elif sub_type == "instagram":
            button_text = f"{icon} {idx}-Instagram sahifasi"
            url = identifier
        elif sub_type == "website":
            button_text = f"{icon} {idx}-Vebsaytga o'tish"
            url = identifier
        else:
            button_text = f"{icon} {idx}-havola"
            url = identifier

        url_buttons.append([InlineKeyboardButton(button_text, url=url)])

    confirm_button = [[InlineKeyboardButton("✅ Barchasini bajardim", callback_data="confirm_all_subs")]]
    reply_markup = InlineKeyboardMarkup(url_buttons + confirm_button)

    if "mandatory_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=context.user_data["mandatory_msg_id"])
        except:
            pass

    sent_msg = await update.message.reply_text(
        text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True
    )
    context.user_data["mandatory_msg_id"] = sent_msg.message_id
    return False


# ======================== Majburiy obuna tekshiruvi ========================
async def check_and_handle_mandatory_subs(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    cache_key = "sub_check_cache"
    cache_time_key = "sub_check_time"
    current_time = time.time()

    if cache_time_key in context.user_data:
        if current_time - context.user_data[cache_time_key] < 30:
            if context.user_data.get(cache_key, False):
                await show_mandatory_subs(update, context)
                return True
            return False

    subs = await get_active_mandatory_subs()
    if not subs:
        context.user_data[cache_key] = False
        context.user_data[cache_time_key] = current_time
        return False

    telegram_check_types = ["telegram", "group"]

    async def check_sub(sub):
        if sub["type"] in telegram_check_types:
            is_member = await check_telegram_membership(context.bot, user_id, sub["identifier"])
            return (sub, is_member)
        else:
            is_completed = await is_user_completed_sub(user_id, sub["id"])
            return (sub, is_completed)

    results = await asyncio.gather(*[check_sub(sub) for sub in subs])

    incomplete = []
    for sub, is_ok in results:
        if sub["type"] in telegram_check_types:
            if not is_ok:
                await set_user_completed_sub(user_id, sub["id"], False)
                incomplete.append(sub)
            else:
                if not await is_user_completed_sub(user_id, sub["id"]):
                    await mark_user_completed_sub(user_id, sub["id"])
        else:
            if not is_ok:
                incomplete.append(sub)

    context.user_data[cache_time_key] = current_time
    if incomplete:
        context.user_data[cache_key] = True
        await show_mandatory_subs(update, context)
        return True
    else:
        context.user_data[cache_key] = False
        return False


# ======================== Callback: obunani tasdiqlash ========================
async def confirm_all_subs_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    subs = await get_active_mandatory_subs()
    if not subs:
        await query.edit_message_text("✅ Hech qanday majburiy obuna mavjud emas.")
        await start_after_subs(update, context)
        return

    still_incomplete = []
    for sub in subs:
        if not await is_user_completed_sub(user_id, sub["id"]):
            still_incomplete.append(sub)

    if not still_incomplete:
        await query.edit_message_text("✅ Barchasi tayyor! Botdan foydalanishingiz mumkin.")
        await start_after_subs(update, context)
        return

    telegram_check_types = ["telegram", "group"]

    async def check_single_sub(sub):
        if sub["type"] in telegram_check_types:
            is_member = await check_telegram_membership(context.bot, user_id, sub["identifier"])
            return (sub, is_member)
        else:
            return (sub, True)

    results = await asyncio.gather(*[check_single_sub(sub) for sub in still_incomplete])

    failed = []
    for sub, is_ok in results:
        if not is_ok:
            name = sub["identifier"].replace("@", "").replace("https://", "").replace("t.me/", "")
            failed.append(f"❌ {name}")

    if failed:
        msg_text = (
            "Quyidagilarga a'zo bo'lmagansiz:\n\n" +
            "\n".join(failed) +
            "\n\nIltimos, avval ularga qo'shiling va qayta tekshiring."
        )
        await query.edit_message_text(msg_text, disable_web_page_preview=True)
        return

    for sub in still_incomplete:
        await mark_user_completed_sub(user_id, sub["id"])

    await query.edit_message_text("✅ Ajoyib! Barcha talablar bajarildi. Botdan foydalanishingiz mumkin!")

    if "mandatory_msg_id" in context.user_data:
        del context.user_data["mandatory_msg_id"]

    await start_after_subs(update, context)


async def start_after_subs(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if update.callback_query:
        message = update.callback_query.message
    else:
        message = update.message

    await message.reply_text(
        "🎬 Kino botiga xush kelibsiz!\n"
        "📣 Kino kanalimiz: @kino_boru\n\n"
        "Film kodini raqamlarda yuboring.\n"
        "Admin: /admin"
    )
    asyncio.create_task(send_ad(context.bot, user_id))


# ======================== Start ========================
async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    referral_code = context.args[0] if context.args else None
    await register_user_start(user_id, referral_code)

    if await check_and_handle_mandatory_subs(update, context):
        return

    await start_after_subs(update, context)


# ======================== Admin panel ========================
async def admin(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Siz admin emassiz!")
        return
    await update.message.reply_text(
        "<b>🔧 Admin panel</b>\n\n"
        "/addvideo - yangi video qo'shish\n"
        "/delvideo &lt;kod&gt; - o'chirish\n"
        "/list - barcha videolar\n"
        "/stats - statistika\n"
        "/broadcast - obunachilarga xabar\n"
        "/createref - referal havola yaratish\n"
        "/refstats - referallar statistikasi\n"
        "/setad - reklama o'rnatish\n"
        "/removead - reklamani o'chirish\n"
        "/adstats - reklama statistikasi\n\n"
        "<b>📛 Majburiy obuna qo'shish:</b>\n"
        "/add_mandatory &lt;tur&gt; &lt;havola&gt; &lt;limit&gt;\n\n"
        "<b>Turlar:</b>\n"
        "• <code>telegram</code> - Telegram kanal\n"
        "• <code>group</code> - Telegram guruh (publik)\n"
        "• <code>invite</code> - Zayafka link\n"
        "• <code>bot</code> - Telegram bot\n"
        "• <code>youtube</code> - YouTube kanal\n"
        "• <code>instagram</code> - Instagram sahifa\n"
        "• <code>website</code> - Vebsayt\n\n"
        "<b>Misollar:</b>\n"
        "/add_mandatory telegram @kino_kanal 5000\n"
        "/add_mandatory group @kino_guruh 2000\n"
        "/add_mandatory invite https://t.me/+abc123 1000\n"
        "/add_mandatory bot @kinobot 3000\n"
        "/add_mandatory youtube https://youtube.com/@kanal 5000\n\n"
        "/remove_mandatory &lt;id&gt; - o'chirish\n"
        "/list_mandatory - ro'yxat",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# ======================== Statistika ========================
async def stats(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    total = await get_total_users()
    today = await get_today_users()
    week = await get_week_users()
    active = await get_active_users_last_24h()
    await update.message.reply_text(
        f"📊 Statistika\n\n"
        f"👥 Umumiy: {total}\n"
        f"🆕 Bugun: {today}\n"
        f"📅 7 kunda: {week}\n"
        f"🟢 24 soatda faol: {active}"
    )


# ======================== Broadcast ========================
async def broadcast_start(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text(
        "📢 Barcha obunachilarga yubormoqchi bo'lgan xabaringizni yuboring.\n"
        "/cancel – bekor qilish"
    )
    return WAITING_BROADCAST


async def broadcast_send(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    msg = update.message
    user_ids = await get_all_user_ids()
    total = len(user_ids)
    progress_msg = await msg.reply_text(f"📤 {total} ta foydalanuvchiga jo'natish boshlandi...")
    asyncio.create_task(_broadcast_task(msg, progress_msg, user_ids, total))
    return ConversationHandler.END


async def _broadcast_task(msg, progress_msg, user_ids, total):
    semaphore = asyncio.Semaphore(25)

    async def send_to_user(uid):
        async with semaphore:
            try:
                await msg.copy(chat_id=uid)
            except:
                pass

    tasks = [asyncio.create_task(send_to_user(uid)) for uid in user_ids]
    await asyncio.gather(*tasks)
    await progress_msg.edit_text(f"✅ Xabar {total} ta foydalanuvchiga yuborildi.")


# ======================== Video qo'shish ========================
async def addvideo_start(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text("📹 Videoni yuboring (fayl sifatida)")
    return WAITING_FOR_VIDEO


async def addvideo_video(update: Update, context: CallbackContext):
    if not update.message.video:
        await update.message.reply_text("❌ Iltimos, video fayl yuboring")
        return WAITING_FOR_VIDEO
    file_id = update.message.video.file_id
    context.user_data['file_id'] = file_id
    await update.message.reply_text("🔢 Kod kiriting (faqat raqamlar):")
    return WAITING_FOR_CUSTOM_CODE


async def addvideo_custom_code(update: Update, context: CallbackContext):
    code = update.message.text.strip()
    if not code.isdigit():
        await update.message.reply_text("❌ Kod faqat raqamlardan iborat bo'lishi kerak:")
        return WAITING_FOR_CUSTOM_CODE
    existing = await get_video(code)
    if existing:
        await update.message.reply_text(f"⚠️ {code} kodi mavjud. Boshqa kod kiriting:")
        return WAITING_FOR_CUSTOM_CODE
    context.user_data['code'] = code
    await update.message.reply_text("✍️ Tavsif yozing (yoki /skip)")
    return WAITING_FOR_DESCRIPTION


async def addvideo_description(update: Update, context: CallbackContext):
    description = update.message.text
    file_id = context.user_data.get('file_id')
    code = context.user_data.get('code')
    if not file_id or not code:
        return ConversationHandler.END
    await add_video(code, file_id, description)
    await update.message.reply_text(f"✅ Video saqlandi!\nKod: {code}\nTavsif: {description}")
    context.user_data.clear()
    return ConversationHandler.END


async def addvideo_skip(update: Update, context: CallbackContext):
    file_id = context.user_data.get('file_id')
    code = context.user_data.get('code')
    if not file_id or not code:
        return ConversationHandler.END
    await add_video(code, file_id, "")
    await update.message.reply_text(f"✅ Video saqlandi!\nKod: {code}\nTavsifsiz")
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text("Bekor qilindi.")
    return ConversationHandler.END


# ======================== Video o'chirish ========================
async def delvideo(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("📛 Kodni kiriting: /delvideo 123")
        return
    code = context.args[0]
    video = await get_video(code)
    if video:
        await delete_video(code)
        await update.message.reply_text(f"✅ {code} o'chirildi.")
    else:
        await update.message.reply_text(f"❌ {code} topilmadi.")


async def listvideos(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    videos = await list_all_videos()
    if not videos:
        await update.message.reply_text("📭 Hech qanday video yo'q.")
        return
    text = "📋 Barcha videolar:\n"
    for code, desc in videos:
        text += f"🔹 Kod: {code} — {desc or 'Tavsifsiz'}\n"
    await update.message.reply_text(text)


# ======================== Referal ========================
async def createref_start(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text("🔗 Referal uchun nom bering:")
    return WAITING_REF_NAME


async def createref_get_name(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("❌ Bo'sh bo'lmagan nom kiriting.")
        return WAITING_REF_NAME
    bot_username = "KINO_bor_botbot"
    while True:
        code = secrets.token_hex(3)
        if not await check_referral_code(code):
            break
    await create_referral(name, code)
    link = f"https://t.me/{bot_username}?start={code}"
    await update.message.reply_text(
        f"✅ Yangi referal havola yaratildi\n\n"
        f"📌 Nomi: {name}\n"
        f"🔗 Havola: {link}\n"
        f"🆔 Kod: {code}"
    )
    return ConversationHandler.END


async def refstats(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    referrals = await get_all_referrals()
    if not referrals:
        await update.message.reply_text("📭 Hali hech qanday referal havola yo'q.")
        return
    text = "📊 Referallar statistikasi\n\n"
    for code, name, count in referrals:
        text += f"• {name} (kod: {code}) – {count} ta\n"
    await update.message.reply_text(text)


# ======================== Reklama ========================
async def setad_start(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    await update.message.reply_text("📢 Reklama kontentini yuboring.\n/cancel – bekor qilish")
    return WAITING_AD_CONTENT


async def setad_get_content(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    msg = update.message
    content_type = None
    file_id = None
    text = None
    caption = msg.caption or ""

    if msg.text and not msg.caption:
        content_type = "text"
        text = msg.text
    elif msg.photo:
        content_type = "photo"
        file_id = msg.photo[-1].file_id
    elif msg.video:
        content_type = "video"
        file_id = msg.video.file_id
    elif msg.document:
        content_type = "document"
        file_id = msg.document.file_id
    elif msg.audio:
        content_type = "audio"
        file_id = msg.audio.file_id
    elif msg.voice:
        content_type = "voice"
        file_id = msg.voice.file_id
    elif msg.animation:
        content_type = "animation"
        file_id = msg.animation.file_id
    else:
        await update.message.reply_text("❌ Qo'llab-quvvatlanmaydi. Boshqa narsa yuboring.")
        return WAITING_AD_CONTENT

    await set_ad(content_type, file_id, text, caption)
    await update.message.reply_text(f"✅ Reklama saqlandi!\nTuri: {content_type}")
    return ConversationHandler.END


async def removead(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    await remove_ad()
    await update.message.reply_text("🗑️ Reklama o'chirildi.")


async def adstats(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    ad = await get_ad()
    if ad:
        count = ad["send_count"]
        await update.message.reply_text(f"📊 Reklama {count} marta yuborilgan.")
    else:
        await update.message.reply_text("📭 Reklama o'rnatilmagan.")


# ======================== Majburiy obuna admin ========================
async def add_mandatory(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Ishlatish: /add_mandatory <type> <identifier> <limit>\n"
            "Masalan: /add_mandatory telegram @my_channel 5000"
        )
        return
    sub_type, identifier, limit = args[0], args[1], int(args[2])
    valid_types = ["telegram", "group", "invite", "bot", "youtube", "instagram", "website"]
    if sub_type not in valid_types:
        await update.message.reply_text(f"❌ Tur noto'g'ri. Qabul qilinadi: {', '.join(valid_types)}")
        return
    await add_mandatory_subscription(sub_type, identifier, limit)
    await update.message.reply_text(f"✅ Qo'shildi: {sub_type} – {identifier} (limit {limit})")


async def remove_mandatory(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Ishlatish: /remove_mandatory <id>")
        return
    sub_id = int(context.args[0])
    await remove_mandatory_subscription(sub_id)
    await update.message.reply_text(f"✅ ID {sub_id} o'chirildi.")


async def list_mandatory(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    rows = await list_mandatory_subscriptions()
    if not rows:
        await update.message.reply_text("Hech qanday majburiy obuna yo'q.")
        return

    text = "📋 Majburiy obunalar:\n\n"
    for r in rows:
        status = "✅ faol" if r["is_active"] else "❌ faol emas"
        text += (
            f"ID {r['id']}: {r['type']} | {r['identifier']}\n"
            f"  Limit: {r['limit_count']} | Bajargan: {r['current_count']} | {status}\n\n"
        )

    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await update.message.reply_text(text[i:i+4000])
    else:
        await update.message.reply_text(text)


# ======================== Kod yuborish ========================
async def handle_code(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if await check_and_handle_mandatory_subs(update, context):
        return

    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("🤔 Iltimos, faqat raqamlardan iborat kod yuboring.")
        return

    video = await get_video(text)
    if video:
        file_id, description = video
        caption = f"🎬 Kodi: {text}\n📖 {description}" if description else f"🎬 Kodi: {text}"
        try:
            await update.message.reply_video(
                video=file_id, caption=caption, supports_streaming=True, protect_content=True
            )
        except Exception as e:
            print(f"Video yuborish xatosi: {e}")
            await update.message.reply_text("❌ Video yuborishda xatolik yuz berdi.")
            return
        links_msg = (
            "📱 Instagram: https://instagram.com/Bear_uzb070\n"
            "📣 Kino kanal: @kino_boru"
        )
        await update.message.reply_text(links_msg)
        await send_ad(context.bot, user_id)
    else:
        await update.message.reply_text(f"❌ {text} kodli video topilmadi.")


# ======================== Webhook ========================
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot_application.bot)
    await bot_application.process_update(update)
    return JSONResponse({"ok": True})


async def healthcheck(request: Request):
    return JSONResponse({"status": "ok"})


bot_application = None


# ======================== Main ========================
async def main():
    global bot_application
    await init_db()
    bot_application = Application.builder().token(BOT_TOKEN).build()

    private_filter = filters.ChatType.PRIVATE

    bot_application.add_handler(CommandHandler("start", start, filters=private_filter))
    bot_application.add_handler(CommandHandler("admin", admin, filters=private_filter))
    bot_application.add_handler(CommandHandler("stats", stats, filters=private_filter))
    bot_application.add_handler(CommandHandler("delvideo", delvideo, filters=private_filter))
    bot_application.add_handler(CommandHandler("list", listvideos, filters=private_filter))
    bot_application.add_handler(CommandHandler("refstats", refstats, filters=private_filter))
    bot_application.add_handler(CommandHandler("removead", removead, filters=private_filter))
    bot_application.add_handler(CommandHandler("adstats", adstats, filters=private_filter))
    bot_application.add_handler(CommandHandler("cancel", cancel, filters=private_filter))
    bot_application.add_handler(CommandHandler("add_mandatory", add_mandatory, filters=private_filter))
    bot_application.add_handler(CommandHandler("remove_mandatory", remove_mandatory, filters=private_filter))
    bot_application.add_handler(CommandHandler("list_mandatory", list_mandatory, filters=private_filter))
    bot_application.add_handler(CallbackQueryHandler(confirm_all_subs_callback, pattern="^confirm_all_subs$"))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("addvideo", addvideo_start, filters=private_filter)],
        states={
            WAITING_FOR_VIDEO: [MessageHandler(filters.VIDEO & private_filter, addvideo_video)],
            WAITING_FOR_CUSTOM_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & private_filter, addvideo_custom_code)
            ],
            WAITING_FOR_DESCRIPTION: [
                CommandHandler("skip", addvideo_skip, filters=private_filter),
                MessageHandler(filters.TEXT & ~filters.COMMAND & private_filter, addvideo_description)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel, filters=private_filter)]
    )
    bot_application.add_handler(conv_handler)

    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start, filters=private_filter)],
        states={
            WAITING_BROADCAST: [
                MessageHandler(filters.ALL & ~filters.COMMAND & private_filter, broadcast_send)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel, filters=private_filter)]
    )
    bot_application.add_handler(broadcast_conv)

    ref_conv = ConversationHandler(
        entry_points=[CommandHandler("createref", createref_start, filters=private_filter)],
        states={
            WAITING_REF_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & private_filter, createref_get_name)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel, filters=private_filter)]
    )
    bot_application.add_handler(ref_conv)

    ad_conv = ConversationHandler(
        entry_points=[CommandHandler("setad", setad_start, filters=private_filter)],
        states={
            WAITING_AD_CONTENT: [
                MessageHandler(filters.ALL & ~filters.COMMAND & private_filter, setad_get_content)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel, filters=private_filter)]
    )
    bot_application.add_handler(ad_conv)

    bot_application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & private_filter, handle_code)
    )

    await bot_application.initialize()
    await bot_application.bot.set_webhook(WEBHOOK_URL)

    starlette_app = Starlette(debug=False, routes=[
        Route(WEBHOOK_PATH, webhook_handler, methods=["POST"]),
        Route("/healthcheck", healthcheck, methods=["GET"]),
    ])

    port = int(os.environ.get("PORT", 8080))
    print(f"✅ Bot ishga tushdi, webhook: {WEBHOOK_URL}")
    import uvicorn
    config = uvicorn.Config(starlette_app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
