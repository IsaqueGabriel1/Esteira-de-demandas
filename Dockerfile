FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FLASK_APP=wsgi.py

WORKDIR /app

# Usuário sem privilégios de root
RUN useradd --create-home --uid 1000 appuser

# Dependências primeiro (aproveita o cache do Docker entre builds)
ARG INSTALAR_DEV=false
COPY requirements.txt requirements-dev.txt ./
RUN if [ "$INSTALAR_DEV" = "true" ]; then pip install -r requirements-dev.txt; \
    else pip install -r requirements.txt; fi

COPY --chown=appuser:appuser . .

USER appuser
EXPOSE 8000

ENTRYPOINT ["sh", "/app/docker/entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
