import os
from atendimentos.models import Atendimento
from agendamentos.services import (
    confirmar_agendamento_pelo_trello,
    recusar_agendamento_pelo_trello,
)
from agendamentos.services import (
    confirmar_agendamento_pelo_trello,
    recusar_agendamento_pelo_trello,
    gerar_retorno_agendamento_para_cliente,
)
import requests


BASE_URL = "https://api.trello.com/1"

LABELS_GERENCIADOS = (
    "PRIORIDADE:",
    "CATEGORIA:",
    "AGENDAMENTO:",
)

STATUS_POR_LISTA_TRELLO = {

    "AGUARDANDO OFICINA": (
        Atendimento.Status.AGUARDANDO_OFICINA
    ),

    "EM ANDAMENTO": (
        Atendimento.Status.EM_ANDAMENTO
    ),

}


def obter_lista_do_card(card_id):
    """
    Consulta no Trello em qual lista
    determinado card está.
    """

    api_key, token = obter_credenciais()

    resposta = requests.get(
        f"{BASE_URL}/cards/{card_id}/list",
        params={
            "key": api_key,
            "token": token,
            "fields": "id,name",
        },
        timeout=15,
    )

    resposta.raise_for_status()

    return resposta.json()


def sincronizar_status_trello_para_django(
    atendimento,
):
    """
    Consulta a lista atual do card no Trello
    e atualiza o status do Atendimento no Django.

    O PostgreSQL mantém estados internos mais
    específicos do que as listas do Trello.
    """

    # =====================================================
    # VERIFICAR SE EXISTE CARD
    # =====================================================

    if not atendimento.trello_card_id:
        return {
            "alterado": False,
            "motivo": "sem_card",
        }

    # =====================================================
    # DESCOBRIR LISTA ATUAL DO CARD
    # =====================================================

    lista = obter_lista_do_card(
        atendimento.trello_card_id
    )

    nome_lista = (
        lista["name"]
        .strip()
        .upper()
    )

    # =====================================================
    # NOVOS
    # =====================================================

    if nome_lista == "NOVOS":

        status_compativeis = {
            Atendimento.Status.NOVO,
            Atendimento.Status.COLETANDO_DADOS,
            Atendimento.Status.AGUARDANDO_CLIENTE,
        }

        # Se o status interno já pertence à etapa NOVOS,
        # preservamos a informação mais específica.
        if atendimento.status in status_compativeis:

            return {
                "alterado": False,
                "motivo": "status_interno_preservado",
                "lista": nome_lista,
                "status": atendimento.status,
            }

        # Se um funcionário moveu um card de outra etapa
        # de volta para NOVOS, consideramos retorno ao início.
        status_anterior = atendimento.status

        atendimento.status = (
            Atendimento.Status.NOVO
        )

        atendimento.save(
            update_fields=[
                "status",
                "atualizado_em",
            ]
        )

        return {
            "alterado": True,
            "lista": nome_lista,
            "status_anterior": status_anterior,
            "status_novo": Atendimento.Status.NOVO,
        }

    # =====================================================
    # AGENDADOS
    # =====================================================

    if nome_lista == "AGENDADOS":

        resultado = (
            confirmar_agendamento_pelo_trello(
                atendimento
            )
        )

        if not resultado["sucesso"]:

            return {
                "alterado": False,
                "motivo": resultado["motivo"],
                "lista": nome_lista,
            }

        retorno_cliente = (
            gerar_retorno_agendamento_para_cliente(
                resultado["agendamento"]
            )
        )

        sincronizar_card_atendimento(
            atendimento
        )

        return {
            "alterado": True,
            "motivo": "agendamento_confirmado",
            "lista": nome_lista,
            "status_anterior": (
                resultado["status_anterior"]
            ),
            "status_novo": (
                resultado["status_novo"]
            ),
            "retorno_cliente": retorno_cliente,
    }

    # =====================================================
    # REAGENDAR
    # =====================================================

   if nome_lista == "REAGENDAR":

        resultado = (
            recusar_agendamento_pelo_trello(
                atendimento
            )
        )

        if not resultado["sucesso"]:

            return {
                "alterado": False,
                "motivo": resultado["motivo"],
                "lista": nome_lista,
            }

        retorno_cliente = (
            gerar_retorno_agendamento_para_cliente(
                resultado["agendamento"]
            )
        )

        sincronizar_card_atendimento(
            atendimento
        )

        return {
            "alterado": True,
            "motivo": "agendamento_recusado",
            "lista": nome_lista,
            "status_anterior": (
                resultado["status_anterior"]
            ),
            "status_novo": (
                resultado["status_novo"]
            ),
            "retorno_cliente": retorno_cliente,
    }

    # =====================================================
    # FINALIZADOS
    # =====================================================

    if nome_lista == "FINALIZADOS":

        status_compativeis = {
            Atendimento.Status.FINALIZADO,
            Atendimento.Status.CANCELADO,
        }

        # Se já está finalizado ou cancelado,
        # não perdemos essa distinção.
        if atendimento.status in status_compativeis:

            return {
                "alterado": False,
                "motivo": "status_interno_preservado",
                "lista": nome_lista,
                "status": atendimento.status,
            }

        status_anterior = atendimento.status

        atendimento.status = (
            Atendimento.Status.FINALIZADO
        )

        atendimento.save(
            update_fields=[
                "status",
                "atualizado_em",
            ]
        )

        return {
            "alterado": True,
            "lista": nome_lista,
            "status_anterior": status_anterior,
            "status_novo": (
                Atendimento.Status.FINALIZADO
            ),
        }

    # =====================================================
    # OUTRAS LISTAS COM RELAÇÃO DIRETA
    # =====================================================

    novo_status = (
        STATUS_POR_LISTA_TRELLO.get(
            nome_lista
        )
    )

    if novo_status is None:

        return {
            "alterado": False,
            "motivo": "lista_desconhecida",
            "lista": nome_lista,
        }

    # =====================================================
    # JÁ ESTÁ SINCRONIZADO
    # =====================================================

    if atendimento.status == novo_status:

        return {
            "alterado": False,
            "motivo": "status_ja_sincronizado",
            "lista": nome_lista,
            "status": novo_status,
        }

    # =====================================================
    # ATUALIZAR DJANGO
    # =====================================================

    status_anterior = atendimento.status

    atendimento.status = novo_status

    atendimento.save(
        update_fields=[
            "status",
            "atualizado_em",
        ]
    )

    return {
        "alterado": True,
        "lista": nome_lista,
        "status_anterior": status_anterior,
        "status_novo": novo_status,
    }

