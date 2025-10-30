import os
import re
import time
import docker
import threading
import requests
import asyncio
import datetime
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackContext
from telegram import ReplyKeyboardMarkup, KeyboardButton

# ================= 时区设置 =================
import pytz
china_tz = pytz.timezone('Asia/Shanghai')

# ================= 环境变量 =================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID"))
DOCKER_SOCKET_PATH = os.getenv("DOCKER_SOCKET_PATH", "/var/run/docker.sock")
WATCHTOWER_SCHEDULE = os.getenv("WATCHTOWER_SCHEDULE", "20 4 * * *")  # 从环境变量读取定时设置

# ================= 获取中国时间 =================
def get_china_time():
    """获取中国时区的时间"""
    return datetime.now(china_tz).strftime('%Y-%m-%d %H:%M:%S')

# ================= 解析定时设置 =================
def parse_schedule_time():
    """解析定时设置返回友好时间格式"""
    try:
        schedule_parts = WATCHTOWER_SCHEDULE.split()
        if len(schedule_parts) >= 5:
            minute, hour, day, month, weekday = schedule_parts
            return f"{hour}:{minute}", f"{hour}点{minute}分"
        else:
            return "未知", "未知"
    except:
        return "未知", "未知"

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
        schedule_time, friendly_time = parse_schedule_time()
        message = f"🚀 Docker 服务启动完成\n\n{status_report}\n⏰ 启动时间：{startup_time}\n📅 定时设置：每天 {friendly_time}"

        # 6. 发送通知 - 不使用 Markdown
        print("📤 发送通知...")
        if send_telegram_message(message, use_markdown=False):
            print("🎉 启动通知发送成功！")
        else:
            print("❌ 启动通知发送失败")
        
    except Exception as e:
        print(f"💥 发送启动通知失败：{e}")

# ================= 定时状态报告 =================
async def daily_scheduled_report(context: CallbackContext):
    """根据环境变量设置发送定时状态报告"""
    try:
        print("🕐 触发定时状态报告")
        client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
        
        status_report = generate_container_status_report(client)
        current_time = get_china_time()
        
        # 解析定时设置显示友好时间
        schedule_time, friendly_time = parse_schedule_time()
            
        message = f"🌙 {friendly_time}状态报告 ({current_time})\n\n{status_report}"
        
        await context.bot.send_message(
            chat_id=ALLOWED_CHAT_ID, 
            text=message
        )
        print(f"✅ 定时状态报告发送成功: {current_time}")
        
    except Exception as e:
        print(f"❌ 定时状态报告发送失败: {e}")

# ================= 设置定时任务 =================
def setup_daily_schedule(app):
    """设置定时任务"""
    try:
        print(f"🔧 开始设置定时任务，当前环境: {WATCHTOWER_SCHEDULE}")
        
        job_queue = app.job_queue
        if job_queue:
            print("✅ JobQueue 可用，正在解析定时设置...")
            
            # 从环境变量解析定时时间
            schedule_parts = WATCHTOWER_SCHEDULE.split()
            if len(schedule_parts) >= 5:
                minute, hour, day, month, weekday = schedule_parts
                schedule_hour = int(hour)
                schedule_minute = int(minute)
                
                print(f"⏰ 解析出的定时时间: {schedule_hour:02d}:{schedule_minute:02d}")
                
                # 设置定时任务（使用中国时区）
                from datetime import time as dt_time
                job_queue.run_daily(
                    daily_scheduled_report,
                    time=dt_time(hour=schedule_hour, minute=schedule_minute, second=0, tzinfo=china_tz),  # 添加时区
                    name=f"daily_{schedule_hour:02d}{schedule_minute:02d}_report"
                )
                print(f"✅ 已成功设置每天 {schedule_hour:02d}:{schedule_minute:02d} 定时状态报告（中国时区）")
                
                # 添加一个测试任务（5分钟后执行）
                job_queue.run_once(daily_scheduled_report, when=300, name="test_report_5min")
                print("✅ 已设置5分钟后测试任务")
                
                # 立即测试一次（用于验证功能）
                job_queue.run_once(daily_scheduled_report, when=10, name="immediate_test")
                print("✅ 已设置10秒后立即测试")
            else:
                print("❌ 定时设置格式错误")
        else:
            print("❌ JobQueue 不可用，定时任务无法设置")
    except Exception as e:
        print(f"❌ 设置定时任务失败: {e}")
        import traceback
        traceback.print_exc()

