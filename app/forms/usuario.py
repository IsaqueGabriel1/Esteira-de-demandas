from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField
from wtforms.validators import DataRequired, Email, Length, Optional

from ..services.perfis import Perfil


class UsuarioForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(message="Informe o nome."), Length(max=120)])
    email = StringField(
        "E-mail", validators=[DataRequired(message="Informe o e-mail."), Email(message="E-mail inválido."), Length(max=120)]
    )
    perfil = SelectField("Perfil", choices=[(p, Perfil.rotulo(p)) for p in Perfil.TODOS])
    senha = PasswordField(
        "Senha", validators=[Optional(), Length(min=8, message="Mínimo de 8 caracteres.")]
    )
    ativo = BooleanField("Ativo", default=True)
