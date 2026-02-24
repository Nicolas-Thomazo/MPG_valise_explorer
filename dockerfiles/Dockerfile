# Utilisation d'une image de base légère Python 3.12
FROM python:3.12-slim-bookworm

# Installation de uv en copiant le binaire depuis l'image officielle (méthode recommandée)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Définition du répertoire de travail
WORKDIR /app
COPY pyproject.toml pyproject.toml
COPY requirements.txt requirements.txt

COPY mpg_explorer ./mpg_explorer
COPY notebooks notebooks

RUN uv venv && \
    uv pip install --no-cache-dir -e .

ENV PATH="/app/.venv/bin:$PATH"

CMD ["tail", "-f", "/dev/null"]