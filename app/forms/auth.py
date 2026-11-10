from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField
from wtforms.validators import DataRequired, Email, EqualTo, Length

from ..services import divisao_service


def opcoes_divisao_usuario(obj=None, vazio="Selecione..."):
    """Divisões ativas para usuários (cadastradas pelo Administrador em Divisões)."""
    siglas = divisao_service.siglas_para_usuarios(atual=getattr(obj, "divisao", None))
    return [("", vazio)] + [(s, s) for s in siglas]


class LoginForm(FlaskForm):
    email = StringField("E-mail", validators=[DataRequired(message="Informe o e-mail.")])
    senha = PasswordField("Senha", validators=[DataRequired(message="Informe a senha.")])
    lembrar = BooleanField("Manter conectado")


class TrocarSenhaForm(FlaskForm):
    senha_atual = PasswordField("Senha atual", validators=[DataRequired()])
    nova_senha = PasswordField(
        "Nova senha", validators=[DataRequired(), Length(min=8, message="Mínimo de 8 caracteres.")]
    )
    confirmacao = PasswordField(
        "Confirme a nova senha", validators=[EqualTo("nova_senha", message="As senhas não conferem.")]
    )


class CadastroForm(FlaskForm):
    nome = StringField("Nome completo", validators=[DataRequired(message="Informe o nome."), Length(max=120)])
    email = StringField(
        "E-mail", validators=[DataRequired(message="Informe o e-mail."), Email(message="E-mail inválido."), Length(max=120)]
    )
    divisao = SelectField("Divisão", validators=[DataRequired(message="Selecione a divisão.")])
    senha = PasswordField(
        "Senha", validators=[DataRequired(message="Informe a senha."), Length(min=8, message="Mínimo de 8 caracteres.")]
    )
    confirmacao = PasswordField(
        "Confirme a senha", validators=[EqualTo("senha", message="As senhas não conferem.")]
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.divisao.choices = opcoes_divisao_usuario()


class MinhaDivisaoForm(FlaskForm):
    divisao = SelectField("Divisão", validators=[DataRequired(message="Selecione a divisão.")])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.divisao.choices = opcoes_divisao_usuario(kwargs.get("obj"))
