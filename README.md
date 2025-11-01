# watchtower
Watchtower的特点与优势（此版本为中文通知）

一.   自动化更新：Watchtower可以定期（您可以配置更新检查的频率）检查您使用的Docker镜像，发现新版本后，自动停止、更新、重新启动容器，无需手动干预。这使得您可以专注于应用开发和其他重要任务，而不用担心容器更新的繁琐问题。

二.   支持多种镜像源：Watchtower支持多种Docker镜像源，包括Docker Hub、私有镜像仓库以及其他公共镜像仓库。这使得您可以灵活地选择自己喜欢的镜像来源。

三.   定制化更新策略：Watchtower允许您根据应用的特定需求定制化更新策略。您可以选择只更新特定标签的镜像，或者仅在满足特定条件（例如，依赖项更新或漏洞修复）时才进行更新。

四.   安全性：Watchtower在更新容器时非常重视安全性。它不会在不安全的网络环境中下载镜像，并且还支持使用私有访问令牌或证书来访问私有镜像仓库，确保您的镜像和数据不会泄露。

五.   通知与日志：Watchtower可以配置通知机制，让您及时了解容器更新的情况。同时，它还提供详细的日志记录，方便您查看更新过程的细节和可能出现的问题

Tips - 注意事项

    1  env环境变量修改部分：BOT_TOKEN=xxxxxxx,ALLOWED_CHAT_ID=xxxxxxx

    2  只需修改.env中的TOKEN和ID部分
   
    3  bot命令控制，举个栗子：/help
   
    4  四个文件与docker-compose.yml放在同一主目录下

    5  目前仅在telegram运行通知提醒，其它暂未测试，有问题请使用原版

    6  部署完后重建并测试
       cd /xxxx/watchtower/watchtower（进入容器所在目录）
       docker compose down
       docker compose up -d --build
       或者 docker exec watchtower /watchtower --run-once 测试发送通知
环境变量设置

environment:
      
      # --- 邮件通知配置 ---

      - WATCHTOWER_NOTIFICATIONS=email  # 启用邮件通知功能
      
      - WATCHTOWER_NOTIFICATION_EMAIL_FROM=<你的邮箱>@qq.com  # 邮件发送方（需替换为你的QQ邮箱）
      
      - WATCHTOWER_NOTIFICATION_EMAIL_TO=<你的邮箱>@qq.com  # 邮件接收方（可与发送方一致）
      
      - WATCHTOWER_NOTIFICATION_EMAIL_SERVER=smtp.qq.com  # QQ邮箱固定SMTP服务器地址
      
      - WATCHTOWER_NOTIFICATION_EMAIL_SERVER_PORT=587  # QQ邮箱TLS加密端口（推荐使用）
      
      - WATCHTOWER_NOTIFICATION_EMAIL_SERVER_USER=<你的邮箱>@qq.com  # SMTP登录账号（与发送方一致）
      
      - WATCHTOWER_NOTIFICATION_EMAIL_SERVER_PASSWORD=<你的SMTP授权码>  # QQ邮箱SMTP授权码（需替换，非邮箱密码）
      
      - WATCHTOWER_NOTIFICATION_EMAIL_SERVER_TLS_SKIP_VERIFY=false  # 不跳过TLS验证，保障传输安全
      
      - WATCHTOWER_NOTIFICATION_EMAIL_SUBJECTTAG=[Watchtower]  # 邮件主题前缀，方便识别
      
      - WATCHTOWER_NOTIFICATIONS_LEVEL=info  # 通知等级：仅容器更新时发邮件（推荐）

command:

      - "0 0 1 * * *"  # 设置容器更新检测间隔，定时：每天凌晨1点
      
      - --cleanup  # 开启自动清理，容器更新后删除旧版本镜像，释放宿主机空间
      
      - --no-startup-message  # 禁用启动通知，避免Watchtower启动时发送无用邮件
      
      - --warn-on-head-failure=never  # 忽略镜像头部拉取失败警告，减少网络波动导致的误报
      
      - danmu-api  # 指定仅监控名为"danmu-api"的容器【删除这行或注释掉，即可监控所有容器】
      
      - --notification-report=false  # 禁用检测报告邮件，仅在容器更新/出错时发通知，避免冗余邮件

源代码：https://github.com/containrrr/watchtower
