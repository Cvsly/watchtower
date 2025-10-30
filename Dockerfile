FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install python-telegram-bot==20.7 docker requests pytz

CMD ["python", "main.py"]
