import logging
import re
import os
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes
)

# ================= কনফিগারেশন =================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9088126091:AAFE8D5PkiggMHTxGFbbb8mxOIwaAlF5NOg")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://red-x-guard.onrender.com")
PORT = int(os.environ.get("PORT", 10000))
CONTROLLER_IDS = [6729349333, 8267564240]

BAD_WORDS = [
    "fuck", "shit", "bitch", "asshole", "bastard", "dick", "pussy", "slut", "whore",
    "মাদারচোদ", "ভোদা", "চোদা", "খানকি", "মাগী", "শালা", "কুত্তা", "বেজন্মা", "হারামজাদা"
]

# গ্লোবাল ভেরিয়েবল
bot_active = True
groups = {}
warnings = {}
remove_history = {}
alert_log = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= হেল্পার =================
def is_controller(user_id): return user_id in CONTROLLER_IDS

def contains_bad_word(text):
    if not text: return False
    return any(re.search(r'\b' + re.escape(w) + r'\b', text.lower()) for w in BAD_WORDS)

def clean_expired_alerts():
    now = datetime.now()
    for cid in list(alert_log):
        for uid in list(alert_log[cid]):
            name, cnt, ft = alert_log[cid][uid]
            if now - ft > timedelta(hours=24):
                del alert_log[cid][uid]

# ================= অ্যাডমিন প্যানেল =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_controller(update.effective_user.id):
        await update.message.reply_text("⛔ অনুমোদিত নন।")
        return
    kb = [
        [InlineKeyboardButton("1. 📋 গ্রুপ লিস্ট", callback_data="menu_groups")],
        [InlineKeyboardButton("2. 🗑️ রিমুভ হিস্টোরি", callback_data="menu_history")],
        [InlineKeyboardButton("3. ➕ অ্যাড গ্রুপ", callback_data="menu_addgroup")],
        [InlineKeyboardButton("4. 📢 নোটিস", callback_data="menu_notice")],
        [InlineKeyboardButton("5. 🚨 অ্যালার্ট", callback_data="menu_alerts")],
        [InlineKeyboardButton("6. 🔘 বট অন/অফ", callback_data="menu_toggle")],
    ]
    await update.message.reply_text("🦅 **RED'X GUARD কন্ট্রোল প্যানেল**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def panel_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    q = update.callback_query
    await q.answer()
    if not is_controller(q.from_user.id):
        await q.edit_message_text("⛔ অনুমোদিত নন।"); return
    d = q.data

    if d == "menu_groups":
        if not groups: await q.edit_message_text("📭 কোনো গ্রুপ নেই।"); return
        btns = [[InlineKeyboardButton(f"❌ {n} থেকে বের হন", callback_data=f"leave_{c}")] for c, n in groups.items()]
        btns.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_main")])
        txt = "📋 **গ্রুপ লিস্ট:**\n\n" + "\n".join([f"• {n} (`{c}`)" for c, n in groups.items()])
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(btns), parse_mode="Markdown")

    elif d == "menu_history":
        if not groups: await q.edit_message_text("📭 কোনো গ্রুপ নেই।"); return
        btns = [[InlineKeyboardButton(n, callback_data=f"hist_{c}")] for c, n in groups.items()]
        btns.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_main")])
        await q.edit_message_text("🗑️ কোন গ্রুপের হিস্টোরি?", reply_markup=InlineKeyboardMarkup(btns))

    elif d == "menu_notice":
        if not groups: await q.edit_message_text("📭 কোনো গ্রুপ নেই।"); return
        btns = [[InlineKeyboardButton(n, callback_data=f"notice_{c}")] for c, n in groups.items()]
        btns.append([InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_main")])
        await q.edit_message_text("📢 কোন গ্রুপে নোটিশ?", reply_markup=InlineKeyboardMarkup(btns))

    elif d == "menu_alerts":
        clean_expired_alerts()
        txt = "🚨 **২৪ ঘন্টার অ্যালার্ট:**\n\n"
        found = False
        for c, us in alert_log.items():
            for u, (n, cnt, _) in us.items():
                txt += f"• {n} ({groups.get(c, c)}) - {cnt} বার\n"; found = True
        if not found: txt += "✅ কোনো অ্যালার্ট নেই।"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_main")]]), parse_mode="Markdown")

    elif d == "menu_toggle":
        st = "✅ অন" if bot_active else "❌ অফ"
        btns = [[InlineKeyboardButton("🟢 অন", callback_data="set_on"), InlineKeyboardButton("🔴 অফ", callback_data="set_off")],
                [InlineKeyboardButton("🔙 ফিরে যান", callback_data="back_main")]]
        await q.edit_message_text(f"🔘 অবস্থা: **{st}**", reply_markup=InlineKeyboardMarkup(btns), parse_mode="Markdown")

    elif d == "set_on":
        bot_active = True
        await q.edit_message_text("✅ চালু হয়েছে।")
    elif d == "set_off":
        bot_active = False
        await q.edit_message_text("❌ বন্ধ হয়েছে।")

    elif d.startswith("leave_"):
        cid = int(d.split("_")[1])
        try:
            await context.bot.leave_chat(cid); groups.pop(cid, None)
            await q.edit_message_text("✅ বের হয়েছেন।")
        except Exception as e: await q.edit_message_text(f"❌ {e}")

    elif d.startswith("hist_"):
        cid = int(d.split("_")[1])
        h = remove_history.get(cid, [])
        if not h: txt = "📭 হিস্টোরি নেই।"
        else:
            txt = f"🗑️ **{groups.get(cid, cid)}:**\n\n" + "\n".join([f"• {n} | {r} | {t}" for n, r, t in h[-20:]])
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="back_main")]]), parse_mode="Markdown")

    elif d.startswith("notice_"):
        context.user_data['notice_chat'] = int(d.split("_")[1])
        context.user_data['awaiting_notice'] = True
        await q.edit_message_text("📝 নোটিশ লিখুন:")

    elif d == "back_main":
        await start(update, context)

