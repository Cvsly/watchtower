@@ -2,25 +2,156 @@
import re
import time
import docker
import threading
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import ReplyKeyboardMarkup, KeyboardButton

# ================= 时区设置 =================
import pytz
china_tz = pytz.timezone('Asia/Shanghai')

# ================= 环境变量 =================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID"))
DOCKER_SOCKET_PATH = os.getenv("DOCKER_SOCKET_PATH", "/var/run/docker.sock")

client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
# ================= 获取中国时间 =================
def get_china_time():
    """获取中国时区的时间"""
    return datetime.now(china_tz).strftime('%Y-%m-%d %H:%M:%S')

# ================= 发送 Telegram 消息 =================
def send_telegram_message(message, use_markdown=False):
    """发送 Telegram 消息"""
    try:
        print(f"📤 准备发送消息，消息长度: {len(message)}")
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": ALLOWED_CHAT_ID,
            "text": message
        }
        # 只在明确要求时使用 Markdown
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
    """等待 Docker 服务完全就绪"""
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
    """生成容器状态报告"""
    try:
        containers = client.containers.list(all=True)
        if not containers:
            return "🟡 未发现任何容器。"

        running = []
        stopped = []
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
    """发送系统启动通知"""
    try:
        print("🔄 开始发送启动通知流程...")
        
        # 1. 等待环境变量就绪
        if not BOT_TOKEN or not ALLOWED_CHAT_ID:
            print("❌ 环境变量未设置")
            return
            
        print("✅ 环境变量已就绪")
        
        # 2. 等待 Docker 服务就绪
        client = wait_for_docker_ready()
        
        # 3. 等待更长时间确保所有容器启动
        print("🕒 等待容器完全启动...")
        for i in range(1, 6):
            print(f"等待中... {i * 5} 秒")
            time.sleep(5)
            
            # 检查关键容器是否就绪
            try:
                containers = client.containers.list(filters={"status": "running"})
                if len(containers) >= 2:  # 至少要有 watchtower 和 bot 自己
                    print(f"✅ 检测到 {len(containers)} 个运行中容器")
                    break
            except:
                pass
        
        # 4. 生成容器状态报告
        print("📊 生成容器状态报告...")
        status_report = generate_container_status_report(client)
        
        # 5. 构建完整消息 - 使用纯文本格式
        startup_time = get_china_time()  # 使用中国时间
        message = f"🚀 Docker 服务启动完成\n\n{status_report}\n⏰ 启动时间：{startup_time}"

        # 6. 发送通知 - 不使用 Markdown
        print("📤 发送通知...")
        if send_telegram_message(message, use_markdown=False):
            print("🎉 启动通知发送成功！")
        else:
            print("❌ 启动通知发送失败")
        
    except Exception as e:
        print(f"💥 发送启动通知失败：{e}")

