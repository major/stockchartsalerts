
# From https://fastapi.tiangolo.com/deployment/docker/#docker-image-with-poetry
FROM docker.io/library/python:3.13@sha256:a6af772cf98267c48c145928cbeb35bd8e89b610acd70f93e3e8ac3e96c92af8
WORKDIR /app

RUN pip install -U pip poetry
COPY ./pyproject.toml ./poetry.lock* /

RUN poetry config virtualenvs.create false
RUN poetry install --only main --no-root

COPY ./stockchartsalerts /code/stockchartsalerts
COPY ./run_bot.py /code/run_bot.py
CMD ["./run_bot.py"]
