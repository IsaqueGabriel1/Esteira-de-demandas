"""Formulários Flask-WTF (validação de entrada e proteção CSRF)."""
from .auth import LoginForm, TrocarSenhaForm
from .demanda import DemandaForm
from .usuario import UsuarioForm

__all__ = ["LoginForm", "TrocarSenhaForm", "DemandaForm", "UsuarioForm"]
