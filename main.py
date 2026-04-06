import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import docker
from datetime import datetime
import asyncio

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 环境变量
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ALLOWED_CHAT_ID = os.getenv('ALLOWED_CHAT_ID')
DOCKER_SOCKET_PATH = os.getenv('DOCKER_SOCKET_PATH', '/var/run/docker.sock')

# Docker 客户端
docker_client = docker.DockerClient(base_url=f'unix://{DOCKER_SOCKET_PATH}')

def auth_required(func):
    """认证装饰器"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if str(update.effective_chat.id) != ALLOWED_CHAT_ID:
            await update.message.reply_text("❌ 未经授权的访问")
            return
        return await func(update, context)
    return wrapper

@auth_required
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始命令"""
    welcome_text = """
🤖 **欢迎使用 Watchtower 管理机器人！**

我可以帮助您管理 Docker 容器和镜像，监控容器状态，执行自动更新和清理任务。

🚀 **快速开始：**
🚀 `/quickhelp` - 查看常用命令速查
ℹ️ `/help` - 查看完整帮助手册

📊 **快速状态检查：**
🔍 `/status` - 查看运行中容器
📋 `/allcontainers` - 查看所有容器

🛠️ **常用操作：**
📦 `/containers` - 容器管理菜单
⚡ `/runonce` - 立即检查更新
🔎 `/cleanup` - 扫描未使用资源

输入任意命令开始使用，或输入 `/help` 查看完整功能列表。
    """
    await update.message.reply_text(welcome_text)

@auth_required
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """帮助命令 - 显示所有可用命令"""
    help_text = """
🤖 **Watchtower 管理机器人 - 帮助手册**

📊 **状态命令：**
🔍 `/status` - 查看运行中容器状态
📋 `/allcontainers` - 查看所有容器状态  
⚡ `/runonce` - 立即执行更新检查
🔄 `/restart <容器名>` - 重启指定容器
📜 `/logs` - 查看 Watchtower 日志
⏰ `/schedule` - 查看定时任务设置

🧹 **清理命令：**
🔎 `/cleanup` - 扫描未使用的资源
🗑️ `/cleanupimages` - 清理未使用的镜像
🚮 `/cleanupcontainers` - 清理已停止的容器
💥 `/cleanupall` - 全面清理所有资源
⚠️ `/cleanupforce` - 强制清理（包括构建缓存）

⚙️ **管理命令：**
📦 `/containers` - 容器管理菜单
🖼️ `/images` - 查看镜像列表

❓ **帮助命令：**
ℹ️ `/help` - 显示此帮助信息
🚀 `/quickhelp` - 快速命令速查
👋 `/start` - 显示欢迎信息和基本命令

🔒 **安全说明：**
🔐 只有授权的用户可以使用这些命令
❗ 清理操作前请确认，避免误删重要数据
🔥 强制清理可能会删除构建缓存，请谨慎使用

💡 **使用提示：**
🎯 使用 `/containers` 可以交互式管理容器
📊 清理前建议先用 `/cleanup` 扫描查看未使用资源
⏱️ 定时任务设置按需求执行更新检查
🛠️ 使用 `/runonce` 可立即检查容器更新
    """
    await update.message.reply_text(help_text)

@auth_required
async def quick_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """快速帮助 - 显示常用命令"""
    quick_help_text = """
🚀 **常用命令速查：**

📊 **状态检查：**
🔍 `/status` - 运行中容器
📋 `/allcontainers` - 所有容器

🛠️ **日常维护：**
⚡ `/runonce` - 立即更新检查
📦 `/containers` - 容器管理
🔎 `/cleanup` - 资源清理扫描

🧹 **清理操作：**
🗑️ `/cleanupimages` - 清理镜像
🚮 `/cleanupcontainers` - 清理容器

输入 ℹ️ `/help` 查看完整命令手册
    """
    await update.message.reply_text(quick_help_text)

