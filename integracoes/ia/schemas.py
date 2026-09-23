from typing import Literal, Optional

from pydantic import BaseModel


class AnaliseAtendimento(BaseModel):

    intencao: Literal[
        "solicitar_servico",
        "solicitar_orcamento",
        "agendar",
        "consultar_status",
        "duvida",
        "falar_com_humano",
        "outro",
    ]

    categoria: Literal[
        "revisao",
        "oleo",
        "freios",
        "suspensao",
        "direcao",
        "motor",
        "eletrica",
        "ar_condicionado",
        "outro",
    ]

    prioridade: Literal[
        "baixa",
        "normal",
        "alta",
    ]

    resumo: str

    veiculo_mencionado: Optional[str]

    placa_mencionada: Optional[str]

    sintomas_identificados: list[str]

    condicoes_do_problema: list[str]

    tempo_do_problema: Optional[str]

    dados_suficientes: bool

    proxima_pergunta: Optional[str]

    precisa_humano: bool