FROM python:3.13.0-slim-bookworm
WORKDIR /srv/

COPY pyproject.toml .
COPY poetry.lock .

RUN apt update
RUN python3.13 -m pip install --pre cffi==1.17.0rc1
RUN pip install poetry

RUN poetry config virtualenvs.create false
RUN poetry install

RUN apt-get remove -y gcc cmake make libc-dev-bin libc6-dev
RUN rm -rf /var/lib/apt/lists/* && apt-get autoremove -y && apt-get clean
RUN pip uninstall pipenv poetry -y

COPY . .

CMD ["python", "-m", "mikrotik-proxy-manager"]