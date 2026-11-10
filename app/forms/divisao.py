from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField
from wtforms.validators import DataRequired, Length

from ..services.divisao_service import TAMANHO_MAXIMO_SIGLA


class DivisaoForm(FlaskForm):
    sigla = StringField(
        "Sigla",
        validators=[
            DataRequired(message="Informe a sigla da divisão."),
            Length(max=TAMANHO_MAXIMO_SIGLA, message=f"Máximo de {TAMANHO_MAXIMO_SIGLA} caracteres."),
        ],
        render_kw={"placeholder": "Ex.: DIO ou DIO/DPO", "maxlength": TAMANHO_MAXIMO_SIGLA},
    )
    para_usuarios = BooleanField("Aparece no cadastro de usuários", default=True)
    para_demandas = BooleanField("Aparece nas demandas", default=True)
    ativa = BooleanField("Ativa", default=True)