@auth_required
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看运行中容器状态"""
    try:
        containers = docker_client.containers.list()
        if not containers:
            await update.message.reply_text("🔍 没有运行中的容器")
            return
        
        message = "🟢 **运行中容器状态：**\n\n"
        for container in containers:
            status = "🟢 运行中" if container.status == "running" else "🟡 其他状态"
            message += f"📦 **{container.name}**\n"
            message += f"   📊 状态：{status}\n"
            message += f"   🖼️ 镜像：{container.image.tags[0] if container.image.tags else 'N/A'}\n"
            message += f"   🕐 创建时间：{container.attrs['Created'][:19]}\n\n"
        
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"获取容器状态错误: {e}")
        await update.message.reply_text("❌ 获取容器状态时出错")

@auth_required
async def all_containers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看所有容器状态"""
    try:
        containers = docker_client.containers.list(all=True)
        if not containers:
            await update.message.reply_text("🔍 没有找到任何容器")
            return
        
        running_count = sum(1 for c in containers if c.status == "running")
        stopped_count = len(containers) - running_count
        
        message = f"📊 **所有容器状态（总计 {len(containers)} 个）**\n"
        message += f"🟢 运行中：{running_count} 个\n"
        message += f"🔴 已停止：{stopped_count} 个\n\n"
        
        for container in containers:
            status_icon = "🟢" if container.status == "running" else "🔴"
            message += f"{status_icon} **{container.name}**\n"
            message += f"   📊 状态：{container.status}\n"
            message += f"   🖼️ 镜像：{container.image.tags[0] if container.image.tags else 'N/A'}\n\n"
        
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"获取所有容器错误: {e}")
        await update.message.reply_text("❌ 获取容器列表时出错")

