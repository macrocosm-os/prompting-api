FROM python:3.10-bookworm

COPY . /app
WORKDIR /app

EXPOSE 10000
RUN pip install -r requirements.txt

ENTRYPOINT ["python", "server.py"]