def listar_labels_do_quadro(board_id):
    api_key, token = obter_credenciais()

    resposta = requests.get(
        f"{BASE_URL}/boards/{board_id}/labels",
        params={
            "key": api_key,
            "token": token,
            "fields": "id,name,color",
            "limit": 1000,
        },
        timeout=15,
    )

    resposta.raise_for_status()


    return resposta.json()

def obter_ou_criar_label(
    board_id,
    nome,
    cor,
):
    """
    Procura uma etiqueta pelo nome.

    Se ainda não existir, cria no quadro.
    """

    labels = listar_labels_do_quadro(
        board_id
    )

    nome_procurado = nome.strip().lower()

    for label in labels:
        if (
            label.get("name", "")
            .strip()
            .lower()
            == nome_procurado
        ):
            return label

    api_key, token = obter_credenciais()

    resposta = requests.post(
        f"{BASE_URL}/labels",
        params={
            "key": api_key,
            "token": token,
            "name": nome,
            "color": cor,
            "idBoard": board_id,
        },
        timeout=15,
    )

    resposta.raise_for_status()

    return resposta.json()

def obter_labels_desejados(atendimento):
    """
    Retorna as etiquetas que o atendimento
    deve possuir no Trello.
    """

    labels = []

    # =====================================================
    # PRIORIDADE
    # =====================================================

    cores_prioridade = {
        "alta": "red",
        "normal": "yellow",
        "baixa": "green",
    }

    prioridade = atendimento.prioridade

    if prioridade:
        labels.append(
            {
                "nome": (
                    f"PRIORIDADE: "
                    f"{prioridade.upper()}"
                ),
                "cor": cores_prioridade.get(
                    prioridade,
                    "yellow",
                ),
            }
        )

    # =====================================================
    # CATEGORIA
    # =====================================================

    cores_categoria = {
        "revisao": "blue",
        "oleo": "green",
        "freios": "orange",
        "suspensao": "purple",
        "direcao": "sky",
        "motor": "red",
        "eletrica": "yellow",
        "ar_condicionado": "lime",
        "outro": "black",
    }

    categoria = atendimento.categoria

    if categoria:
        nome_categoria = (
            categoria
            .replace("_", " ")
            .upper()
        )

        labels.append(
            {
                "nome": (
                    f"CATEGORIA: "
                    f"{nome_categoria}"
                ),
                "cor": cores_categoria.get(
                    categoria,
                    "blue",
                ),
            }
        )

    # =====================================================
    # AGENDAMENTO
    # =====================================================

    agendamento = (
        atendimento.agendamentos
        .order_by("-criado_em")
        .first()
    )

    if agendamento:

        if agendamento.status in [
            "solicitado",
            "aguardando_confirmacao",
        ]:
            labels.append(
                {
                    "nome": (
                        "AGENDAMENTO: SOLICITADO"
                    ),
                    "cor": "yellow",
                }
            )

        elif agendamento.status == "confirmado":
            labels.append(
                {
                    "nome": (
                        "AGENDAMENTO: CONFIRMADO"
                    ),
                    "cor": "green",
                }
            )

        elif agendamento.status == "remarcado":
            labels.append(
                {
                    "nome": (
                        "AGENDAMENTO: REMARCADO"
                    ),
                    "cor": "purple",
                }
            )
        elif agendamento.status == "recusado":
            labels.append(
                {
                    "nome": (
                        "AGENDAMENTO: RECUSADO"
                    ),
                    "cor": "red",
                }
            )

    return labels

