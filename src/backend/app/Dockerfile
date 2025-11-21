FROM python:slim

WORKDIR /app

RUN apt-get update && apt-get install -y pandoc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /requirements.txt

RUN pip install --no-cache-dir --upgrade -r /requirements.txt

COPY . .

EXPOSE 8080

CMD ["fastapi", "run", "/app/main.py", "--port", "8080"]
