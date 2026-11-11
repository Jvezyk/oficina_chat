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
    nome_cliente_mencionado: Optional[str]
    sintomas_identificados: list[str]
    condicoes_do_problema: list[str]
    tempo_do_problema: Optional[str]
    dados_suficientes: bool
    proxima_pergunta: Optional[str]
    precisa_humano: bool

    # =====================================================
    # AGENDAMENTO
    # =====================================================

    tipo_data_agendamento: Optional[
        Literal[
            "hoje",
            "amanha",
            "depois_amanha",
            "dia_semana",
            "data_explicita",
        ]
    ]

    dia_semana_agendamento: Optional[
        Literal[
            "segunda",
            "terca",
            "quarta",
            "quinta",
            "sexta",
            "sabado",
            "domingo",
        ]
    ]

    data_explicita_agendamento: Optional[str]

    horario_agendamento_mencionado: Optional[str]

    periodo_agendamento_mencionado: Optional[
        Literal[
            "manha",
            "tarde",
            "noite",
        ]
    ]