def obter_card_trello(card_id):
    api_key, token = obter_credenciais()

    resposta = requests.get(
        f"{BASE_URL}/cards/{card_id}",
        params={
            "key": api_key,
            "token": token,
            "fields": "id,name",
            "labels": "all",
            "label_fields": "id,name,color",
        },
        timeout=15,
    )

    resposta.raise_for_status()

    return resposta.json()


def label_eh_gerenciado(nome):
    nome = (nome or "").upper()

    return any(
        nome.startswith(prefixo)
        for prefixo in LABELS_GERENCIADOS
    )


def adicionar_label_ao_card(
    card_id,
    label_id,
):
    api_key, token = obter_credenciais()

    resposta = requests.post(
        f"{BASE_URL}/cards/{card_id}/idLabels",
        params={
            "key": api_key,
            "token": token,
            "value": label_id,
        },
        timeout=15,
    )

    resposta.raise_for_status()


def remover_label_do_card(
    card_id,
    label_id,
):
    api_key, token = obter_credenciais()

    resposta = requests.delete(
        f"{BASE_URL}/cards/"
        f"{card_id}/idLabels/{label_id}",
        params={
            "key": api_key,
            "token": token,
        },
        timeout=15,
    )

    resposta.raise_for_status()

def sincronizar_labels_card(atendimento):
    if not atendimento.trello_card_id:
        return

    board_id = os.getenv(
        "TRELLO_BOARD_ID"
    )

    if not board_id:
        raise ValueError(
            "TRELLO_BOARD_ID não configurado."
        )

    desejados = obter_labels_desejados(
        atendimento
    )

    # Cria/obtém as labels que deveriam existir
    labels_desejados = []

    for item in desejados:
        label = obter_ou_criar_label(
            board_id=board_id,
            nome=item["nome"],
            cor=item["cor"],
        )

        labels_desejados.append(label)

    ids_desejados = {
        label["id"]
        for label in labels_desejados
    }

    # Consulta labels atuais do card
    card = obter_card_trello(
        atendimento.trello_card_id
    )

    labels_atuais = card.get(
        "labels",
        []
    )

    # =====================================================
    # REMOVE APENAS LABELS CONTROLADAS PELO SISTEMA
    # =====================================================

    for label in labels_atuais:

        if not label_eh_gerenciado(
            label.get("name")
        ):
            continue

        if label["id"] not in ids_desejados:

            remover_label_do_card(
                atendimento.trello_card_id,
                label["id"],
            )

    ids_atuais = {
        label["id"]
        for label in labels_atuais
    }

    # =====================================================
    # ADICIONA AS QUE ESTÃO FALTANDO
    # =====================================================

    for label in labels_desejados:

        if label["id"] not in ids_atuais:

            adicionar_label_ao_card(
                atendimento.trello_card_id,
                label["id"],
            )


