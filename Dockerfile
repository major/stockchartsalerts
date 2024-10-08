# From https://fastapi.tiangolo.com/deployment/docker/#docker-image-with-poetry
FROM python:3.13 AS requirements-stage
WORKDIR /tmp
RUN pip install -U pip && pip install poetry poetry-plugin-export
COPY ./pyproject.toml ./poetry.lock* /tmp/
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

FROM python:3.13-slim
WORKDIR /code
COPY --from=requirements-stage /tmp/requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./stockchartsalerts /code/stockchartsalerts
COPY ./run_bot.py /code/run_bot.py
CMD ["./run_bot.py"]
