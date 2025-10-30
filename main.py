import os
import re
import time
import docker
import threading
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import ReplyKeyboardMarkup, KeyboardButton
import pytz

# ================= 时区设置 =================
china_tz = pytz.timezone('Asia/Shanghai')

# ================= 环境变量 =================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID"))
DOCKER_SOCKET_PATH = os.getenv("DOCKER_SOCKET_PATH", "/var/run/docker.sock")

# ================= 获取中国时间 =================
def get_china_time():
    return datetime.now(china_tz).strftime('%Y-%m-%d %H:%M:%S')

# ================= 发送 Telegram 消息 =================
def send_telegram_message(message, use_markdown=False):
    try:
        print(f"📤 准备发送消息，消息长度: {len(message)}")
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": ALLOWED_CHAT_ID, "text": message}
        if use_markdown:
            payload["parse_mode"] = "Markdown"
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            print("✅ 消息发送成功")
            return True
        else:
            print(f"❌ 消息发送失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 发送消息异常: {e}")
        return False

# ================= 检查 Docker 服务是否就绪 =================
def wait_for_docker_ready():
    max_retries = 10
    for i in range(max_retries):
        try:
            client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
            client.ping()
            print(f"✅ Docker 服务已就绪 (尝试 {i+1}/{max_retries})")
            return client
        except Exception as e:
            print(f"🔄 等待 Docker 服务... (尝试 {i+1}/{max_retries}) - {e}")
            time.sleep(3)
    raise Exception("Docker 服务未就绪")

# ================= 生成容器状态报告 =================
def generate_container_status_report(client):
    try:
        containers = client.containers.list(all=True)
        if not containers:
            return "🟡 未发现任何容器。"

        running, stopped = [], []
        for c in containers:
            img = c.image.tags[0] if c.image.tags else c.image.short_id
            line = f"- 容器名称：{c.name}\n  镜像：{img}\n  状态：{'🟢 已启动' if c.status == 'running' else '🛑 已停止'}"
            if c.status == "running":
                running.append(line)
            else:
                stopped.append(line)

        msg = "📊 容器状态报告\n---\n"
        msg += f"🔍 总容器数：{len(containers)}\n"
        msg += f"🟢 运行中：{len(running)}\n"
        msg += f"🛑 已停止：{len(stopped)}\n\n"
        if running: msg += "✅ 运行中容器：\n" + "\n".join(running) + "\n\n"
        if stopped: msg += "⚠️ 已停止容器：\n" + "\n".join(stopped)
        return msg
    except Exception as e:
        return f"❌ 生成报告失败：{e}"

# ================= 发送启动通知 =================
def send_startup_notification():
    try:
        print("🔄 开始发送启动通知流程...")
        if not BOT_TOKEN or not ALLOWED_CHAT_ID:
            print("❌ 环境变量未设置")
            return
        print("✅ 环境变量已就绪")
        client = wait_for_docker_ready()
        print("🕒 等待容器完全启动...")
        for i in range(1, 6):
            print(f"等待中... {i * 5} 秒")
            time.sleep(5)
            try:
                containers = client.containers.list(filters={"status": "running"})
                if len(containers) >= 2:
                    print(f"✅ 检测到 {len(containers)} 个运行中容器")
                    break
            except:
                pass
        status_report = generate_container_status_report(client)
        startup_time = get_china_time()
        message = f"🚀 Docker 服务启动完成\n\n{status_report}\n⏰ 启动时间：{startup_time}"
        print("📤 发送通知...")
        if send_telegram_message(message, use_markdown=False):
            print("🎉 启动通知发送成功！")
        else:
            print("❌ 启动通知发送失败")
    except Exception as e:
        print(f"💥 发送启动通知失败：{e}")

