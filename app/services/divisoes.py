"""Divisões: a responsável pela demanda e a que o usuário pertence."""


class Divisao:
    DIO = "DIO"
    DPO = "DPO"
    GGO = "GGO"
    DIO_DPO = "DIO/DPO"
    DPO_DIO = "DPO/DIO"
    GGO_DPO_DIO = "GGO/DPO/DIO"

    TODAS = (DIO, DPO, GGO, DIO_DPO, DPO_DIO, GGO_DPO_DIO)


class DivisaoUsuario:
    """Divisão a que cada usuário pertence (o Administrador fica de fora)."""

    SR = "SR"
    GGO = "GGO"
    DPO = "DPO"
    DIO = "DIO"

    TODAS = (SR, GGO, DPO, DIO)
