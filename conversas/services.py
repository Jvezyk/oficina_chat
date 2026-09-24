from django.db import transaction

from atendimentos.models import Atendimento
from atendimentos.services import processar_conversa
from clientes.services import obter_ou_criar_veiculo
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


def gerar_pergunta_veiculo(cliente, analise):
    """
    Define qual pergunta deve ser feita para identificar
    corretamente o veículo relacionado ao atendimento.
    """

    veiculos = list(cliente.veiculos.all())

    # A IA identificou um veículo
    if analise.veiculo_mencionado:

        # Sabemos o veículo, mas ainda não sabemos a placa
        if not analise.placa_mencionada:
            return (
                f"Certo, é um {analise.veiculo_mencionado}. "
                "Pode me informar a placa do veículo?"
            )

        # Temos veículo e placa, mas ele ainda não foi
        # vinculado ao atendimento
        return (
            f"Entendi. Você informou um "
            f"{analise.veiculo_mencionado}, "
            f"placa {analise.placa_mencionada}. "
            "Ainda preciso validar esse veículo no cadastro."
        )

    # Cliente não possui veículo cadastrado
    if len(veiculos) == 0:
        return (
            "Para eu registrar corretamente o atendimento, "
            "qual é o modelo, o ano e a placa do veículo?"
        )

    # Cliente possui vários veículos
    if len(veiculos) > 1:

        opcoes = []

        for veiculo in veiculos:
            descricao = f"{veiculo.marca} {veiculo.modelo}".strip()

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

    return None


@transaction.atomic
def processar_mensagem_cliente(conversa, conteudo):
    """
    Processa uma nova mensagem enviada pelo cliente.

    Fluxo:
    1. Salva mensagem
    2. Analisa conversa
    3. Cria/atualiza atendimento
    4. Tenta identificar ou cadastrar veículo
    5. Decide a próxima resposta
    """

    # ---------------------------------------------------------
    # 1. Salvar mensagem do cliente
    # ---------------------------------------------------------

    mensagem_cliente = salvar_mensagem(
        conversa=conversa,
        remetente=Mensagem.Remetente.CLIENTE,
        conteudo=conteudo,
    )

    # ---------------------------------------------------------
    # 2. IA analisa conversa e atualiza atendimento
    # ---------------------------------------------------------

    atendimento, analise = processar_conversa(
        conversa
    )

    # ---------------------------------------------------------
    # 3. Tentar identificar ou cadastrar veículo
    # ---------------------------------------------------------

    situacao_veiculo = None

    if atendimento.veiculo is None:

        veiculo, situacao_veiculo = obter_ou_criar_veiculo(
            cliente=conversa.cliente,
            analise=analise,
        )

        if veiculo is not None:

            atendimento.veiculo = veiculo

            atendimento.save(
                update_fields=[
                    "veiculo",
                    "atualizado_em",
                ]
            )

    # ---------------------------------------------------------
    # 4. Se ainda não temos veículo, descobrir o que perguntar
    # ---------------------------------------------------------

    pergunta_veiculo = None

    if atendimento.veiculo is None:

        pergunta_veiculo = gerar_pergunta_veiculo(
            cliente=conversa.cliente,
            analise=analise,
        )

    mensagem_bot = None

    # ---------------------------------------------------------
    # 5. Placa inválida
    # ---------------------------------------------------------

    if situacao_veiculo == "placa_invalida":

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
            conteudo=(
                "Não consegui identificar essa placa. "
                "Pode conferir e me informar novamente?"
            ),
        )

    # ---------------------------------------------------------
    # 6. Placa pertence a outro cliente
    # ---------------------------------------------------------

    elif situacao_veiculo == "conflito":

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

        mensagem_bot = salvar_mensagem(
            conversa=conversa,
            remetente=Mensagem.Remetente.BOT,
            conteudo=(
                "Encontrei uma inconsistência no cadastro "
                "desse veículo. Vou encaminhar para um "
                "responsável da oficina verificar."
            ),
        )

    # ---------------------------------------------------------
    # 7. IA determinou necessidade de humano
    # ---------------------------------------------------------

    elif analise.precisa_humano:

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

        mensagem_bot = salvar_mensagem(
            conversa=conversa,
            remetente=Mensagem.Remetente.BOT,
            conteudo=(
                "Entendi. Vou encaminhar sua solicitação "
                "para um responsável da oficina."
            ),
        )

    # ---------------------------------------------------------
    # 8. Ainda falta identificar veículo
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

    # ---------------------------------------------------------
    # 9. Ainda faltam dados técnicos
    # ---------------------------------------------------------

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
    # 10. Triagem concluída
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

        mensagem_bot = salvar_mensagem(
            conversa=conversa,
            remetente=Mensagem.Remetente.BOT,
            conteudo=(
                "Perfeito! Já registrei as informações "
                "do seu atendimento para a oficina."
            ),
        )

    # ---------------------------------------------------------
    # 11. Retorno
    # ---------------------------------------------------------

    return {
        "atendimento": atendimento,
        "analise": analise,
        "mensagem_cliente": mensagem_cliente,
        "mensagem_bot": mensagem_bot,
        "situacao_veiculo": situacao_veiculo,
    }