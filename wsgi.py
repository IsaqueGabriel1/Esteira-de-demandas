"""Ponto de entrada WSGI (usado pelo Gunicorn e pelo comando flask)."""
from app import create_app

app = create_app()
