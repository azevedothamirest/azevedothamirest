FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV JOBBOT_DB=/data/jobbot.db
CMD ["python", "bot.py"]
