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
        if running:
            msg += "✅ 运行中容器：\n" + "\n".join(running) + "\n\n"
        if stopped:
            msg += "⚠️ 已停止容器：\n" + "\n".join(stopped)
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

# ================= 按钮菜单 =================
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
    welcome_msg = (
        "🚀 欢迎使用 Watchtower 控制机器人\n\n"
        "使用下方按钮或输入命令来管理您的容器：\n\n"
        "📊 /status - 查看运行中容器\n"
        "📋 /allcontainers - 查看所有容器状态\n"
        "🔄 /runonce - 立即执行更新检查\n"
        "♻️ /restart - 重启指定容器\n"
        "📝 /logs - 查看 Watchtower 日志\n"
        "🧹 /cleanup - 执行镜像清理\n"
        "❓ /help - 查看帮助信息"
    )
    await update.message.reply_text(welcome_msg, reply_markup=get_command_keyboard())

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
            line = f"- 容器名称：{c.name}\n  镜像：{img}\n  状态：🟢 已启动"
            running.append(line)
        msg = "📊 容器状态报告\n---\n"
        msg += f"🔍 总容器数：{len(containers)}\n"
        msg += f"🟢 运行中：{len(running)}\n"
        msg += f"🛑 已停止：0\n\n"
        if running:
            msg += "✅ 运行中容器：\n" + "\n".join(running)
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ 获取状态失败：{e}")

# ================= /cleanup =================
async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    await update.message.reply_text("🧹 正在执行镜像清理，请稍候…")
    try:
        client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
        result = client.images.prune()

        images_deleted = result.get("ImagesDeleted")
        space_reclaimed = result.get("SpaceReclaimed", 0)

        if not images_deleted:
            msg = (
                "🧹 **镜像清理报告**\n"
                "---\n"
                "🗑️ 删除无用镜像：0 个\n"
                f"💾 释放空间：{round(space_reclaimed / (1024**2), 2)} MB"
            )
        else:
            msg = (
                "🧹 **镜像清理报告**\n"
                "---\n"
                f"🗑️ 删除无用镜像：{len(images_deleted)} 个\n"
                f"💾 释放空间：{round(space_reclaimed / (1024**2), 2)} MB"
            )

        # 只保留一条回复消息，删除重复的 send_telegram_message 调用
        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ 镜像清理失败：{e}")

# ================= 主函数 =================
def main():
    print("🔄 正在启动 Watchtower 控制 Bot...")
    def delayed_startup():
        time.sleep(10)
        send_startup_notification()
    threading.Thread(target=delayed_startup, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("cleanup", cleanup_command))

    print("✅ Watchtower 控制 Bot 已启动")
    print("🔄 开始轮询...")
    app.run_polling()

if __name__ == "__main__":
    main()
