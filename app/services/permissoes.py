"""Matriz de permissões por perfil. Funções puras, sem acesso a banco.

Cada perfil tem um conjunto de funcionalidades que podem ser ligadas ou desligadas pelo
Administrador na tela Permissões. O padrão (PADRAO) reproduz as regras originais:

| Ação                                  | Gerente | Chefe de Divisão         | Usuário Comum |
|---------------------------------------|---------|--------------------------|---------------|
| Criar / editar / cancelar demanda     | Sim     | Sim                      | Não           |
| Definir pesos GUT                     | Sim     | Sim                      | Não           |
| Atribuir demanda                      | A todos | Só a Usuário Comum¹      | Não           |
| Aceitar / recusar (com justificativa) | Se for o atribuído (fixo)                          |
| Enviar para revisão                   | Se for o atribuído (fixo)                          |
| Aprovar / devolver revisão            | Sim     | Sim, se não for o atribuído | Não        |
| Ver todas as demandas                 | Sim     | Sim                      | Só as suas    |
| Gerenciar usuários                    | Sim     | Não                      | Não           |

O Gestor do Plano tem os mesmos poderes do Chefe de Divisão, exceto que
¹ também pode atribuir demandas a si mesmo.

As alterações feitas na tela ficam no banco; permissao_service.carregar() as aplica aqui
com configurar() a cada requisição. Sem configuração, vale o PADRAO.
"""
from .perfis import Perfil

# (chave, rótulo, grupo) — a ordem é a ordem das linhas na tela Permissões
FUNCIONALIDADES = [
    ("criar_demanda", "Criar demanda", "Demandas"),
    ("editar_demanda", "Editar demanda", "Demandas"),
    ("cancelar_demanda", "Cancelar demanda", "Demandas"),
    ("definir_gut", "Definir pesos GUT", "Demandas"),
    ("ver_todas", "Ver todas as demandas (desligado: só as suas e as de apoio)", "Demandas"),
    ("atribuir_a_si", "Atribuir a si mesmo (aceite automático)", "Atribuição"),
    ("atribuir_" + Perfil.GERENTE, "Atribuir a Gerente", "Atribuição"),
    ("atribuir_" + Perfil.CHEFE, "Atribuir a Chefe de Divisão", "Atribuição"),
    ("atribuir_" + Perfil.GESTOR_PLANO, "Atribuir a Gestor do Plano", "Atribuição"),
    ("atribuir_" + Perfil.USUARIO, "Atribuir a Usuário Comum", "Atribuição"),
    ("revisar", "Aprovar / devolver entrega", "Revisão"),
    ("revisar_propria", "Aprovar / devolver a própria entrega", "Revisão"),
    ("gerenciar_usuarios", "Gerenciar usuários", "Administração"),
]
CHAVES = frozenset(chave for chave, _, _ in FUNCIONALIDADES)

_GESTAO = {"criar_demanda", "editar_demanda", "cancelar_demanda", "definir_gut", "ver_todas", "revisar"}
_ATRIBUIR_TODOS = {"atribuir_" + p for p in Perfil.TODOS}

PADRAO = {
    Perfil.GERENTE: _GESTAO | _ATRIBUIR_TODOS | {"atribuir_a_si", "revisar_propria", "gerenciar_usuarios"},
    Perfil.CHEFE: _GESTAO | {"atribuir_" + Perfil.USUARIO},
    Perfil.GESTOR_PLANO: _GESTAO | {"atribuir_" + Perfil.USUARIO, "atribuir_a_si"},
    Perfil.USUARIO: set(),
}

# {(perfil, chave): ativo} — só o que difere do padrão
_alteracoes = {}


def configurar(alteracoes):
    """Substitui as alterações em vigor (dicionário vazio volta ao padrão)."""
    global _alteracoes
    _alteracoes = dict(alteracoes)


def padrao(perfil, chave):
    return chave in PADRAO.get(perfil, ())


def permitido(perfil, chave):
    return _alteracoes.get((perfil, chave), padrao(perfil, chave))


def eh_gestor(perfil):
    return perfil in Perfil.GESTORES


def pode_criar_demanda(perfil):
    return permitido(perfil, "criar_demanda")


def pode_editar_demanda(perfil):
    return permitido(perfil, "editar_demanda")


def pode_cancelar(perfil):
    return permitido(perfil, "cancelar_demanda")


def pode_definir_gut(perfil):
    return permitido(perfil, "definir_gut")


def pode_ver_todas(perfil):
    return permitido(perfil, "ver_todas")


def pode_gerenciar_usuarios(perfil):
    return permitido(perfil, "gerenciar_usuarios")


def pode_atribuir(perfil_quem_atribui, perfil_destino, para_si=False):
    """Atribuir a si mesmo é uma permissão própria; a outra pessoa depende do perfil dela."""
    if para_si:
        return permitido(perfil_quem_atribui, "atribuir_a_si")
    return perfil_destino in Perfil.TODOS and permitido(perfil_quem_atribui, "atribuir_" + perfil_destino)


def pode_atribuir_alguem(perfil):
    return any(permitido(perfil, chave) for chave in _ATRIBUIR_TODOS | {"atribuir_a_si"})


def descrever_atribuicao(perfil):
    """Texto de ajuda: a quem o perfil pode atribuir. None se puder a todos."""
    destinos = [Perfil.rotulo(p) for p in Perfil.TODOS if permitido(perfil, "atribuir_" + p)]
    a_si = permitido(perfil, "atribuir_a_si")
    if len(destinos) == len(Perfil.TODOS) and a_si:
        return None
    partes = (["a si mesmo"] if a_si else []) + [f"a usuários com perfil {d}" for d in destinos]
    if not partes:
        return "não pode atribuir demandas"
    return "só pode atribuir " + (", ".join(partes[:-1]) + " ou " + partes[-1] if len(partes) > 1 else partes[0])


def pode_revisar(perfil, eh_o_atribuido):
    """Aprovar/devolver; quando o revisor é o próprio responsável, exige também 'revisar_propria'."""
    if not permitido(perfil, "revisar"):
        return False
    return not eh_o_atribuido or permitido(perfil, "revisar_propria")
