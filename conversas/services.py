from django.db import transaction

from atendimentos.models import Atendimento
from atendimentos.services import processar_conversa
from conversas.models import Mensagem


def salvar_mensagem(
    conversa,
    remetente,
    conteudo,
    tipo=Mensagem.Tipo.TEXTO,
):
    """
    Salva uma mensagem no histórico da conversa.
    """

    return Mensagem.objects.create(
        conversa=conversa,
        remetente=remetente,
        tipo=tipo,
        conteudo=conteudo,
    )


@transaction.atomic
def processar_mensagem_cliente(conversa, conteudo):
    """
    Processa uma nova mensagem enviada pelo cliente.

    Fluxo:
        1. Salva mensagem do cliente
        2. Analisa a conversa inteira
        3. Cria/atualiza Atendimento
        4. Decide se precisa fazer outra pergunta
        5. Salva a resposta do bot

    Retorna:
        atendimento
        analise
        mensagem_cliente
        mensagem_bot
    """

    # ---------------------------------------------------------
    # 1. Salvar a mensagem recebida
    # ---------------------------------------------------------

    mensagem_cliente = salvar_mensagem(
        conversa=conversa,
        remetente=Mensagem.Remetente.CLIENTE,
        conteudo=conteudo,
    )

    # ---------------------------------------------------------
    # 2. IA analisa conversa e Atendimento é atualizado
    # ---------------------------------------------------------

    atendimento, analise = processar_conversa(
        conversa
    )

    pergunta_veiculo = None

    if atendimento.veiculo is None:
        pergunta_veiculo = gerar_pergunta_veiculo(
            cliente=conversa.cliente,
            analise=analise,
        )
    

    mensagem_bot = None

    # ---------------------------------------------------------
    # 3. Situação precisa de uma pessoa
    # ---------------------------------------------------------

    if analise.precisa_humano:

        atendimento.status = (
            Atendimento.Status.AGUARDANDO_OFICINA
        )

        atendimento.save(
            update_fields=[
                "status",
                "atualizado_em",
            ]
        )

        conversa.status = (
            conversa.Status.AGUARDANDO_HUMANO
        )

        conversa.save(
            update_fields=[
                "status",
                "atualizada_em",
            ]
        )

        resposta = (
            "Entendi. Vou encaminhar sua solicitação "
            "para um responsável da oficina."
        )

        mensagem_bot = salvar_mensagem(
            conversa=conversa,
            remetente=Mensagem.Remetente.BOT,
            conteudo=resposta,
        )

    # ---------------------------------------------------------
    # 4. Ainda faltam informações
    # ---------------------------------------------------------

    elif pergunta_veiculo:

        atendimento.status = (
            Atendimento.Status.COLETANDO_DADOS
        )

        atendimento.save(
            update_fields=[
                "status",
                "atualizado_em",
            ]
        )

        mensagem_bot = salvar_mensagem(
            conversa=conversa,
            remetente=Mensagem.Remetente.BOT,
            conteudo=pergunta_veiculo,
    )


    elif not analise.dados_suficientes:

        atendimento.status = (
            Atendimento.Status.COLETANDO_DADOS
        )

        atendimento.save(
            update_fields=[
                "status",
                "atualizado_em",
            ]
        )

        if analise.proxima_pergunta:

            mensagem_bot = salvar_mensagem(
                conversa=conversa,
                remetente=Mensagem.Remetente.BOT,
                conteudo=analise.proxima_pergunta,
            )

    # ---------------------------------------------------------
    # 5. Triagem concluída
    # ---------------------------------------------------------

    else:

        atendimento.status = (
            Atendimento.Status.AGUARDANDO_OFICINA
        )

        atendimento.save(
            update_fields=[
                "status",
                "atualizado_em",
            ]
        )

        resposta = (
            "Perfeito! Já registrei as informações "
            "do seu atendimento para a oficina."
        )

        mensagem_bot = salvar_mensagem(
            conversa=conversa,
            remetente=Mensagem.Remetente.BOT,
            conteudo=resposta,
        )

    # ---------------------------------------------------------
    # 6. Retorno
    # ---------------------------------------------------------

    return {
        "atendimento": atendimento,
        "analise": analise,
        "mensagem_cliente": mensagem_cliente,
        "mensagem_bot": mensagem_bot,
    }

def gerar_pergunta_veiculo(cliente, analise):
    """
    Define qual pergunta deve ser feita para identificar
    corretamente o veículo relacionado ao atendimento.

    Regras:
    - Se a IA mencionou um veículo, mas ele ainda não foi
      vinculado ao atendimento, pedimos a placa.
    - Se a IA já mencionou veículo e placa, mas o veículo
      não existe no cadastro, informamos que ele precisa
      ser cadastrado.
    - Se o cliente não possui veículos cadastrados,
      perguntamos modelo e ano.
    - Se possui vários veículos, pedimos para escolher.
    - Se possui apenas um veículo e nada foi mencionado,
      não é necessário perguntar.
    """

    veiculos = list(cliente.veiculos.all())

    # ---------------------------------------------------------
    # 1. A IA identificou um veículo na conversa
    # ---------------------------------------------------------

    if analise.veiculo_mencionado:

        # Sabemos o veículo, mas ainda não sabemos a placa
        if not analise.placa_mencionada:
            return (
                f"Certo, é um {analise.veiculo_mencionado}. "
                "Pode me informar a placa do veículo?"
            )

        # Temos veículo + placa, mas ele ainda não foi
        # encontrado/vinculado no cadastro.
        return (
            f"Entendi. Você informou um "
            f"{analise.veiculo_mencionado}, "
            f"placa {analise.placa_mencionada}. "
            "Esse veículo ainda não está cadastrado no sistema."
        )

    # ---------------------------------------------------------
    # 2. Cliente ainda não possui veículo cadastrado
    # ---------------------------------------------------------

    if len(veiculos) == 0:
        return (
            "Para eu registrar corretamente o atendimento, "
            "qual é o modelo, o ano e a placa do veículo?"
        )

    # ---------------------------------------------------------
    # 3. Cliente possui vários veículos cadastrados
    # ---------------------------------------------------------

    if len(veiculos) > 1:

        opcoes = []

        for veiculo in veiculos:
            descricao = f"{veiculo.marca} {veiculo.modelo}"

            if veiculo.ano:
                descricao += f" {veiculo.ano}"

            if veiculo.placa:
                descricao += f" - {veiculo.placa}"

            opcoes.append(descricao)

        lista_veiculos = ", ".join(opcoes)

        return (
            "Para eu registrar corretamente, "
            f"é sobre qual veículo: {lista_veiculos}?"
        )

    # ---------------------------------------------------------
    # 4. Cliente possui apenas um veículo cadastrado
    # ---------------------------------------------------------

    # Nesse caso não precisamos perguntar nada.
    # O identificar_veiculo() pode usar esse veículo,
    # desde que a conversa não mencione outro diferente.

    return None