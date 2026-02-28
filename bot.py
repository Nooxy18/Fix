import os, json, smtplib, imaplib, email
from email.message import EmailMessage
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Load ENV
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID","0"))

LOG_FILE = "./logs/bot.log"
os.makedirs("./logs", exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE,"a") as f: f.write(line+"\n")

with open("config.json","r") as f:
    config = json.load(f)

TARGETS = config.get("targets", [])
senders = config.get("senders", {})
premium_users = set(config.get("premium_users", []))

async def send_email_popup(update, sender, target, subject, body, status, progress):
    msg = (
        f"🟢  SEND EMAIL REPORT\n\n"
        f"⚙️ Sender      : {sender}\n"
        f"📌 Target      : {target}\n"
        f"💎 User Type   : {'Premium' if update.effective_user.id in premium_users else 'Standard'}\n"
        f"📧 Subject     : {subject}\n"
        f"📝 Body        : {body[:40]}{'...' if len(body) > 40 else ''}\n\n"
        f"{'✅ SUCCESS' if status else '⚠️ FAILED'}  | 📊 {progress}\n"
        f"⏱ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await update.message.reply_text(msg)

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args)<2:
        await update.message.reply_text("Usage: /send <from_email> <subject> <body>")
        return

    sender = context.args[0]
    subject = context.args[1]
    body=" ".join(context.args[2:])
    target = TARGETS[0] if TARGETS else None

    if target is None:
        await update.message.reply_text("❌ No locked targets configured.")
        return

    if sender not in senders:
        await update.message.reply_text("❌ Sender not found. Use /addsender first.")
        return

    try:
        m=EmailMessage()
        m["From"] = sender
        m["To"] = target
        m["Subject"] = subject
        m.set_content(body)

        smtp = smtplib.SMTP_SSL("smtp.gmail.com",465)
        smtp.login(sender, senders[sender])
        smtp.send_message(m)
        smtp.quit()
        success = True
    except Exception as e:
        log(f"Send failed: {e}")
        success = False

    await send_email_popup(update, sender, target, subject, body, success, "1/1")

async def add_sender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args)!=2:
        await update.message.reply_text("Use /addsender <email> <app_password>")
        return
    email,address_pwd = context.args
    senders[email]=address_pwd
    config["senders"]=senders
    with open("config.json","w") as f: json.dump(config,f, indent=2)
    await update.message.reply_text(f"✅ Sender {email} added")

async def list_senders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not senders:
        await update.message.reply_text("No senders yet.")
        return
    text="\n".join(senders.keys())
    await update.message.reply_text("📧 Senders:\n"+text)

async def bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 Status\nSenders: {len(senders)}\nTargets: {len(TARGETS)}\nPremium: {len(premium_users)}"
    )

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("send", send_command))
    app.add_handler(CommandHandler("addsender", add_sender))
    app.add_handler(CommandHandler("listsenders", list_senders))
    app.add_handler(CommandHandler("botstatus", bot_status))
    app.run_polling(poll_interval=1, timeout=30)

if __name__=="__main__":
    main()