def obter_credenciais():
    api_key = os.getenv("TRELLO_API_KEY")
    token = os.getenv("TRELLO_TOKEN")

    if not api_key:
        raise ValueError(
            "TRELLO_API_KEY não configurada no .env."
        )

    if not token:
        raise ValueError(
            "TRELLO_TOKEN não configurado no .env."
        )

    return api_key, token


def testar_conexao():
    """
    Testa a autenticação consultando
    o usuário associado ao token.
    """

    api_key, token = obter_credenciais()

    resposta = requests.get(
        f"{BASE_URL}/members/me",
        params={
            "key": api_key,
            "token": token,
        },
        timeout=15,
    )

    resposta.raise_for_status()

    return resposta.json()

def listar_quadros():
    """
    Lista os quadros da conta autenticada.
    """

    api_key, token = obter_credenciais()

    resposta = requests.get(
        f"{BASE_URL}/members/me/boards",
        params={
            "key": api_key,
            "token": token,
            "fields": "id,name,url,closed",
        },
        timeout=15,
    )

    resposta.raise_for_status()

    return resposta.json()


def buscar_quadro_por_nome(nome):
    """
    Procura um quadro pelo nome.
    """

    quadros = listar_quadros()

    nome_procurado = nome.lower().strip()

    for quadro in quadros:

        if quadro["closed"]:
            continue

        if quadro["name"].lower().strip() == nome_procurado:
            return quadro

    return None


def listar_listas_do_quadro(board_id):
    """
    Lista as listas de um quadro do Trello.
    """

    api_key, token = obter_credenciais()

    resposta = requests.get(
        f"{BASE_URL}/boards/{board_id}/lists",
        params={
            "key": api_key,
            "token": token,
            "fields": "id,name,closed,pos",
        },
        timeout=15,
    )

    resposta.raise_for_status()

    return resposta.json()

def buscar_lista_por_nome(
    board_id,
    nome_lista,
):
    """
    Procura uma lista dentro do quadro pelo nome.
    """

    listas = listar_listas_do_quadro(
        board_id
    )

    nome_procurado = (
        nome_lista.lower().strip()
    )

    for lista in listas:

        if lista.get("closed"):
            continue

        if (
            lista["name"].lower().strip()
            == nome_procurado
        ):
            return lista

    return None


def montar_nome_card(atendimento):
    """
    Gera o título do card.
    """

    cliente = atendimento.cliente
    veiculo = atendimento.veiculo

    nome_cliente = (
        cliente.nome
        or cliente.telefone
    )

    if veiculo:
        descricao_veiculo = (
            f"{veiculo.marca} "
            f"{veiculo.modelo}"
        ).strip()

        return (
            f"{nome_cliente} • "
            f"{descricao_veiculo}"
        )

    return nome_cliente


