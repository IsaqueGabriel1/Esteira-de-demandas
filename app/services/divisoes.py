"""Divisões: a responsável pela demanda e a que o usuário pertence."""


class Divisao:
    DIO = "DIO"
    DPO = "DPO"
    DIO_DPO = "DIO/DPO"

    TODAS = (DIO, DPO, DIO_DPO)


class DivisaoUsuario:
    """Divisão a que cada usuário pertence (o Administrador fica de fora)."""

    SR = "SR"
    GGO = "GGO"
    DPO = "DPO"
    DIO = "DIO"

    TODAS = (SR, GGO, DPO, DIO)