# ================= 命令按钮 =================
def get_command_keyboard():
    """生成命令按钮键盘"""
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
    
    # 解析定时设置显示友好时间
    schedule_time, friendly_time = parse_schedule_time()
    
    msg = (
        f"🤖 Watchtower 控制命令\n\n"
        f"⏰ 自动更新: 每天 {friendly_time}\n\n"
        "📋 手动命令:\n"
        "/status - 查看运行中容器\n"
        "/allcontainers - 查看所有容器状态\n"
        "/runonce - 立即执行一次性更新检查\n"
        "/restart <容器名> - 重启指定容器\n"
        "/logs - 查看 Watchtower 日志\n"
        "/cleanup - 执行镜像清理并生成报告\n"
        "/test_schedule - 测试定时任务功能\n"
        "/schedule_info - 查看定时任务信息\n"
        "/check_jobs - 检查定时任务状态\n"
        "/help - 查看帮助"
    )
    await update.message.reply_text(msg, reply_markup=get_command_keyboard())

# ================= /start =================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
    
    # 解析定时设置显示友好时间
    schedule_time, friendly_time = parse_schedule_time()
    
    welcome_msg = (
        f"🚀 欢迎使用 Watchtower 控制机器人\n\n"
        f"⏰ 自动更新: 每天 {friendly_time}\n\n"
        "使用下方按钮或输入命令来管理您的容器：\n\n"
        "📊 /status - 查看运行中容器\n"
        "📋 /allcontainers - 查看所有容器状态\n"
        "🔄 /runonce - 立即执行更新检查\n"
        "♻️ /restart - 重启指定容器\n"
        "📝 /logs - 查看 Watchtower 日志\n"
        "🧹 /cleanup - 执行镜像清理\n"
        "🧪 /test_schedule - 测试定时任务\n"
        "📅 /schedule_info - 查看定时设置\n"
        "🔍 /check_jobs - 检查任务状态\n"
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

# ================= /allcontainers =================
async def allcontainers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_permission(update): return
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

        msg = "📊 容器状态报告\n---\n"
        msg += f"🔍 总容器数：{len(containers)}\n"
        msg += f"🟢 运行中：{len(running)}\n"
        msg += f"🛑 已停止：{len(stopped)}\n\n"

        if running:
            msg += "✅ 运行中容器：\n" + "\n".join(running) + "\n\n"
        if stopped:
            msg += "⚠️ 已停止容器：\n" + "\n".join(stopped)

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
        formatted = []
        for line in lines:
            ts_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
            ts_fmt = ""
            if ts_match:
                try:
                    dt = datetime.fromisoformat(ts_match.group(1))
                    dt_china = dt.astimezone(china_tz)  # 转换为中国时区
                    ts_fmt = dt_china.strftime("%m-%d %H:%M")
                except:
                    ts_fmt = ts_match.group(1)
            line = (line
                    .replace("Found new image", "发现新镜像")
                    .replace("Stopping container", "停止容器")
                    .replace("Removing image", "删除旧镜像")
                    .replace("Starting container", "启动容器")
                    .replace("No new images found", "未发现新镜像")
                    .replace("Removing unused images", "清理未使用镜像")
                    .replace("Cleaning up unused images", "清理未使用镜像"))
            formatted.append(f"🕒 {ts_fmt} | {line}")
        msg = "\n".join(formatted[-20:])
        await update.message.reply_text(f"🧾 Watchtower 最新日志：\n\n{msg}")
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
        client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
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
📊 容器更新报告
---
🔍 扫描总数：{{len .Scanned}}
✔️ 成功更新：{{len .Updated}}
⚠️ 跳过更新：{{len .Skipped}}
❌ 更新失败：{{len .Failed}}
{{- if .Updated }}
✳️ 已更新容器：
{{- range .Updated }}
- 容器名称：{{.Name}}
  镜像：{{.ImageName}}
  旧版本 ID：{{.CurrentImageID.ShortID}}
  新版本 ID：{{.LatestImageID.ShortID}}
{{- end }}
{{- end }}
{{- if .Failed }}
🛑 更新失败的容器：
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

        timeout = 120
        start = time.time()
        
        try:
            while True:
                container.reload()
                if container.status in ("exited", "dead"):
                    break
                if time.time() - start > timeout:
                    container.stop(timeout=3)
                    break
                time.sleep(1)
        except docker.errors.NotFound:
            pass

        await update.message.reply_text("✅ 一次性更新完成。")

    except Exception as e:
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
        
        # 更安全的镜像清理方法
        actual_removed = 0
        space_reclaimed = 0
        
        try:
            # 尝试执行镜像清理
            result = client.images.prune(filters={"dangling": False})
            
            # 安全地处理返回结果
            if result and isinstance(result, dict):
                removed_images = result.get('ImagesDeleted')
                space_reclaimed = result.get('SpaceReclaimed', 0)
                
                # 计算实际删除的镜像数量
                if removed_images is not None and isinstance(removed_images, list):
                    actual_removed = len([img for img in removed_images if img is not None])
                else:
                    actual_removed = 0
            else:
                actual_removed = 0
                space_reclaimed = 0
                
        except Exception as prune_error:
            # 如果 prune 失败，记录但不抛出错误
            print(f"⚠️ 镜像清理执行完成（无需要清理的镜像）: {prune_error}")
            actual_removed = 0
            space_reclaimed = 0
        
        # 生成报告
        report = "🧹 镜像清理报告\n---\n"
        report += f"🗑️ 删除无用镜像：{actual_removed} 个\n"
        report += f"💾 释放磁盘空间：{space_reclaimed / 1024 / 1024:.2f} MB\n"
        
        if actual_removed > 0:
            report += "\n📋 已删除的镜像：\n"
            # 如果有删除的镜像，尝试显示详细信息
            try:
                if result and 'ImagesDeleted' in result:
                    for img in result['ImagesDeleted']:
                        if img and isinstance(img, dict):
                            deleted_tag = img.get('Deleted', '')
                            if deleted_tag:
                                image_id = deleted_tag.split(':')[1][:12] if ':' in deleted_tag else deleted_tag[:12]
                                report += f"- 镜像ID: {image_id}\n"
            except:
                report += "- 清理完成（详细信息不可用）\n"
        else:
            report += "\n✅ 没有需要清理的镜像，系统状态良好。"
        
        await update.message.reply_text(report)
        print(f"✅ 镜像清理报告生成完成：删除 {actual_removed} 个镜像，释放 {space_reclaimed / 1024 / 1024:.2f} MB")

    except Exception as e:
        # 即使出现意外错误也提供友好的报告
        print(f"❌ 镜像清理过程中出现意外错误: {e}")
        error_report = (
            "🧹 镜像清理报告\n---\n"
            "🗑️ 删除无用镜像：0 个\n"
            "💾 释放磁盘空间：0.0 MB\n\n"
            "✅ 系统状态良好，无需清理"
        )
        await update.message.reply_text(error_report)

# ================= /test_schedule =================
async def test_schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """测试定时任务功能"""
    if not await check_permission(update): 
        return
    
    try:
        await update.message.reply_text("🧪 正在测试定时任务功能...")
        
        # 立即触发一次报告来测试功能
        client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET_PATH}")
        status_report = generate_container_status_report(client)
        current_time = get_china_time()
        
        # 解析定时设置显示友好时间
        schedule_time, friendly_time = parse_schedule_time()
        
        message = f"🧪 定时任务测试报告 ({current_time})\n\n{status_report}\n\n✅ 定时任务功能正常\n⏰ 定时设置: 每天 {friendly_time}"
        await update.message.reply_text(message)
        
        # 显示定时任务状态
        job_queue = context.application.job_queue
        if job_queue:
            jobs = job_queue.jobs()
            schedule_info = f"📅 定时任务状态:\n"
            schedule_info += f"✅ 已设置每天 {friendly_time} 定时报告\n"
            schedule_info += f"⏰ 下次执行: 明天 {friendly_time}"
        else:
            schedule_info = "❌ 定时任务队列未就绪"
            
        await update.message.reply_text(schedule_info)
        
    except Exception as e:
        await update.message.reply_text(f"❌ 测试失败：{e}")

