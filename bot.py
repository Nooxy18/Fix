import os, json, smtplib, imaplib, email
from email.message import EmailMessage
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ENV
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

# Folder logs, aman di Railway
log_path = "./logs"
try:
    os.makedirs(log_path)
except FileExistsError:
    pass

LOG_FILE = os.path.join(log_path, "bot.log")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass  # aman kalau permission terbatas

# Load config
try:
    with open("config.json", "r") as f:
        config = json.load(f)
except Exception:
    config = {"targets": [], "senders": {}, "premium_users": []}

TARGETS = config.get("targets", [])
senders = config.get("senders", {})
premium_users = set(config.get("premium_users", []))

# Popup Telegram rapi
async def send_email_popup(update, sender, target, subject, body, status, progress):
    msg = (
        f"🟢 SEND EMAIL REPORT\n\n"
        f"⚙️ Sender    : {sender}\n"
        f"📌 Target    : {target}\n"
        f"💎 UserType  : {'Premium' if update.effective_user.id in premium_users else 'Standard'}\n"
        f"📧 Subject   : {subject}\n"
        f"📝 Body      : {body[:40]}{'...' if len(body)>40 else ''}\n\n"
        f"{'✅ SUCCESS' if status else '⚠️ FAILED'} | 📊 {progress}\n"
        f"⏱ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await update.message.reply_text(msg)

# Command /send
async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args)<2:
        await update.message.reply_text("Usage: /send <from_email> <subject> <body>")
        return

    sender = context.args[0]
    subject = context.args[1]
    body = " ".join(context.args[2:])
    target = TARGETS[0] if TARGETS else None

    if target is None:
        await update.message.reply_text("❌ No locked targets configured.")
        return

    if sender not in senders:
        await update.message.reply_text("❌ Sender not found. Use /addsender first.")
        return

    try:
        m = EmailMessage()
        m["From"] = sender
        m["To"] = target
        m["Subject"] = subject
        m.set_content(body)

        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp.login(sender, senders[sender])
        smtp.send_message(m)
        smtp.quit()
        success = True
    except Exception as e:
        log(f"Send failed: {e}")
        success = False

    await send_email_popup(update, sender, target, subject, body, success, "1/1")

# Command /addsender
async def add_sender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args)!=2:
        await update.message.reply_text("Use /addsender <email> <app_password>")
        return
    email_addr = context.args[0]
    app_pass = context.args[1]
    senders[email_addr]=app_pass
    config["senders"]=senders
    try:
        with open("config.json","w") as f:
            json.dump(config,f,indent=2)
    except Exception:
        pass
    await update.message.reply_text(f"✅ Sender {email_addr} added")

# Command /listsenders
async def list_senders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not senders:
        await update.message.reply_text("No senders yet.")
        return
    text = "\n".join(senders.keys())
    await update.message.reply_text("📧 Senders:\n"+text)

# Command /botstatus
async def bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 Status\nSenders: {len(senders)}\nTargets: {len(TARGETS)}\nPremium: {len(premium_users)}"
    )

# IMAP reply checker
async def check_replies():
    import asyncio
    while True:
        for email_addr, app_pass in senders.items():
            try:
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                mail.login(email_addr, app_pass)
                mail.select("inbox")
                status, data = mail.search(None, "UNSEEN")
                for num in data[0].split():
                    typ, msg_data = mail.fetch(num, "(RFC822)")
                    msg = email.message_from_bytes(msg_data[0][1])
                    from_addr = msg.get("From")
                    subject = msg.get("Subject")
                    body_msg = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type()=="text/plain":
                                body_msg=part.get_payload(decode=True).decode()
                                break
                    else:
                        body_msg=msg.get_payload(decode=True).decode()
                    log(f"REPLY FROM {from_addr}: {subject} | {body_msg}")
                mail.logout()
            except Exception as e:
                log(f"Failed checking replies: {e}")
        await asyncio.sleep(60)

# MAIN
def main():
    import asyncio
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("send", send_command))
    app.add_handler(CommandHandler("addsender", add_sender))
    app.add_handler(CommandHandler("listsenders", list_senders))
    app.add_handler(CommandHandler("botstatus", bot_status))

    # Jalankan IMAP reply checker setelah loop jalan
    async def startup(app):
        asyncio.create_task(check_replies())

    app.run_polling(poll_interval=1, timeout=30, stop_signals=None, on_startup=[startup])

if __name__=="__main__":
    main()
