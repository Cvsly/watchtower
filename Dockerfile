FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 明确安装 job-queue 扩展
RUN pip install --no-cache-dir \
    "python-telegram-bot[job-queue]" \
    docker \
    pytz \
    requests

COPY main.py .

CMD ["python", "main.py"]
