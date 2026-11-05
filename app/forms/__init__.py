"""Formulários Flask-WTF (validação de entrada e proteção CSRF)."""
from .auth import CadastroForm, LoginForm, TrocarSenhaForm
from .demanda import DemandaForm
from .usuario import UsuarioForm

__all__ = ["CadastroForm", "LoginForm", "TrocarSenhaForm", "DemandaForm", "UsuarioForm"]