# ================= মেসেজ লজিক =================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_active
    if not bot_active or not update.message: return
    chat, user, msg = update.effective_chat, update.effective_user, update.message

    if chat.type in ["group", "supergroup", "channel"] and chat.id not in groups:
        groups[chat.id] = chat.title or str(chat.id)

    try:
        m = await chat.get_member(user.id)
        is_admin = m.status in ["administrator", "creator"]
    except: is_admin = False
    if is_admin or is_controller(user.id): return

    if msg.text and contains_bad_word(msg.text):
        await punish(update, context, "গালাগালি", chat.id, user); return

    if (msg.photo or msg.video or msg.animation) and msg.caption and contains_bad_word(msg.caption):
        await punish(update, context, "১৮+ কন্টেন্ট", chat.id, user); return

    if context.user_data.get('awaiting_notice') and is_controller(user.id):
        tc = context.user_data.get('notice_chat')
        if tc:
            try:
                await context.bot.send_message(tc, msg.text)
                await msg.reply_text("✅ পাঠানো হয়েছে।")
            except Exception as e: await msg.reply_text(f"❌ {e}")
        context.user_data['awaiting_notice'] = False

async def punish(update, context, reason, cid, user):
    try: await update.message.delete()
    except: pass
    key = (cid, user.id); warnings[key] = warnings.get(key, 0) + 1
    cnt = warnings[key]; name = user.full_name or user.username or "User"

    if cid not in alert_log: alert_log[cid] = {}
    if user.id not in alert_log[cid]: alert_log[cid][user.id] = (name, 1, datetime.now())
    else:
        old = alert_log[cid][user.id]; alert_log[cid][user.id] = (name, old[1] + 1, old[2])

    if cid not in remove_history: remove_history[cid] = []
    remove_history[cid].append((name, reason, datetime.now().strftime("%Y-%m-%d %H:%M")))

    await context.bot.send_message(cid, f"{name} ভদ্র ভাষায় কথা বলুন\nDEVELOPER BY RED TEAM BD 🦅\n\"সর্বদা সর্বোচ্চ দেশের তরে আমরা\"")

    if cnt >= 3:
        try:
            await context.bot.ban_chat_member(cid, user.id)
            warnings.pop(key, None)
            await context.bot.send_message(cid, f"🚫 {name} কে ৩ বার নিয়ম ভাঙার জন্য ব্যান করা হয়েছে।")
        except Exception as e: logger.error(f"Ban failed: {e}")

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for m in update.message.new_chat_members:
        if m.id == context.bot.id:
            msg = (
                "আসসালামু আলাইকুম\nRED TEAM BANGLADESH SECURITY OPERATION 🦅\n"
                "এর পক্ষ থেকে সবাইকে শুভেচ্ছা ও অভিনন্দন\n"
                "আপনাদের গ্রুপ বা চ্যানেল সুন্দরভাবে পরিচালনার জন্য \"RED'X GUARD\" অ্যাড করার জন্য অসংখ্য ধন্যবাদ\n\n"
                "সকলে গ্রুপের রুলস মেনে চলবেন\nধন্যবাদ\n"
                "DEVELOPER BY RED TEAM BD 🦅\n\"সর্বদা সর্বোচ্চ দেশের তরে আমরা\""
            )
            await update.message.reply_text(msg)
            groups[update.effective_chat.id] = update.effective_chat.title or str(update.effective_chat.id)

# ================= মেইন =================
if __name__ == "__main__":
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(panel_buttons))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    # রেন্ডারে ওয়েবহুক চালু করা (পোলিং এর দরকার নেই, তাই Conflict হবে না)
    logger.info("🦅 RED'X GUARD Webhook সার্ভার চালু হচ্ছে...")
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="/webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook",
        drop_pending_updates=True
        )
    await application.initialize()
    await application.bot.set_webhook(f"{WEBHOOK_URL}/{BOT_TOKEN}")
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_post(f"/{BOT_TOKEN}", webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🦅 Webhook সার্ভার চালু: পোর্ট {PORT}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
