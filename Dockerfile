FROM python:3.12.7-slim-bookworm
WORKDIR /srv/

COPY pyproject.toml .
COPY poetry.lock .

RUN apt update
RUN apt install -y gcc cmake make libc-dev-bin libc6-dev && pip install --upgrade pip
RUN pip install poetry

RUN poetry config virtualenvs.create false
RUN poetry install

RUN apt-get remove -y gcc cmake make libc-dev-bin libc6-dev
RUN rm -rf /var/lib/apt/lists/* && apt-get autoremove -y && apt-get clean
RUN pip uninstall pipenv poetry -y

COPY . .

CMD ["python", "-m", "mikrotik-proxy-manager"]