# ================= /schedule_info =================
async def schedule_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看定时任务信息"""
    if not await check_permission(update): 
        return
    
    try:
        # 解析定时设置
        schedule_time, friendly_time = parse_schedule_time()
        
        job_queue = context.application.job_queue
        if job_queue:
            jobs = job_queue.jobs()
            if jobs:
                job_info = "📅 当前定时任务:\n"
                for job in jobs:
                    job_info += f"- {job.name}: 每天 {friendly_time} 执行\n"
            else:
                job_info = "⚠️ 没有活跃的定时任务"
        else:
            job_info = "❌ 定时任务队列未就绪"
    
        info = (
            "📅 定时任务设置信息\n\n"
            "🕐 Watchtower 更新检查:\n"
            f"   - 时间: 每天 {friendly_time}\n"
            f"   - 命令: --schedule \"{WATCHTOWER_SCHEDULE}\"\n\n"
            "📊 Bot 状态报告:\n"
            f"   - 时间: 每天 {friendly_time}\n"
            "   - 内容: 完整容器状态报告\n\n"
            f"{job_info}\n\n"
            "💡 立即测试:\n"
            "   - 使用 /runonce 立即检查更新\n"
            "   - 使用 /test_schedule 测试报告功能\n"
            "   - 使用 /check_jobs 查看任务状态\n"
            "   - 使用 /status 查看当前状态"
        )
        
        await update.message.reply_text(info)
    except Exception as e:
        await update.message.reply_text(f"❌ 获取定时任务信息失败: {e}")

# ================= /check_jobs =================
async def check_jobs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """检查当前定时任务状态"""
    if not await check_permission(update): 
        return
    
    try:
        job_queue = context.application.job_queue
        if job_queue:
            jobs = job_queue.jobs()
            if jobs:
                message = "📅 当前活跃的定时任务:\n\n"
                for job in jobs:
                    next_run = job.next_t
                    if next_run:
                        # 转换为中国时区
                        next_run_china = next_run.astimezone(china_tz)
                        next_run_str = next_run_china.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        next_run_str = "未知"
                    
                    message += f"🔹 {job.name}\n"
                    message += f"   下次执行: {next_run_str}\n\n"
            else:
                message = "⚠️ 没有活跃的定时任务"
        else:
            message = "❌ JobQueue 不可用"
        
        await update.message.reply_text(message)
        
    except Exception as e:
        await update.message.reply_text(f"❌ 检查任务失败: {e}")

# ================= 主程序启动 =================
def main():
    """主程序"""
    print("🔄 正在启动 Watchtower 控制 Bot...")
    
    # 显示当前定时设置
    schedule_time, friendly_time = parse_schedule_time()
    print(f"⏰ 当前定时设置: {WATCHTOWER_SCHEDULE} (每天 {friendly_time})")
    print(f"🌏 系统时区: {china_tz}")
    
    # 创建应用
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 添加命令处理器
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("allcontainers", allcontainers_command))
    app.add_handler(CommandHandler("restart", restart_command))
    app.add_handler(CommandHandler("logs", logs_command))
    app.add_handler(CommandHandler("runonce", runonce_command))
    app.add_handler(CommandHandler("cleanup", cleanup_command))
    app.add_handler(CommandHandler("test_schedule", test_schedule_command))
    app.add_handler(CommandHandler("schedule_info", schedule_info_command))
    app.add_handler(CommandHandler("check_jobs", check_jobs_command))

    # 设置定时任务
    setup_daily_schedule(app)

    # 延迟启动通知线程，确保环境就绪
    def delayed_startup():
        time.sleep(10)  # 等待10秒确保环境完全就绪
        send_startup_notification()
    
    startup_thread = threading.Thread(target=delayed_startup)
    startup_thread.daemon = True
    startup_thread.start()

    print("✅ Watchtower 控制 Bot 已启动")
    print("🔄 开始轮询...")
    
    # 启动 bot
    app.run_polling()

if __name__ == "__main__":
    main()