# ================= 命令按钮 =================
def get_command_keyboard():
    """生成命令按钮键盘"""
    keyboard = [
        [KeyboardButton("/status"), KeyboardButton("/allcontainers")],
        [KeyboardButton("/runonce"), KeyboardButton("/logs")],
        [KeyboardButton("/help")]
        [KeyboardButton("/cleanup"), KeyboardButton("/help")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

@@ -35,12 +166,13 @@ async def check_permission(update: Update):
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    msg = (
        "🤖 **Watchtower 控制命令**\n\n"
        "🤖 Watchtower 控制命令\n\n"
        "/status - 查看运行中容器\n"
        "/allcontainers - 查看所有容器状态\n"
        "/runonce - 立即执行一次性更新检查\n"
        "/restart <容器名> - 重启指定容器\n"
        "/logs - 查看 Watchtower 日志（中文格式）\n"
        "/logs - 查看 Watchtower 日志\n"
        "/cleanup - 执行镜像清理并生成报告\n"
        "/help - 查看帮助"
    )
    await update.message.reply_text(msg, reply_markup=get_command_keyboard())
@@ -49,71 +181,79 @@ async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    welcome_msg = (
        "🚀 **欢迎使用 Watchtower 控制机器人**\n\n"
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
    containers = client.containers.list()
    if not containers:
        await update.message.reply_text("🟡 当前没有运行中的容器。")
        return
    
    # 按照 /allcontainers 的格式输出
    running = []
    for c in containers:
        img = c.image.tags[0] if c.image.tags else c.image.short_id
        line = f"- 容器名称：{c.name}\n  镜像：{img}\n  状态：🟢 已启动"
        running.append(line)
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

    msg = "📊 **容器状态报告**\n---\n"
    msg += f"🔍 总容器数：{len(containers)}\n"
    msg += f"🟢 运行中：{len(running)}\n"
    msg += f"🛑 已停止：0\n\n"
        msg = "📊 容器状态报告\n---\n"
        msg += f"🔍 总容器数：{len(containers)}\n"
        msg += f"🟢 运行中：{len(running)}\n"
        msg += f"🛑 已停止：0\n\n"

    if running:
        msg += "✅ **运行中容器：**\n" + "\n".join(running)
        if running:
            msg += "✅ 运行中容器：\n" + "\n".join(running)

    await update.message.reply_text(msg)
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ 获取状态失败：{e}")

# ================= /allcontainers =================
async def allcontainers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    containers = client.containers.list(all=True)
    if not containers:
        await update.message.reply_text("🟡 未发现任何容器。")
        return
    try:
        client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
        containers = client.containers.list(all=True)
        if not containers:
            await update.message.reply_text("🟡 未发现任何容器。")
            return

    running = []
    stopped = []
    for c in containers:
        img = c.image.tags[0] if c.image.tags else c.image.short_id
        line = f"- 容器名称：{c.name}\n  镜像：{img}\n  状态：{'🟢 已启动' if c.status == 'running' else '🛑 已停止'}"
        if c.status == "running":
            running.append(line)
        else:
            stopped.append(line)
        running = []
        stopped = []
        for c in containers:
            img = c.image.tags[0] if c.image.tags else c.image.short_id
            line = f"- 容器名称：{c.name}\n  镜像：{img}\n  状态：{'🟢 已启动' if c.status == 'running' else '🛑 已停止'}"
            if c.status == "running":
                running.append(line)
            else:
                stopped.append(line)

    msg = "📊 **容器状态报告**\n---\n"
    msg += f"🔍 总容器数：{len(containers)}\n"
    msg += f"🟢 运行中：{len(running)}\n"
    msg += f"🛑 已停止：{len(stopped)}\n\n"
        msg = "📊 容器状态报告\n---\n"
        msg += f"🔍 总容器数：{len(containers)}\n"
        msg += f"🟢 运行中：{len(running)}\n"
        msg += f"🛑 已停止：{len(stopped)}\n\n"

    if running:
        msg += "✅ **运行中容器：**\n" + "\n".join(running) + "\n\n"
    if stopped:
        msg += "⚠️ **已停止容器：**\n" + "\n".join(stopped)
        if running:
            msg += "✅ 运行中容器：\n" + "\n".join(running) + "\n\n"
        if stopped:
            msg += "⚠️ 已停止容器：\n" + "\n".join(stopped)

    await update.message.reply_text(msg)
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ 获取容器列表失败：{e}")

# ================= /restart =================
async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
@@ -123,16 +263,29 @@ async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        return
    name = context.args[0]
    try:
        client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
        await update.message.reply_text(f"🔄 正在重启容器：{name}...")
        c = client.containers.get(name)
        c.restart()
        await update.message.reply_text(f"♻️ 已重启容器：{name}")
        
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
        error_msg = f"❌ 重启失败：{e}"
        await update.message.reply_text(error_msg)

# ================= /logs =================
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    try:
        client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
        wt = client.containers.get("watchtower")
        raw_logs = wt.logs(tail=30).decode(errors="ignore")
        lines = raw_logs.strip().split("\n")
@@ -143,18 +296,21 @@ async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if ts_match:
                try:
                    dt = datetime.fromisoformat(ts_match.group(1))
                    ts_fmt = dt.strftime("%m-%d %H:%M")
                    dt_china = dt.astimezone(china_tz)  # 转换为中国时区
                    ts_fmt = dt_china.strftime("%m-%d %H:%M")
                except:
                    ts_fmt = ts_match.group(1)
            line = (line
                    .replace("Found new image", "发现新镜像")
                    .replace("Stopping container", "停止容器")
                    .replace("Removing image", "删除旧镜像")
                    .replace("Starting container", "启动容器")
                    .replace("No new images found", "未发现新镜像"))
                    .replace("No new images found", "未发现新镜像")
                    .replace("Removing unused images", "清理未使用镜像")
                    .replace("Cleaning up unused images", "清理未使用镜像"))
            formatted.append(f"🕒 {ts_fmt} | {line}")
        msg = "\n".join(formatted[-20:])
        await update.message.reply_text(f"🧾 **Watchtower 最新日志：**\n\n{msg}")
        await update.message.reply_text(f"🧾 Watchtower 最新日志：\n\n{msg}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ 获取日志失败：{e}")

@@ -168,6 +324,7 @@ async def runonce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tmp_name = "watchtower-runonce-temp"

    try:
        client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
        # 清理旧容器
        try:
            old = client.containers.get(tmp_name)
@@ -186,14 +343,14 @@ async def runonce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
                "WATCHTOWER_NOTIFICATION_REPORT": "true",
                "WATCHTOWER_NOTIFICATION_URL": f"telegram://{BOT_TOKEN}@telegram/?chats={ALLOWED_CHAT_ID}",
                "WATCHTOWER_NOTIFICATION_TEMPLATE": """{{- with .Report -}}
📊 **容器更新报告**
📊 容器更新报告
---
🔍 扫描总数：{{len .Scanned}}
✔️ 成功更新：{{len .Updated}}
⚠️ 跳过更新：{{len .Skipped}}
❌ 更新失败：{{len .Failed}}
{{- if .Updated }}
✳️ **已更新容器：**
✳️ 已更新容器：
{{- range .Updated }}
- 容器名称：{{.Name}}
  镜像：{{.ImageName}}
@@ -202,7 +359,7 @@ async def runonce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
{{- end }}
{{- end }}
{{- if .Failed }}
🛑 **更新失败的容器：**
🛑 更新失败的容器：
{{- range .Failed }}
- 容器名称：{{.Name}}
  错误信息：{{.Error}}
@@ -215,12 +372,10 @@ async def runonce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            name=tmp_name
        )

        # 等待容器完成
        timeout = 120
        start = time.time()

        try:
            # 等待容器完成，不捕获日志
            while True:
                container.reload()
                if container.status in ("exited", "dead"):
@@ -230,31 +385,82 @@ async def runonce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
                    break
                time.sleep(1)
        except docker.errors.NotFound:
            # 容器已被自动移除，这是正常情况
            pass

        # 不发送运行日志，只发送完成消息
        await update.message.reply_text("✅ 一次性更新完成。")

    except Exception as e:
        # 过滤掉容器不存在的错误，不发送通知
        error_str = str(e)
        if "No such container" in error_str or "404 Client Error" in error_str:
            await update.message.reply_text("✅ 一次性更新完成。")
        else:
            await update.message.reply_text(f"❌ 执行一次性更新失败：{e}")

# ================= /cleanup =================
async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """执行镜像清理并生成报告"""
    if not await check_permission(update): return
    await update.message.reply_text("🧹 正在执行镜像清理，请稍候…")

    try:
        client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
        result = client.images.prune(filters={"dangling": False})
        
        removed_images = result.get('ImagesDeleted', [])
        space_reclaimed = result.get('SpaceReclaimed', 0)
        
        actual_removed = len([img for img in removed_images if img])
        
        report = "🧹 镜像清理报告\n---\n"
        report += f"🗑️ 删除无用镜像：{actual_removed} 个\n"
        report += f"💾 释放磁盘空间：{space_reclaimed / 1024 / 1024:.2f} MB\n"
        
        if actual_removed > 0:
            report += "\n📋 已删除的镜像：\n"
            for img in removed_images:
                if img and 'Deleted' in img:
                    image_id = img.get('Deleted', '').split(':')[1][:12] if ':' in img.get('Deleted', '') else img.get('Deleted', '')[:12]
                    report += f"- 镜像ID: {image_id}\n"
        else:
            report += "\n✅ 没有需要清理的镜像，系统状态良好。"
        
        await update.message.reply_text(report)

    except Exception as e:
        await update.message.reply_text(f"❌ 镜像清理失败：{e}")

# ================= 主程序启动 =================
app = ApplicationBuilder().token(BOT_TOKEN).build()
def main():
    """主程序"""
    print("🔄 正在启动 Watchtower 控制 Bot...")
    
    # 延迟启动通知线程，确保环境就绪
    def delayed_startup():
        time.sleep(10)  # 等待10秒确保环境完全就绪
        send_startup_notification()
    
    startup_thread = threading.Thread(target=delayed_startup)
    startup_thread.daemon = True
    startup_thread.start()
    
    # 创建应用
    app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("status", status_command))
app.add_handler(CommandHandler("allcontainers", allcontainers_command))
app.add_handler(CommandHandler("restart", restart_command))
app.add_handler(CommandHandler("logs", logs_command))
app.add_handler(CommandHandler("runonce", runonce_command))
    # 添加命令处理器
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("allcontainers", allcontainers_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CommandHandler("logs", logs_command))
    app.add_handler(CommandHandler("runonce", runonce_command))
    app.add_handler(CommandHandler("cleanup", cleanup_command))

if __name__ == "__main__":
    print("✅ Watchtower 控制 Bot 已启动")
    print("🔄 开始轮询...")
    
    # 启动 bot
    app.run_polling()

if __name__ == "__main__":
    main()
