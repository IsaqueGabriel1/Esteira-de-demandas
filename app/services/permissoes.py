"""Matriz de permissões por perfil. Funções puras, sem acesso a banco.

| Ação                                  | Gerente | Chefe de Divisão         | Usuário Comum |
|---------------------------------------|---------|--------------------------|---------------|
| Criar / editar / cancelar demanda     | Sim     | Sim                      | Não           |
| Definir pesos GUT                     | Sim     | Sim                      | Não           |
| Atribuir demanda                      | A todos | Só a Usuário Comum       | Não           |
| Aceitar / recusar (com justificativa) | Se for o atribuído                                 |
| Enviar para revisão                   | Se for o atribuído                                 |
| Aprovar / devolver revisão            | Sim     | Sim, se não for o atribuído | Não        |
| Ver todas as demandas                 | Sim     | Sim                      | Só as suas    |
| Gerenciar usuários                    | Sim     | Não                      | Não           |
"""
from .perfis import Perfil


def eh_gestor(perfil):
    return perfil in Perfil.GESTORES


def pode_criar_demanda(perfil):
    return eh_gestor(perfil)


def pode_editar_demanda(perfil):
    return eh_gestor(perfil)


def pode_cancelar(perfil):
    return eh_gestor(perfil)


def pode_definir_gut(perfil):
    return eh_gestor(perfil)


def pode_ver_todas(perfil):
    return eh_gestor(perfil)


def pode_gerenciar_usuarios(perfil):
    return perfil == Perfil.GERENTE


def pode_atribuir(perfil_quem_atribui, perfil_destino):
    """Gerente atribui a qualquer pessoa; Chefe de Divisão apenas a Usuário Comum."""
    if perfil_quem_atribui == Perfil.GERENTE:
        return perfil_destino in Perfil.TODOS
    if perfil_quem_atribui == Perfil.CHEFE:
        return perfil_destino == Perfil.USUARIO
    return False


def pode_revisar(perfil, eh_o_atribuido):
    """Gerente sempre pode revisar; Chefe só se não for o responsável pela demanda."""
    if perfil == Perfil.GERENTE:
        return True
    if perfil == Perfil.CHEFE:
        return not eh_o_atribuido
    return False
