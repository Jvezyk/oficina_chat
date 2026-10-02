from datetime import datetime, timedelta
from django.utils import timezone
from agendamentos.models import Agendamento


# =========================================================
# DATA
# =========================================================


def resolver_data_agendamento(
    tipo_data,
    dia_semana=None,
    data_explicita=None,
    data_referencia=None,
):
    """
    Converte a estrutura interpretada pela IA em uma data real.

    A IA classifica a expressão.
    O Django calcula a data.
    """

    if data_referencia is None:
        data_referencia = timezone.localdate()

    # -----------------------------------------------------
    # Hoje
    # -----------------------------------------------------

    if tipo_data == "hoje":
        return data_referencia

    # -----------------------------------------------------
    # Amanhã
    # -----------------------------------------------------

    if tipo_data == "amanha":
        return data_referencia + timedelta(days=1)

    # -----------------------------------------------------
    # Depois de amanhã
    # -----------------------------------------------------

    if tipo_data == "depois_amanha":
        return data_referencia + timedelta(days=2)

    # -----------------------------------------------------
    # Dia da semana
    # -----------------------------------------------------

    if tipo_data == "dia_semana":

        dias_semana = {
            "segunda": 0,
            "terca": 1,
            "quarta": 2,
            "quinta": 3,
            "sexta": 4,
            "sabado": 5,
            "domingo": 6,
        }

        if dia_semana not in dias_semana:
            return None

        dia_desejado = dias_semana[dia_semana]
        dia_atual = data_referencia.weekday()

        diferenca = (
            dia_desejado - dia_atual
        ) % 7

        # Se hoje já for o dia mencionado,
        # consideramos a próxima ocorrência.
        if diferenca == 0:
            diferenca = 7

        return (
            data_referencia
            + timedelta(days=diferenca)
        )

    # -----------------------------------------------------
    # Data explícita
    # -----------------------------------------------------

    if tipo_data == "data_explicita":

        if not data_explicita:
            return None

        formatos = [
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y-%m-%d",
        ]

        for formato in formatos:

            try:
                return datetime.strptime(
                    data_explicita,
                    formato,
                ).date()

            except ValueError:
                continue

    return None


# =========================================================
# HORÁRIO
# =========================================================


def resolver_horario_agendamento(horario):
    """
    Converte o horário estruturado pela IA em datetime.time.

    Exemplo:
    "10:00" -> time(10, 0)
    """

    if not horario:
        return None

    formatos = [
        "%H:%M",
        "%H:%M:%S",
    ]

    for formato in formatos:

        try:
            return datetime.strptime(
                horario,
                formato,
            ).time()

        except ValueError:
            continue

    return None


# =========================================================
# AGENDAMENTO ATIVO
# =========================================================


def buscar_agendamento_ativo(atendimento):
    """
    Procura uma solicitação de agendamento ainda em aberto.

    Assim evitamos criar um novo Agendamento a cada
    mensagem analisada pela IA.
    """

    return (
        atendimento.agendamentos
        .filter(
            status__in=[
                Agendamento.Status.SOLICITADO,
                Agendamento.Status.AGUARDANDO_CONFIRMACAO,
            ]
        )
        .order_by("-criado_em")
        .first()
    )


# =========================================================
# PROCESSAMENTO DA SOLICITAÇÃO
# =========================================================


