FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Chromium and its driver for Selenium
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    DATA_PATH="/app/data"

COPY pyproject.toml pyproject.toml
COPY requirements.txt requirements.txt

COPY mpg_explorer ./mpg_explorer
COPY notebooks notebooks

RUN uv venv && \
    uv pip install .

RUN mkdir -p /app/data /app/data/reports /app/data_kestra

# ENTRYPOINT ["python"]
# CMD ["python", "notebooks/player_bonus_status.py"]
CMD ["tail", "-f", "/dev/null"]