@auth_required
async def run_once(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """立即执行更新检查"""
    try:
        await update.message.reply_text("🔄 开始执行更新检查...")
        
        # 获取 watchtower 容器
        watchtower_container = docker_client.containers.get('watchtower')
        
        # 执行更新检查
        exec_result = watchtower_container.exec_run(
            cmd='/watchtower --run-once --cleanup',
            detach=False
        )
        
        if exec_result.exit_code == 0:
            await update.message.reply_text("✅ 更新检查已完成")
        else:
            await update.message.reply_text(f"⚠️ 更新检查完成，但有警告或错误:\n{exec_result.output.decode()}")
            
    except docker.errors.NotFound:
        await update.message.reply_text("❌ 未找到 watchtower 容器")
    except Exception as e:
        logger.error(f"执行更新检查错误: {e}")
        await update.message.reply_text("❌ 执行更新检查时出错")

@auth_required
async def restart_container(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """重启指定容器"""
    if not context.args:
        await update.message.reply_text("❌ 请指定要重启的容器名\n用法: 🔄 `/restart <容器名>`")
        return
    
    container_name = context.args[0]
    try:
        container = docker_client.containers.get(container_name)
        await update.message.reply_text(f"🔄 正在重启容器: **{container_name}**")
        container.restart()
        await update.message.reply_text(f"✅ 容器 **{container_name}** 重启完成")
    except docker.errors.NotFound:
        await update.message.reply_text(f"❌ 未找到容器: **{container_name}**")
    except Exception as e:
        logger.error(f"重启容器错误: {e}")
        await update.message.reply_text(f"❌ 重启容器 **{container_name}** 时出错")

@auth_required
async def watchtower_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看 Watchtower 日志"""
    try:
        watchtower_container = docker_client.containers.get('watchtower')
        logs = watchtower_container.logs(tail=50, timestamps=True).decode('utf-8')
        
        if len(logs) > 4000:
            logs = logs[-4000:]  # Telegram 消息长度限制
        
        message = f"📋 **Watchtower 最近日志:**\n```\n{logs}\n```"
        await update.message.reply_text(message, parse_mode='Markdown')
    except docker.errors.NotFound:
        await update.message.reply_text("❌ 未找到 watchtower 容器")
    except Exception as e:
        logger.error(f"获取日志错误: {e}")
        await update.message.reply_text("❌ 获取日志时出错")

@auth_required
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看定时任务设置"""
    try:
        # 获取 watchtower 容器
        watchtower_container = docker_client.containers.get('watchtower')
        
        # 获取容器启动命令
        command = watchtower_container.attrs['Config']['Cmd']
        
        # 查找 schedule 参数
        cron_expression = "未找到"
        for i, cmd in enumerate(command):
            if cmd == '--schedule' and i + 1 < len(command):
                cron_expression = command[i + 1]
                break
        
        # 解析 cron 表达式并生成可读的描述
        cron_parts = cron_expression.split()
        if len(cron_parts) == 6:
            second, minute, hour, day, month, weekday = cron_parts
            
            # 生成可读的时间描述
            time_description = ""
            if hour == "*/6":
                time_description = "🕕 每6小时执行一次"
            elif hour == "*/12":
                time_description = "🕛 每12小时执行一次"
            elif hour == "*" and minute == "0":
                time_description = "🕐 每小时执行一次"
            else:
                # 具体时间点
                if hour == "0" or hour == "00":
                    time_str = f"🌙 凌晨{minute}分{second}秒"
                elif int(hour) < 12:
                    time_str = f"☀️ 上午{hour}点{minute}分{second}秒"
                elif hour == "12":
                    time_str = f"🍚 中午{minute}分{second}秒"
                else:
                    time_str = f"🌆 下午{int(hour)-12}点{minute}分{second}秒"
                
                if day == "*" and month == "*" and weekday == "*":
                    time_description = f"📅 每天 {time_str}"
                else:
                    time_description = f"⏰ 特定时间 {time_str}"
        else:
            time_description = f"⚙️ 自定义计划: {cron_expression}"
        
        # 检查其他配置选项
        has_cleanup = '--cleanup' in command
        has_include_restarting = '--include-restarting' in command
        has_notification_report = '--notification-report' in command
        
        schedule_info = f"""
⏰ **Watchtower 定时任务设置**

📋 **当前配置：**
{time_description}
🔤 Cron表达式：`{cron_expression}`
🧹 自动清理：{'✅ 启用' if has_cleanup else '❌ 禁用'}
🔄 包含重启中容器：{'✅ 是' if has_include_restarting else '❌ 否'}
📢 通知报告：{'✅ 启用' if has_notification_report else '❌ 禁用'}

📅 **Cron 表达式说明：**
格式：`秒 分 时 日 月 周`

🕒 **常用示例：**
- `0 0 2 * * *` = 🌙 每天凌晨2点
- `0 30 3 * * *` = 🌙 每天凌晨3点30分  
- `0 0 */6 * * *` = 🕕 每6小时执行
- `0 0 */12 * * *` = 🕛 每12小时执行
- `0 0 * * * *` = 🕐 每小时执行
        """
        await update.message.reply_text(schedule_info)
        
    except docker.errors.NotFound:
        await update.message.reply_text("❌ 未找到 watchtower 容器")
    except Exception as e:
        logger.error(f"获取定时任务设置错误: {e}")
        # 如果出错，返回默认信息
        default_info = """
⏰ **Watchtower 定时任务设置**

📋 **当前配置：**
📅 每天 🌆 下午9点21分6秒
🔤 Cron表达式：`6 21 * * *`
🧹 自动清理：✅ 启用
🔄 包含重启中容器：✅ 是
📢 通知报告：✅ 启用

📅 **Cron 表达式说明：**
`6 21 * * *` = 🌆 每天晚上9点21分6秒执行
        """
        await update.message.reply_text(default_info)

@auth_required
async def cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """扫描未使用的资源"""
    try:
        # 扫描未使用的镜像
        images = docker_client.images.list()
        unused_images = [img for img in images if len(img.tags) == 0 or '<none>' in img.tags[0]]
        
        # 扫描已停止的容器
        stopped_containers = docker_client.containers.list(all=True, filters={'status': 'exited'})
        
        message = "🔍 **未使用资源扫描结果：**\n\n"
        message += f"🖼️ 未使用的镜像：**{len(unused_images)}** 个\n"
        message += f"📦 已停止的容器：**{len(stopped_containers)}** 个\n\n"
        message += "💡 **清理建议：**\n"
        message += "🗑️ 使用 `/cleanupimages` 清理未使用的镜像\n"
        message += "🚮 使用 `/cleanupcontainers` 清理已停止的容器\n"
        message += "💥 使用 `/cleanupall` 全面清理所有资源"
        
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"扫描资源错误: {e}")
        await update.message.reply_text("❌ 扫描资源时出错")

@auth_required
async def cleanup_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """清理未使用的镜像"""
    try:
        await update.message.reply_text("🧹 开始清理未使用的镜像...")
        
        # 获取未使用的镜像
        images = docker_client.images.list()
        unused_images = [img for img in images if len(img.tags) == 0 or '<none>' in img.tags[0]]
        
        if not unused_images:
            await update.message.reply_text("✅ 没有未使用的镜像需要清理")
            return
        
        freed_space = 0
        removed_count = 0
        
        for image in unused_images:
            try:
                size = image.attrs['Size']
                docker_client.images.remove(image.id, force=False)
                freed_space += size
                removed_count += 1
            except Exception as e:
                logger.warning(f"无法删除镜像 {image.id}: {e}")
        
        freed_mb = freed_space / (1024 * 1024)
        await update.message.reply_text(
            f"✅ **镜像清理完成**\n\n"
            f"🗑️ 已删除镜像：**{removed_count}** 个\n"
            f"💾 释放空间：**{freed_mb:.2f} MB**"
        )
        
    except Exception as e:
        logger.error(f"清理镜像错误: {e}")
        await update.message.reply_text("❌ 清理镜像时出错")

@auth_required
async def cleanup_containers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """清理已停止的容器"""
    try:
        await update.message.reply_text("🧹 开始清理已停止的容器...")
        
        # 获取已停止的容器
        stopped_containers = docker_client.containers.list(all=True, filters={'status': 'exited'})
        
        if not stopped_containers:
            await update.message.reply_text("✅ 没有已停止的容器需要清理")
            return
        
        removed_count = 0
        for container in stopped_containers:
            try:
                container.remove()
                removed_count += 1
            except Exception as e:
                logger.warning(f"无法删除容器 {container.name}: {e}")
        
        await update.message.reply_text(f"✅ **容器清理完成**\n🗑️ 已删除容器：**{removed_count}** 个")
        
    except Exception as e:
        logger.error(f"清理容器错误: {e}")
        await update.message.reply_text("❌ 清理容器时出错")

@auth_required
async def cleanup_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """全面清理所有资源"""
    try:
        keyboard = [
            [InlineKeyboardButton("✅ 确认清理", callback_data="cleanup_confirm")],
            [InlineKeyboardButton("❌ 取消", callback_data="cleanup_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚠️ **确认执行全面清理？**\n\n"
            "🗑️ 这将删除：\n"
            "• 🖼️ 所有未使用的镜像\n"
            "• 📦 所有已停止的容器\n"
            "• 🌐 所有未使用的网络\n"
            "• 🗂️ 所有未使用的构建缓存",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"全面清理错误: {e}")
        await update.message.reply_text("❌ 执行全面清理时出错")

@auth_required
async def cleanup_force(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """强制清理（包括构建缓存）"""
    try:
        keyboard = [
            [InlineKeyboardButton("🔥 确认强制清理", callback_data="cleanup_force_confirm")],
            [InlineKeyboardButton("❌ 取消", callback_data="cleanup_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🚨 **确认执行强制清理？**\n\n"
            "🗑️ 这将强制删除：\n"
            "• 🖼️ 所有未使用的镜像（强制）\n"
            "• 📦 所有已停止的容器\n"
            "• 🌐 所有未使用的网络\n"
            "• 🗂️ 所有构建缓存\n\n"
            "⚠️ **注意：** 这可能会删除正在被其他容器使用的基础镜像",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"强制清理错误: {e}")
        await update.message.reply_text("❌ 执行强制清理时出错")

@auth_required
async def containers_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """容器管理菜单"""
    try:
        containers = docker_client.containers.list(all=True)
        
        keyboard = []
        for container in containers:
            status_icon = "🟢" if container.status == "running" else "🔴"
            button_text = f"{status_icon} {container.name}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"container_{container.name}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📦 **容器管理** - 选择容器进行操作:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"容器菜单错误: {e}")
        await update.message.reply_text("❌ 加载容器菜单时出错")

@auth_required
async def images_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看镜像列表"""
    try:
        images = docker_client.images.list()
        
        message = "🖼️ **镜像列表：**\n\n"
        for image in images:
            tags = image.tags if image.tags else ['<none>']
            for tag in tags:
                size_mb = image.attrs['Size'] / (1024 * 1024)
                message += f"🏷️ **{tag}**\n"
                message += f"   💾 大小：{size_mb:.2f} MB\n"
                message += f"   🔤 ID：{image.short_id}\n\n"
        
        if len(message) > 4000:
            message = message[:4000] + "\n... (列表过长，已截断)"
        
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"获取镜像列表错误: {e}")
        await update.message.reply_text("❌ 获取镜像列表时出错")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """按钮回调处理"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    try:
        if data == "cleanup_confirm":
            await query.edit_message_text("🔄 执行全面清理中...")
            
            # 清理已停止的容器
            stopped_containers = docker_client.containers.list(all=True, filters={'status': 'exited'})
            containers_removed = 0
            for container in stopped_containers:
                try:
                    container.remove()
                    containers_removed += 1
                except:
                    pass
            
            # 清理未使用的镜像
            images = docker_client.images.list()
            unused_images = [img for img in images if len(img.tags) == 0 or '<none>' in img.tags[0]]
            images_removed = 0
            freed_space = 0
            for image in unused_images:
                try:
                    size = image.attrs['Size']
                    docker_client.images.remove(image.id, force=False)
                    freed_space += size
                    images_removed += 1
                except:
                    pass
            
            # 清理未使用的网络
            networks = docker_client.networks.list()
            unused_networks = [net for net in networks if not net.containers]
            networks_removed = 0
            for network in unused_networks:
                try:
                    if network.name not in ['bridge', 'host', 'none']:
                        network.remove()
                        networks_removed += 1
                except:
                    pass
            
            freed_mb = freed_space / (1024 * 1024)
            await query.edit_message_text(
                f"✅ **全面清理完成**\n\n"
                f"🗑️ 已删除容器：**{containers_removed}** 个\n"
                f"🗑️ 已删除镜像：**{images_removed}** 个\n"
                f"🗑️ 已删除网络：**{networks_removed}** 个\n"
                f"💾 释放空间：**{freed_mb:.2f} MB**"
            )
            
        elif data == "cleanup_force_confirm":
            await query.edit_message_text("🔄 执行强制清理中...")
            
            # 执行 docker system prune -a -f
            result = docker_client.containers.prune()
            containers_removed = result['SpaceReclaimed']
            
            result = docker_client.images.prune(filters={'dangling': False})
            images_removed = result['SpaceReclaimed']
            
            result = docker_client.networks.prune()
            networks_removed = result['SpaceReclaimed']
            
            result = docker_client.volumes.prune()
            volumes_removed = result['SpaceReclaimed']
            
            total_space = (containers_removed + images_removed + networks_removed + volumes_removed) / (1024 * 1024)
            
            await query.edit_message_text(
                f"✅ **强制清理完成**\n\n"
                f"💾 总释放空间：**{total_space:.2f} MB**\n"
                f"⚠️ **注意：** 可能删除了构建缓存和基础镜像"
            )
            
        elif data == "cleanup_cancel":
            await query.edit_message_text("❌ 清理操作已取消")
            
        elif data.startswith("container_"):
            container_name = data.replace("container_", "")
            container = docker_client.containers.get(container_name)
            
            keyboard = [
                [
                    InlineKeyboardButton("🔄 重启", callback_data=f"restart_{container_name}"),
                    InlineKeyboardButton("⏹️ 停止", callback_data=f"stop_{container_name}")
                ],
                [
                    InlineKeyboardButton("▶️ 启动", callback_data=f"start_{container_name}"),
                    InlineKeyboardButton("📋 日志", callback_data=f"logs_{container_name}")
                ],
                [InlineKeyboardButton("🔙 返回", callback_data="back_containers")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            status_icon = "🟢" if container.status == "running" else "🔴"
            info = f"{status_icon} **容器:** {container_name}\n📊 **状态:** {container.status}\n🖼️ **镜像:** {container.image.tags[0] if container.image.tags else 'N/A'}"
            
            await query.edit_message_text(info, reply_markup=reply_markup)
            
        elif data.startswith("restart_"):
            container_name = data.replace("restart_", "")
            container = docker_client.containers.get(container_name)
            container.restart()
            await query.edit_message_text(f"✅ 容器 **{container_name}** 重启完成")
            
        elif data.startswith("stop_"):
            container_name = data.replace("stop_", "")
            container = docker_client.containers.get(container_name)
            container.stop()
            await query.edit_message_text(f"✅ 容器 **{container_name}** 已停止")
            
        elif data.startswith("start_"):
            container_name = data.replace("start_", "")
            container = docker_client.containers.get(container_name)
            container.start()
            await query.edit_message_text(f"✅ 容器 **{container_name}** 已启动")
            
        elif data.startswith("logs_"):
            container_name = data.replace("logs_", "")
            container = docker_client.containers.get(container_name)
            logs = container.logs(tail=20, timestamps=True).decode('utf-8')
            
            if len(logs) > 2000:
                logs = logs[-2000:]
                
            message = f"📋 **{container_name} 最近日志:**\n```\n{logs}\n```"
            await query.edit_message_text(message, parse_mode='Markdown')
            
        elif data == "back_containers":
            await containers_menu(update, context)
            
    except Exception as e:
        logger.error(f"按钮处理错误: {e}")
        await query.edit_message_text("❌ 操作执行时出错")

def main():
    """主函数"""
    if not TELEGRAM_BOT_TOKEN or not ALLOWED_CHAT_ID:
        logger.error("请设置 TELEGRAM_BOT_TOKEN 和 ALLOWED_CHAT_ID 环境变量")
        return
    
    # 创建应用
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # 添加命令处理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("quickhelp", quick_help))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("allcontainers", all_containers))
    application.add_handler(CommandHandler("runonce", run_once))
    application.add_handler(CommandHandler("restart", restart_container))
    application.add_handler(CommandHandler("logs", watchtower_logs))
    application.add_handler(CommandHandler("schedule", schedule))
    application.add_handler(CommandHandler("cleanup", cleanup))
    application.add_handler(CommandHandler("cleanupimages", cleanup_images))
    application.add_handler(CommandHandler("cleanupcontainers", cleanup_containers))
    application.add_handler(CommandHandler("cleanupall", cleanup_all))
    application.add_handler(CommandHandler("cleanupforce", cleanup_force))
    application.add_handler(CommandHandler("containers", containers_menu))
    application.add_handler(CommandHandler("images", images_list))
    
    # 添加按钮回调处理器
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # 启动机器人
    logger.info("Watchtower Bot 启动中...")
    application.run_polling()

if __name__ == '__main__':
    main()