def processar_solicitacao_agendamento(
    atendimento,
    analise,
):
    """
    Cria ou atualiza uma solicitação de agendamento
    a partir da análise da conversa.

    Nunca confirma disponibilidade automaticamente.

    Retorna:

        agendamento, situacao

    Situações possíveis:

        nao_solicitado
        criado
        atualizado
        existente
        data_invalida
        data_passada
        horario_invalido
    """

    # -----------------------------------------------------
    # Cliente não está tentando agendar
    # -----------------------------------------------------

    if analise.intencao != "agendar":
        return None, "nao_solicitado"

    # -----------------------------------------------------
    # Resolver data
    # -----------------------------------------------------

    data_solicitada = resolver_data_agendamento(
        tipo_data=analise.tipo_data_agendamento,
        dia_semana=analise.dia_semana_agendamento,
        data_explicita=analise.data_explicita_agendamento,
    )

    # Foi informado algum tipo de data,
    # mas não conseguimos interpretá-la.
    if (
        analise.tipo_data_agendamento
        and data_solicitada is None
    ):
        return None, "data_invalida"

    # -----------------------------------------------------
    # Não aceitar data no passado
    # -----------------------------------------------------

    if (
        data_solicitada
        and data_solicitada < timezone.localdate()
    ):
        return None, "data_passada"

    # -----------------------------------------------------
    # Resolver horário
    # -----------------------------------------------------

    horario_solicitado = resolver_horario_agendamento(
        analise.horario_agendamento_mencionado
    )

    if (
        analise.horario_agendamento_mencionado
        and horario_solicitado is None
    ):
        return None, "horario_invalido"

    # -----------------------------------------------------
    # Período
    # -----------------------------------------------------

    periodo_preferido = (
        analise.periodo_agendamento_mencionado
        or ""
    )

    # -----------------------------------------------------
    # Procurar solicitação já existente
    # -----------------------------------------------------

    agendamento = buscar_agendamento_ativo(
        atendimento
    )

    # -----------------------------------------------------
    # Criar solicitação
    # -----------------------------------------------------

    if agendamento is None:

        agendamento = Agendamento.objects.create(
            atendimento=atendimento,
            data_solicitada=data_solicitada,
            horario_solicitado=horario_solicitado,
            periodo_preferido=periodo_preferido,
            status=Agendamento.Status.SOLICITADO,
        )

        return agendamento, "criado"

    # -----------------------------------------------------
    # Atualizar somente informações realmente informadas
    # -----------------------------------------------------

    alterado = False

    if (
        data_solicitada is not None
        and agendamento.data_solicitada
        != data_solicitada
    ):
        agendamento.data_solicitada = (
            data_solicitada
        )
        alterado = True

    # -----------------------------------------------------
    # Atualizar horário/período
    # -----------------------------------------------------

    # O cliente informou um horário exato.
    # Nesse caso, o período anterior deixa de valer.
    if horario_solicitado is not None:

        if (
            agendamento.horario_solicitado
            != horario_solicitado
        ):
            agendamento.horario_solicitado = (
                horario_solicitado
            )
            alterado = True

    if agendamento.periodo_preferido:
        agendamento.periodo_preferido = ""
        alterado = True


    # O cliente informou um período, mas não um horário exato.
    # Ex.: "sexta de manhã".
    elif periodo_preferido:

        if agendamento.horario_solicitado is not None:
            agendamento.horario_solicitado = None
            alterado = True

        if (
            agendamento.periodo_preferido
            != periodo_preferido
        ):
            agendamento.periodo_preferido = (
                periodo_preferido
            )
            alterado = True

    # -----------------------------------------------------
    # Salvar apenas se algo mudou
    # -----------------------------------------------------

    if alterado:

        agendamento.status = (
            Agendamento.Status.SOLICITADO
        )

        agendamento.save()

        return agendamento, "atualizado"

    return agendamento, "existente"

def buscar_agendamento_pendente(atendimento):
    """
    Retorna o agendamento mais recente que ainda
    pode ser aceito ou recusado pela oficina.
    """

    return (
        atendimento.agendamentos
        .filter(
            status__in=[
                Agendamento.Status.SOLICITADO,
                Agendamento.Status.AGUARDANDO_CONFIRMACAO,
                Agendamento.Status.REMARCADO,
            ]
        )
        .order_by("-criado_em")
        .first()
    )


def confirmar_agendamento_pelo_trello(
    atendimento,
):
    """
    Confirma o horário solicitado pelo cliente.

    Só confirma quando existe data E horário exatos.
    """

    agendamento = buscar_agendamento_pendente(
        atendimento
    )

    if not agendamento:
        return {
            "sucesso": False,
            "motivo": "sem_agendamento_pendente",
        }

    if not agendamento.data_solicitada:
        return {
            "sucesso": False,
            "motivo": "sem_data",
            "agendamento": agendamento,
        }

    if not agendamento.horario_solicitado:
        return {
            "sucesso": False,
            "motivo": "sem_horario_exato",
            "agendamento": agendamento,
        }

    data_hora = datetime.combine(
        agendamento.data_solicitada,
        agendamento.horario_solicitado,
    )

    data_hora = timezone.make_aware(
        data_hora,
        timezone.get_current_timezone(),
    )

    agendamento.data_hora_confirmada = data_hora

    agendamento.status = (
        Agendamento.Status.CONFIRMADO
    )

    agendamento.observacao_retorno = (
        "Horário confirmado pela oficina."
    )

    agendamento.save(
        update_fields=[
            "data_hora_confirmada",
            "status",
            "observacao_retorno",
            "atualizado_em",
        ]
    )

    status_anterior = atendimento.status

    atendimento.status = (
        atendimento.Status.AGENDADO
    )

    atendimento.save(
        update_fields=[
            "status",
            "atualizado_em",
        ]
    )

    return {
        "sucesso": True,
        "motivo": "agendamento_confirmado",
        "agendamento": agendamento,
        "status_anterior": status_anterior,
        "status_novo": atendimento.status,
    }


