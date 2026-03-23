FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    DATA_PATH="/app/data"

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

RUN mkdir -p /app/data /app/data/reports

ENTRYPOINT ["python"]
# CMD ["python", "notebooks/player_bonus_status.py"]
CMD ["tail", "-f", "/dev/null"]