def montar_descricao_card(atendimento):
    """
    Monta a descrição do Atendimento
    que será exibida no Trello.
    """

    cliente = atendimento.cliente
    veiculo = atendimento.veiculo

    partes = []

    # =====================================================
    # CLIENTE
    # =====================================================

    partes.append("## 👤 Cliente")

    partes.append(
        f"**Nome:** "
        f"{cliente.nome or 'Não informado'}"
    )

    partes.append(
        f"**Telefone:** {cliente.telefone}"
    )

    # =====================================================
    # VEÍCULO
    # =====================================================

    partes.append("")
    partes.append("## 🚗 Veículo")

    if veiculo:

        partes.append(
            f"**Marca:** "
            f"{veiculo.marca or 'Não informada'}"
        )

        partes.append(
            f"**Modelo:** {veiculo.modelo}"
        )

        partes.append(
            f"**Ano:** "
            f"{veiculo.ano or 'Não informado'}"
        )

        partes.append(
            f"**Placa:** "
            f"{veiculo.placa or 'Não informada'}"
        )

    else:
        partes.append(
            "Veículo ainda não identificado."
        )

    # =====================================================
    # TRIAGEM
    # =====================================================

    partes.append("")
    partes.append("## 🔧 Triagem")

    partes.append(
        f"**Intenção:** {atendimento.intencao}"
    )

    partes.append(
        f"**Categoria:** {atendimento.categoria}"
    )

    partes.append(
        f"**Prioridade:** {atendimento.prioridade}"
    )

    if atendimento.resumo:

        partes.append("")
        partes.append("**Resumo:**")
        partes.append(
            atendimento.resumo
        )

    # =====================================================
    # SINTOMAS
    # =====================================================

    if atendimento.sintomas:

        partes.append("")
        partes.append("**Sintomas:**")

        for sintoma in atendimento.sintomas:
            partes.append(
                f"- {sintoma}"
            )

    # =====================================================
    # CONDIÇÕES
    # =====================================================

    if atendimento.condicoes:

        partes.append("")
        partes.append(
            "**Condições do problema:**"
        )

        for condicao in atendimento.condicoes:
            partes.append(
                f"- {condicao}"
            )

    # =====================================================
    # TEMPO DO PROBLEMA
    # =====================================================

    if atendimento.tempo_problema:

        partes.append("")

        partes.append(
            f"**Tempo do problema:** "
            f"{atendimento.tempo_problema}"
        )

    # =====================================================
    # AGENDAMENTO
    # =====================================================

    agendamento = (
        atendimento.agendamentos
        .exclude(
            status__in=[
                "cancelado",
                "recusado",
            ]
        )
        .order_by("-criado_em")
        .first()
    )

    if agendamento:

        partes.append("")
        partes.append("## 📅 Agendamento")

        if agendamento.data_solicitada:
            partes.append(
                f"**Data solicitada:** "
                f"{agendamento.data_solicitada.strftime('%d/%m/%Y')}"
            )

        if agendamento.horario_solicitado:
            partes.append(
                f"**Horário solicitado:** "
                f"{agendamento.horario_solicitado.strftime('%H:%M')}"
            )

        if agendamento.periodo_preferido:
            partes.append(
                f"**Período:** "
                f"{agendamento.get_periodo_preferido_display()}"
            )

        partes.append(
            f"**Status:** "
            f"{agendamento.get_status_display()}"
        )

    # =====================================================
    # IDENTIFICADOR INTERNO
    # =====================================================

    partes.append("")
    partes.append("---")

    partes.append(
        f"Atendimento #{atendimento.id}"
    )

    return "\n".join(partes)