def recusar_agendamento_pelo_trello(
    atendimento,
):
    """
    Registra que a oficina não aceitou
    o horário solicitado.
    """

    agendamento = buscar_agendamento_pendente(
        atendimento
    )

    if not agendamento:
        return {
            "sucesso": False,
            "motivo": "sem_agendamento_pendente",
        }

    agendamento.status = (
        Agendamento.Status.RECUSADO
    )

    agendamento.data_hora_confirmada = None

    agendamento.observacao_retorno = (
        "Horário solicitado não confirmado "
        "pela oficina. É necessário escolher "
        "uma nova opção."
    )

    agendamento.save(
        update_fields=[
            "status",
            "data_hora_confirmada",
            "observacao_retorno",
            "atualizado_em",
        ]
    )

    status_anterior = atendimento.status

    atendimento.status = (
        atendimento.Status.AGUARDANDO_OFICINA
    )

    atendimento.save(
        update_fields=[
            "status",
            "atualizado_em",
        ]
    )

    return {
        "sucesso": True,
        "motivo": "agendamento_recusado",
        "agendamento": agendamento,
        "status_anterior": status_anterior,
        "status_novo": atendimento.status,
    }

def gerar_retorno_agendamento_para_cliente(
    agendamento,
):
    """
    Gera uma mensagem interna de retorno para o cliente
    quando um agendamento é confirmado ou recusado.

    Ainda não envia para o WhatsApp.
    Apenas registra a mensagem no sistema.
    """

    from conversas.models import Mensagem

    atendimento = agendamento.atendimento
    conversa = atendimento.conversa

    # =====================================================
    # PRECISAMOS SABER EM QUAL CONVERSA RESPONDER
    # =====================================================

    if not conversa:
        return {
            "gerado": False,
            "motivo": "sem_conversa",
            "mensagem": None,
        }

    # =====================================================
    # APENAS CONFIRMADO OU RECUSADO GERAM RETORNO
    # =====================================================

    status_permitidos = {
        Agendamento.Status.CONFIRMADO,
        Agendamento.Status.RECUSADO,
    }

    if agendamento.status not in status_permitidos:
        return {
            "gerado": False,
            "motivo": "status_sem_retorno",
            "mensagem": None,
        }

    # =====================================================
    # EVITAR DUPLICAÇÃO
    # =====================================================

    if (
        agendamento.ultimo_status_retorno_gerado
        == agendamento.status
    ):
        return {
            "gerado": False,
            "motivo": "retorno_ja_gerado",
            "mensagem": None,
        }

    # =====================================================
    # AGENDAMENTO CONFIRMADO
    # =====================================================

    if (
        agendamento.status
        == Agendamento.Status.CONFIRMADO
    ):

        if not agendamento.data_hora_confirmada:
            return {
                "gerado": False,
                "motivo": "sem_data_hora_confirmada",
                "mensagem": None,
            }

        data_hora = timezone.localtime(
            agendamento.data_hora_confirmada
        )

        data_formatada = (
            data_hora.strftime("%d/%m/%Y")
        )

        horario_formatado = (
            data_hora.strftime("%H:%M")
        )

        conteudo = (
            f"Seu agendamento foi confirmado para "
            f"{data_formatada} às {horario_formatado}. 👍"
        )

    # =====================================================
    # AGENDAMENTO RECUSADO
    # =====================================================

    else:

        conteudo = (
            "O horário solicitado não pôde ser "
            "confirmado pela oficina. "
            "Você pode me informar outra data "
            "ou horário de preferência?"
        )

    # =====================================================
    # SALVAR MENSAGEM
    # =====================================================

    mensagem = Mensagem.objects.create(
        conversa=conversa,
        remetente=Mensagem.Remetente.BOT,
        tipo=Mensagem.Tipo.TEXTO,
        conteudo=conteudo,
        dados_extras={
            "origem": "agendamento_trello",
            "agendamento_id": agendamento.id,
            "evento": agendamento.status,
        },
        processada_por_ia=False,
    )

    # =====================================================
    # MARCAR RETORNO COMO GERADO
    # =====================================================

    agendamento.ultimo_status_retorno_gerado = (
        agendamento.status
    )

    agendamento.save(
        update_fields=[
            "ultimo_status_retorno_gerado",
            "atualizado_em",
        ]
    )

    return {
        "gerado": True,
        "motivo": "retorno_gerado",
        "mensagem": mensagem,
    }