FROM python:3.12.7-slim-bookworm
WORKDIR /srv/

COPY pyproject.toml .
COPY poetry.lock .

RUN apt-get update && pip install poetry

RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction

RUN apt-get clean && rm -rf /var/lib/apt/lists/* && apt-get autoremove -y
RUN pip uninstall pipenv poetry -y

COPY . .

CMD ["python", "-m", "mikrotik_proxy_manager"]