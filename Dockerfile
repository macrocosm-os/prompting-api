FROM python:3.10-bookworm

COPY . /app
WORKDIR /app

EXPOSE 8000
RUN pip install poetry
RUN poetry install

ENTRYPOINT ["python", "api.py"]
