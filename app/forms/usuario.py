from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField
from wtforms.validators import DataRequired, Email, Length, Optional

from ..services.perfis import Perfil
from .auth import opcoes_divisao_usuario


class UsuarioForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(message="Informe o nome."), Length(max=120)])
    email = StringField(
        "E-mail", validators=[DataRequired(message="Informe o e-mail."), Email(message="E-mail inválido."), Length(max=120)]
    )
    perfil = SelectField("Perfil", choices=[(p, Perfil.rotulo(p)) for p in Perfil.TODOS])
    divisao = SelectField("Divisão", default="")
    senha = PasswordField(
        "Senha", validators=[Optional(), Length(min=8, message="Mínimo de 8 caracteres.")]
    )
    ativo = BooleanField("Ativo", default=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.divisao.choices = opcoes_divisao_usuario(
            kwargs.get("obj"), vazio="— Não informada (o usuário escolhe ao entrar) —"
        )
