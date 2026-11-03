from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, SelectMultipleField, TextAreaField
from wtforms.validators import DataRequired, Optional, ValidationError

from ..services import permissoes

OPCOES_PESO = [(0, "—")] + [(i, str(i)) for i in range(1, 6)]


def _int_ou_zero(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


class DemandaForm(FlaskForm):
    eixo_id = SelectField("Eixo", coerce=_int_ou_zero, validators=[DataRequired(message="Selecione o eixo.")])
    acao = TextAreaField("Ação", validators=[DataRequired(message="Descreva a ação a ser realizada.")])
    produto = TextAreaField(
        "Produto / Entrega", validators=[DataRequired(message="Descreva o produto ou entrega esperada.")]
    )
    inicio = DateField("Começa em", validators=[Optional()])
    termino = DateField("Termina em", validators=[Optional()])
    atribuido_id = SelectField("Usuário atribuído", coerce=_int_ou_zero, validate_choice=False)
    apoio_ids = SelectMultipleField("Usuários de apoio", coerce=_int_ou_zero, validate_choice=False)
    gravidade = SelectField("Gravidade (G)", coerce=_int_ou_zero, choices=OPCOES_PESO)
    urgencia = SelectField("Urgência (U)", coerce=_int_ou_zero, choices=OPCOES_PESO)
    tendencia = SelectField("Tendência (T)", coerce=_int_ou_zero, choices=OPCOES_PESO)

    def configurar(self, usuario_logado, eixos, usuarios):
        """Preenche as opções. Todos os usuários aparecem; os que o usuário logado
        não pode atribuir ficam desabilitados (a regra é validada de novo no back-end)."""
        self.eixo_id.choices = [(0, "Selecione...")] + [(e.id, e.rotulo) for e in eixos]
        opcoes = [(0, "— Não atribuir agora —", {})]
        for u in usuarios:
            rotulo = f"{u.nome} ({u.perfil_rotulo})"
            render_kw = {} if permissoes.pode_atribuir(usuario_logado.perfil, u.perfil) else {"disabled": True}
            opcoes.append((u.id, rotulo, render_kw))
        self.atribuido_id.choices = opcoes
        self.apoio_ids.choices = [(u.id, f"{u.nome} ({u.perfil_rotulo})") for u in usuarios]
        return self

    def validate_termino(self, campo):
        if campo.data and self.inicio.data and campo.data < self.inicio.data:
            raise ValidationError("O término deve ser igual ou posterior ao início.")

    def validate_apoio_ids(self, campo):
        if self.atribuido_id.data and self.atribuido_id.data in (campo.data or []):
            raise ValidationError("O usuário atribuído não pode ser também usuário de apoio.")

    def validate_tendencia(self, _campo):
        pesos = [self.gravidade.data, self.urgencia.data, self.tendencia.data]
        if any(pesos) and not all(pesos):
            raise ValidationError("Preencha os três pesos GUT ou deixe todos em branco.")

    def para_dados(self):
        """Converte o formulário no dicionário esperado pela camada de serviços."""
        def peso(campo):
            return campo.data or None

        return {
            "eixo_id": self.eixo_id.data or None,
            "acao": self.acao.data,
            "produto": self.produto.data,
            "inicio": self.inicio.data,
            "termino": self.termino.data,
            "atribuido_id": self.atribuido_id.data or None,
            "apoio_ids": [i for i in (self.apoio_ids.data or []) if i],
            "gravidade": peso(self.gravidade),
            "urgencia": peso(self.urgencia),
            "tendencia": peso(self.tendencia),
        }
