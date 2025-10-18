import os
import re
import time
import docker
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================= 环境变量 =================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID"))
DOCKER_SOCKET_PATH = os.getenv("DOCKER_SOCKET_PATH", "/var/run/docker.sock")

client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")

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
        "🤖 **Watchtower 控制命令**\n\n"
        "/status - 查看运行中容器\n"
        "/allcontainers - 查看所有容器状态\n"
        "/runonce - 立即执行一次性更新检查\n"
        "/restart <容器名> - 重启指定容器\n"
        "/logs - 查看 Watchtower 日志（中文格式）\n"
        "/help - 查看帮助"
    )
    await update.message.reply_text(msg)

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

    msg = "📊 **容器状态报告**\n---\n"
    msg += f"🔍 总容器数：{len(containers)}\n"
    msg += f"🟢 运行中：{len(running)}\n"
    msg += f"🛑 已停止：0\n\n"

    if running:
        msg += "✅ **运行中容器：**\n" + "\n".join(running)

    await update.message.reply_text(msg)

# ================= /allcontainers =================
async def allcontainers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
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

    msg = "📊 **容器状态报告**\n---\n"
    msg += f"🔍 总容器数：{len(containers)}\n"
    msg += f"🟢 运行中：{len(running)}\n"
    msg += f"🛑 已停止：{len(stopped)}\n\n"

    if running:
        msg += "✅ **运行中容器：**\n" + "\n".join(running) + "\n\n"
    if stopped:
        msg += "⚠️ **已停止容器：**\n" + "\n".join(stopped)

    await update.message.reply_text(msg)

# ================= /restart =================
async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    if not context.args:
        await update.message.reply_text("用法：/restart <容器名>")
        return
    name = context.args[0]
    try:
        c = client.containers.get(name)
        c.restart()
        await update.message.reply_text(f"♻️ 已重启容器：{name}")
    except Exception as e:
        await update.message.reply_text(f"❌ 重启失败：{e}")

# ================= /logs =================
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    try:
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
                    ts_fmt = dt.strftime("%m-%d %H:%M")
                except:
                    ts_fmt = ts_match.group(1)
            line = (line
                    .replace("Found new image", "发现新镜像")
                    .replace("Stopping container", "停止容器")
                    .replace("Removing image", "删除旧镜像")
                    .replace("Starting container", "启动容器")
                    .replace("No new images found", "未发现新镜像"))
            formatted.append(f"🕒 {ts_fmt} | {line}")
        msg = "\n".join(formatted[-20:])
        await update.message.reply_text(f"🧾 **Watchtower 最新日志：**\n\n{msg}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ 获取日志失败：{e}")

# ================= /runonce =================
async def runonce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """执行一次性更新检查（--run-once）"""
    if not await check_permission(update): return
    await update.message.reply_text("🔄 正在执行一次性更新检查，请稍候…")

    image_name = "containrrr/watchtower:latest"
    tmp_name = "watchtower-runonce-temp"

    try:
        # 清理旧容器
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
                "WATCHTOWER_NOTIFICATION_URL": f"telegram://{BOT_TOKEN}@telegram/?chats={ALLOWED_CHAT_ID}",
                "WATCHTOWER_NOTIFICATION_TEMPLATE": """{{- with .Report -}}
📊 **容器更新报告**
---
🔍 扫描总数：{{len .Scanned}}
✔️ 成功更新：{{len .Updated}}
⚠️ 跳过更新：{{len .Skipped}}
❌ 更新失败：{{len .Failed}}
{{- if .Updated }}
✳️ **已更新容器：**
{{- range .Updated }}
- 容器名称：{{.Name}}
  镜像：{{.ImageName}}
  旧版本 ID：{{.CurrentImageID.ShortID}}
  新版本 ID：{{.LatestImageID.ShortID}}
{{- end }}
{{- end }}
{{- if .Failed }}
🛑 **更新失败的容器：**
{{- range .Failed }}
- 容器名称：{{.Name}}
  错误信息：{{.Error}}
{{- end }}
{{- end }}
{{- end -}}"""
            },
            remove=True,
            detach=True,
            name=tmp_name
        )

        # 等待容器完成
        timeout = 120
        start = time.time()
        while True:
            container.reload()
            if container.status in ("exited", "dead"):
                break
            if time.time() - start > timeout:
                container.stop(timeout=3)
                break
            time.sleep(1)

        logs = container.logs().decode(errors="ignore")[-3000:]
        if logs.strip():
            await update.message.reply_text(f"✅ 一次性更新完成，以下为运行日志：\n```\n{logs}\n```", parse_mode="MarkdownV2")
        else:
            await update.message.reply_text("✅ 一次性更新完成，未产生输出。通知已发送 Telegram。")

    except Exception as e:
        await update.message.reply_text(f"❌ 执行一次性更新失败：{e}")

# ================= 主程序启动 =================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("start", help_command))
app.add_handler(CommandHandler("status", status_command))
app.add_handler(CommandHandler("allcontainers", allcontainers_command))
app.add_handler(CommandHandler("restart", restart_command))
app.add_handler(CommandHandler("logs", logs_command))
app.add_handler(CommandHandler("runonce", runonce_command))

if __name__ == "__main__":
    print("✅ Watchtower 控制 Bot 已启动")
    app.run_polling()
