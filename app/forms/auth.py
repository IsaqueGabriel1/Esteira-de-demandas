from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField
from wtforms.validators import DataRequired, EqualTo, Length


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