# ================= 命令按钮 =================
def get_command_keyboard():
    keyboard = [
        [KeyboardButton("/status"), KeyboardButton("/allcontainers")],
        [KeyboardButton("/runonce"), KeyboardButton("/logs")],
        [KeyboardButton("/cleanup"), KeyboardButton("/help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

# ================= 权限检查 =================
async def check_permission(update: Update):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        await update.message.reply_text("🚫 没有权限使用此机器人。")
        return False
    return True

# ================= /help =================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    msg = (
        "🤖 Watchtower 控制命令\n\n"
        "/status - 查看运行中容器\n"
        "/allcontainers - 查看所有容器状态\n"
        "/runonce - 立即执行一次性更新检查\n"
        "/restart <容器名> - 重启指定容器\n"
        "/logs - 查看 Watchtower 日志\n"
        "/cleanup - 执行镜像清理并生成报告\n"
        "/help - 查看帮助"
    )
    await update.message.reply_text(msg, reply_markup=get_command_keyboard())

# ================= /start =================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    msg = (
        "🚀 欢迎使用 Watchtower 控制机器人\n\n"
        "📊 /status - 查看运行中容器\n"
        "📋 /allcontainers - 查看所有容器状态\n"
        "🔄 /runonce - 立即执行更新检查\n"
        "♻️ /restart - 重启指定容器\n"
        "📝 /logs - 查看 Watchtower 日志\n"
        "🧹 /cleanup - 执行镜像清理\n"
        "❓ /help - 查看帮助信息"
    )
    await update.message.reply_text(msg, reply_markup=get_command_keyboard())

# ================= /status =================
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    try:
        client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
        containers = client.containers.list()
        if not containers:
            await update.message.reply_text("🟡 当前没有运行中的容器。")
            return
        running = []
        for c in containers:
            img = c.image.tags[0] if c.image.tags else c.image.short_id
            running.append(f"- 容器名称：{c.name}\n  镜像：{img}\n  状态：🟢 已启动")
        msg = "📊 容器状态报告\n---\n"
        msg += f"🔍 总容器数：{len(containers)}\n🟢 运行中：{len(running)}\n🛑 已停止：0\n\n"
        msg += "✅ 运行中容器：\n" + "\n".join(running)
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ 获取状态失败：{e}")

# ================= /allcontainers =================
async def allcontainers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    try:
        client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
        containers = client.containers.list(all=True)
        if not containers:
            await update.message.reply_text("🟡 未发现任何容器。")
            return
        running, stopped = [], []
        for c in containers:
            img = c.image.tags[0] if c.image.tags else c.image.short_id
            line = f"- 容器名称：{c.name}\n  镜像：{img}\n  状态：{'🟢 已启动' if c.status == 'running' else '🛑 已停止'}"
            if c.status == "running": running.append(line)
            else: stopped.append(line)
        msg = "📊 容器状态报告\n---\n"
        msg += f"🔍 总容器数：{len(containers)}\n🟢 运行中：{len(running)}\n🛑 已停止：{len(stopped)}\n\n"
        if running: msg += "✅ 运行中容器：\n" + "\n".join(running) + "\n\n"
        if stopped: msg += "⚠️ 已停止容器：\n" + "\n".join(stopped)
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ 获取容器列表失败：{e}")

# ================= /restart =================
async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    if not context.args:
        await update.message.reply_text("用法：/restart <容器名>", reply_markup=get_command_keyboard())
        return
    name = context.args[0]
    try:
        client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
        await update.message.reply_text(f"🔄 正在重启容器：{name}...")
        c = client.containers.get(name)
        c.restart()
        time.sleep(2)
        c.reload()
        if c.status == "running":
            await update.message.reply_text(f"✅ 容器重启成功：{name}")
            restart_msg = f"🔄 容器重启通知\n\n📦 容器名称：{name}\n⏰ 重启时间：{get_china_time()}\n✅ 状态：重启完成"
            threading.Thread(target=lambda: send_telegram_message(restart_msg, use_markdown=False), daemon=True).start()
        else:
            await update.message.reply_text(f"⚠️ 容器重启后状态异常：{c.status}")
    except Exception as e:
        await update.message.reply_text(f"❌ 重启失败：{e}")

# ================= /logs =================
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    try:
        client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
        wt = client.containers.get("watchtower")
        raw_logs = wt.logs(tail=30).decode(errors="ignore")
        lines = raw_logs.strip().split("\n")
        formatted = []
        for line in lines:
            ts_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
            ts_fmt = ""
            if ts_match:
                try:
                    dt = datetime.fromisoformat(ts_match.group(1))
                    ts_fmt = dt.astimezone(china_tz).strftime("%m-%d %H:%M")
                except:
                    ts_fmt = ts_match.group(1)
            line = line.replace("Found new image", "发现新镜像")\
                       .replace("Stopping container", "停止容器")\
                       .replace("Removing image", "删除旧镜像")\
                       .replace("Starting container", "启动容器")\
                       .replace("No new images found", "未发现新镜像")\
                       .replace("Removing unused images", "清理未使用镜像")
            formatted.append(f"🕒 {ts_fmt} | {line}")
        msg = "\n".join(formatted[-20:])
        await update.message.reply_text(f"🧾 Watchtower 最新日志：\n\n{msg}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ 获取日志失败：{e}")

# ================= /runonce =================
async def runonce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    await update.message.reply_text("🔄 正在执行一次性更新检查，请稍候…")
    image_name = "containrrr/watchtower:latest"
    tmp_name = "watchtower-runonce-temp"
    try:
        client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
        try:
            old = client.containers.get(tmp_name)
            old.remove(force=True)
        except docker.errors.NotFound:
            pass
        container = client.containers.run(
            image_name,
            command=["--run-once", "--cleanup"],
            entrypoint="/watchtower",
            volumes={"/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}},
            environment={
                "TZ": "Asia/Shanghai",
                "WATCHTOWER_NOTIFICATIONS": "shoutrrr",
                "WATCHTOWER_NOTIFICATION_REPORT": "true",
                "WATCHTOWER_NOTIFICATION_URL": f"telegram://{BOT_TOKEN}@telegram/?chats={ALLOWED_CHAT_ID}"
            },
            remove=True,
            detach=True,
            name=tmp_name
        )
        start = time.time()
        while True:
            container.reload()
            if container.status in ("exited", "dead"): break
            if time.time() - start > 120:
                container.stop(timeout=3)
                break
            time.sleep(1)
        await update.message.reply_text("✅ 一次性更新完成。")
    except Exception as e:
        await update.message.reply_text(f"❌ 执行一次性更新失败：{e}")

# ================= /cleanup =================
async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    await update.message.reply_text("🧹 正在执行镜像清理，请稍候…")
    try:
        client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
        result = client.images.prune(filters={"dangling": False})
        removed = result.get('ImagesDeleted', [])
        space = result.get('SpaceReclaimed', 0)
        report = "🧹 镜像清理报告\n---\n"
        report += f"🗑️ 删除无用镜像：{len(removed)} 个\n💾 释放空间：{space / 1024 / 1024:.2f} MB\n"
        await update.message.reply_text(report)
    except Exception as e:
        await update.message.reply_text(f"❌ 镜像清理失败：{e}")

# ================= 主程序启动 =================
def main():
    print("🔄 正在启动 Watchtower 控制 Bot...")
    threading.Thread(target=lambda: (time.sleep(10), send_startup_notification()), daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("allcontainers", allcontainers_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CommandHandler("logs", logs_command))
    app.add_handler(CommandHandler("runonce", runonce_command))
    app.add_handler(CommandHandler("cleanup", cleanup_command))
    print("✅ Watchtower 控制 Bot 已启动")
    app.run_polling()

if __name__ == "__main__":
    main()
