FROM python:latest

COPY . /app

WORKDIR /app

RUN pip install -r requirements.txt

CMD ["sh", "-c", "sleep 150s && python bot.py"]
