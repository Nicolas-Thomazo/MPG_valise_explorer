FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml pyproject.toml
COPY requirements.txt requirements.txt

COPY mpg_explorer ./mpg_explorer
COPY notebooks notebooks

# RUN apt-get update && apt-get install -y --no-install-recommends \
#     chromium \
#     chromium-driver \
#     ca-certificates \
#     fonts-liberation \
#     && rm -rf /var/lib/apt/lists/*

RUN uv venv && \
    uv pip install .

ENV PATH="/app/.venv/bin:$PATH"


CMD ["tail", "-f", "/dev/null"]
# CMD ["notebooks/player_bonus_status.py"]
