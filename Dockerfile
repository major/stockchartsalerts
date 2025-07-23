
# From https://fastapi.tiangolo.com/deployment/docker/#docker-image-with-poetry
FROM docker.io/library/python:3.13@sha256:7175df81f9a313ee52286c94a5c35620d37afb31f9e05e47a3e058db84d53854
WORKDIR /app

RUN pip install -U pip poetry
COPY ./pyproject.toml ./poetry.lock* /

RUN poetry config virtualenvs.create false
RUN poetry install --only main --no-root

COPY ./stockchartsalerts /code/stockchartsalerts
COPY ./run_bot.py /code/run_bot.py
CMD ["./run_bot.py"]