def criar_card_atendimento(
    atendimento,
    nome_lista="NOVOS",
):
    """
    Cria um card no Trello para o Atendimento.

    Se o Atendimento já possuir um card,
    não cria outro.
    """

    # =====================================================
    # EVITAR DUPLICAÇÃO
    # =====================================================

    if atendimento.trello_card_id:

        return {
            "id": atendimento.trello_card_id,
            "url": atendimento.trello_card_url,
            "existente": True,
        }

    

    # =====================================================
    # CREDENCIAIS
    # =====================================================

    api_key, token = obter_credenciais()

    board_id = os.getenv(
        "TRELLO_BOARD_ID"
    )

    if not board_id:
        raise ValueError(
            "TRELLO_BOARD_ID não configurado "
            "no .env."
        )

    # =====================================================
    # ENCONTRAR LISTA
    # =====================================================

    lista = buscar_lista_por_nome(
        board_id=board_id,
        nome_lista=nome_lista,
    )

    if lista is None:
        raise ValueError(
            f'Lista "{nome_lista}" '
            "não encontrada no Trello."
        )

    # =====================================================
    # CONTEÚDO
    # =====================================================

    nome = montar_nome_card(
        atendimento
    )

    descricao = montar_descricao_card(
        atendimento
    )

    # =====================================================
    # CRIAR CARD
    # =====================================================

    resposta = requests.post(
        f"{BASE_URL}/cards",
        params={
            "key": api_key,
            "token": token,
        },
        json={
            "idList": lista["id"],
            "name": nome,
            "desc": descricao,
        },
        timeout=15,
    )

    resposta.raise_for_status()

    card = resposta.json()

    # =====================================================
    # SALVAR VÍNCULO COM O TRELLO
    # =====================================================

    atendimento.trello_card_id = card["id"]

    atendimento.trello_card_url = (
        card.get("url", "")
    )

    atendimento.save(
        update_fields=[
            "trello_card_id",
            "trello_card_url",
            "atualizado_em",
        ]
    )

    # =====================================================
    # SINCRONIZAR LABELS
    # =====================================================

    sincronizar_labels_card(
        atendimento
    )

    card["existente"] = False

    return card

def obter_nome_lista_por_status(atendimento):
    """
    Define em qual lista do Trello o atendimento deve ficar.
    """

    mapa = {
        Atendimento.Status.NOVO: "NOVOS",
        Atendimento.Status.COLETANDO_DADOS: "NOVOS",
        Atendimento.Status.AGUARDANDO_CLIENTE: "NOVOS",

        Atendimento.Status.AGUARDANDO_OFICINA: (
            "AGUARDANDO OFICINA"
        ),

        Atendimento.Status.AGENDADO: "AGENDADOS",

        Atendimento.Status.EM_ANDAMENTO: (
            "EM ANDAMENTO"
        ),

        Atendimento.Status.FINALIZADO: "FINALIZADOS",
        Atendimento.Status.CANCELADO: "FINALIZADOS",
    }

    return mapa.get(
        atendimento.status,
        "NOVOS",
    )

def atualizar_card_atendimento(atendimento):
    """
    Atualiza título, descrição e lista de um card
    já existente no Trello.
    """

    if not atendimento.trello_card_id:
        raise ValueError(
            "Esse atendimento ainda não possui "
            "um card no Trello."
        )

    api_key, token = obter_credenciais()

    board_id = os.getenv(
        "TRELLO_BOARD_ID"
    )

    if not board_id:
        raise ValueError(
            "TRELLO_BOARD_ID não configurado."
        )

    nome_lista = obter_nome_lista_por_status(
        atendimento
    )

    lista = buscar_lista_por_nome(
        board_id=board_id,
        nome_lista=nome_lista,
    )

    if lista is None:
        raise ValueError(
            f'Lista "{nome_lista}" não encontrada.'
        )

    nome = montar_nome_card(
        atendimento
    )

    descricao = montar_descricao_card(
        atendimento
    )

    resposta = requests.put(
        f"{BASE_URL}/cards/"
        f"{atendimento.trello_card_id}",
        params={
            "key": api_key,
            "token": token,
        },
        json={
            "name": nome,
            "desc": descricao,
            "idList": lista["id"],
        },
        timeout=15,
    )

    resposta.raise_for_status()

    card = resposta.json()

    sincronizar_labels_card(
        atendimento
    )

    return card

def sincronizar_card_atendimento(atendimento):
    """
    Mantém o Atendimento sincronizado com o Trello.

    Se ainda não houver card:
        cria

    Se já houver:
        atualiza o mesmo card
    """

    if atendimento.trello_card_id:
        return atualizar_card_atendimento(
            atendimento
        )

    nome_lista = obter_nome_lista_por_status(
        atendimento
    )

    return criar_card_atendimento(
        atendimento=atendimento,
        nome_lista=nome_lista,
    )