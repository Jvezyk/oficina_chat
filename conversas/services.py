from django.db import transaction

from atendimentos.models import Atendimento
from atendimentos.services import processar_conversa

from clientes.services import (
    obter_ou_criar_cliente_por_telefone,
    obter_ou_criar_veiculo,
)

from conversas.models import Conversa, Mensagem


# =========================================================
# MENSAGENS
# =========================================================


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


def personalizar_resposta(
    conteudo,
    cliente,
    nome_acabou_de_ser_salvo=False,
    nova_conversa=False,
):
    """
    Personaliza pequenas partes da resposta do bot.

    Regras:
    - Uma conversa nova recebe uma saudação.
    - Cliente já conhecido é chamado pelo primeiro nome.
    - Se o nome acabou de ser informado durante uma conversa
      existente, usamos "Prazer, Nome!".
    - Não repete cumprimentos durante a mesma conversa.
    """

    nome = (cliente.nome or "").strip()

    # -----------------------------------------------------
    # Nova conversa
    # -----------------------------------------------------

    if nova_conversa:

        if nome:
            primeiro_nome = nome.split()[0]

            return (
                f"Olá, {primeiro_nome}! 👋 "
                "Vou te ajudar com seu atendimento. "
                f"{conteudo}"
            )

        return (
            "Olá! 👋 "
            "Vou te ajudar com seu atendimento. "
            f"{conteudo}"
        )

    # -----------------------------------------------------
    # Cliente acabou de informar o nome
    # -----------------------------------------------------

    if nome_acabou_de_ser_salvo and nome:
        primeiro_nome = nome.split()[0]

        return (
            f"Prazer, {primeiro_nome}! 😊 "
            f"{conteudo}"
        )

    # -----------------------------------------------------
    # Resposta normal
    # -----------------------------------------------------

    return conteudo


def salvar_mensagem_bot(
    conversa,
    conteudo,
    cliente,
    nome_acabou_de_ser_salvo=False,
    nova_conversa=False,
):
    """
    Personaliza e salva uma mensagem enviada pelo bot.
    """

    resposta = personalizar_resposta(
        conteudo=conteudo,
        cliente=cliente,
        nome_acabou_de_ser_salvo=nome_acabou_de_ser_salvo,
        nova_conversa=nova_conversa,
    )

    return salvar_mensagem(
        conversa=conversa,
        remetente=Mensagem.Remetente.BOT,
        conteudo=resposta,
    )


# =========================================================
# VEÍCULO
# =========================================================


def gerar_pergunta_veiculo(cliente, analise):
    """
    Define qual pergunta deve ser feita quando ainda
    não foi possível vincular um veículo ao atendimento.
    """

    veiculos = list(
        cliente.veiculos.all()
    )

    # -----------------------------------------------------
    # IA identificou algum veículo na conversa
    # -----------------------------------------------------

    if analise.veiculo_mencionado:

        # Sabemos o veículo, mas ainda não sabemos a placa
        if not analise.placa_mencionada:
            return (
                f"Certo, é um {analise.veiculo_mencionado}. "
                "Pode me informar a placa do veículo?"
            )

        # Temos veículo e placa, mas por algum motivo ele
        # ainda não foi vinculado ao atendimento.
        return (
            f"Entendi. Você informou um "
            f"{analise.veiculo_mencionado}, "
            f"placa {analise.placa_mencionada}. "
            "Ainda preciso validar esse veículo no cadastro."
        )

    # -----------------------------------------------------
    # Cliente não possui veículos cadastrados
    # -----------------------------------------------------

    if len(veiculos) == 0:
        return (
            "Para eu registrar corretamente o atendimento, "
            "qual é o modelo, o ano e a placa do veículo?"
        )

    # -----------------------------------------------------
    # Cliente possui vários veículos
    # -----------------------------------------------------

    if len(veiculos) > 1:

        opcoes = []

        for veiculo in veiculos:

            descricao = (
                f"{veiculo.marca} {veiculo.modelo}"
            ).strip()

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

    # -----------------------------------------------------
    # Cliente possui apenas um veículo
    # -----------------------------------------------------

    # Nesse caso, identificar_veiculo() já pode vincular
    # automaticamente quando for seguro fazer isso.

    return None


# =========================================================
# CONVERSA
# =========================================================


def obter_ou_criar_conversa(
    cliente,
    canal=Conversa.Canal.WHATSAPP,
):
    """
    Procura uma conversa ainda ativa do cliente.

    Conversas ABERTAS ou AGUARDANDO_HUMANO continuam
    sendo utilizadas.

    Conversas FINALIZADAS não são reutilizadas.

    Se nenhuma conversa ativa existir, cria uma nova.
    """

    conversa = (
        Conversa.objects
        .filter(
            cliente=cliente,
            canal=canal,
            status__in=[
                Conversa.Status.ABERTA,
                Conversa.Status.AGUARDANDO_HUMANO,
            ],
        )
        .order_by("-atualizada_em")
        .first()
    )

    # -----------------------------------------------------
    # Existe conversa ativa
    # -----------------------------------------------------

    if conversa:
        return conversa, False

    # -----------------------------------------------------
    # Não existe conversa ativa
    # -----------------------------------------------------

    conversa = Conversa.objects.create(
        cliente=cliente,
        canal=canal,
        status=Conversa.Status.ABERTA,
    )

    return conversa, True


# =========================================================
# MOTOR DA CONVERSA
# =========================================================


@transaction.atomic
def processar_mensagem_cliente(
    conversa,
    conteudo,
    nova_conversa=False,
):
    """
    Processa uma nova mensagem enviada pelo cliente.

    Fluxo:

    1. Salva a mensagem
    2. Analisa todo o histórico com IA
    3. Cria ou atualiza Atendimento
    4. Atualiza nome do cliente
    5. Identifica ou cadastra veículo
    6. Decide a próxima resposta
    """

    # =====================================================
    # 1. SALVAR MENSAGEM DO CLIENTE
    # =====================================================

    mensagem_cliente = salvar_mensagem(
        conversa=conversa,
        remetente=Mensagem.Remetente.CLIENTE,
        conteudo=conteudo,
    )

    # =====================================================
    # 2. ANALISAR CONVERSA
    # =====================================================

    atendimento, analise = processar_conversa(
        conversa
    )

    cliente = conversa.cliente

    # =====================================================
    # 3. NOME DO CLIENTE
    # =====================================================

    nome_acabou_de_ser_salvo = False

    nome_atual = (
        cliente.nome or ""
    ).strip()

    if (
        not nome_atual
        and analise.nome_cliente_mencionado
    ):
        nome = (
            analise.nome_cliente_mencionado
            .strip()
        )

        if nome:

            cliente.nome = nome[:150]

            cliente.save(
                update_fields=[
                    "nome",
                    "atualizado_em",
                ]
            )

            nome_acabou_de_ser_salvo = True

    # -----------------------------------------------------
    # Se ainda não sabemos o nome
    # -----------------------------------------------------

    pergunta_nome = None

    if not (cliente.nome or "").strip():
        pergunta_nome = (
            "Antes de continuarmos, "
            "como posso te chamar?"
        )

    # =====================================================
    # 4. IDENTIFICAR OU CADASTRAR VEÍCULO
    # =====================================================

    situacao_veiculo = None

    if atendimento.veiculo is None:

        veiculo, situacao_veiculo = (
            obter_ou_criar_veiculo(
                cliente=cliente,
                analise=analise,
            )
        )

        if veiculo is not None:

            atendimento.veiculo = veiculo

            atendimento.save(
                update_fields=[
                    "veiculo",
                    "atualizado_em",
                ]
            )

    # =====================================================
    # 5. VERIFICAR SE AINDA FALTA VEÍCULO
    # =====================================================

    pergunta_veiculo = None

    if atendimento.veiculo is None:

        pergunta_veiculo = (
            gerar_pergunta_veiculo(
                cliente=cliente,
                analise=analise,
            )
        )

    mensagem_bot = None

    # =====================================================
    # 6. PLACA INVÁLIDA
    # =====================================================

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

        mensagem_bot = salvar_mensagem_bot(
            conversa=conversa,
            cliente=cliente,
            conteudo=(
                "Não consegui identificar essa placa. "
                "Pode conferir e me informar novamente?"
            ),
            nome_acabou_de_ser_salvo=(
                nome_acabou_de_ser_salvo
            ),
            nova_conversa=nova_conversa,
        )

    # =====================================================
    # 7. CONFLITO DE PLACA
    # =====================================================

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
            Conversa.Status.AGUARDANDO_HUMANO
        )

        conversa.save(
            update_fields=[
                "status",
                "atualizada_em",
            ]
        )

        mensagem_bot = salvar_mensagem_bot(
            conversa=conversa,
            cliente=cliente,
            conteudo=(
                "Encontrei uma inconsistência no cadastro "
                "desse veículo. Vou deixar seu atendimento "
                "com um responsável da oficina para que ele "
                "possa verificar."
            ),
            nome_acabou_de_ser_salvo=(
                nome_acabou_de_ser_salvo
            ),
            nova_conversa=nova_conversa,
        )

    # =====================================================
    # 8. PRECISA DE ATENDIMENTO HUMANO
    # =====================================================

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
            Conversa.Status.AGUARDANDO_HUMANO
        )

        conversa.save(
            update_fields=[
                "status",
                "atualizada_em",
            ]
        )

        mensagem_bot = salvar_mensagem_bot(
            conversa=conversa,
            cliente=cliente,
            conteudo=(
                "Entendi. Vou deixar seu atendimento "
                "com um responsável da oficina para que "
                "ele possa te ajudar melhor."
            ),
            nome_acabou_de_ser_salvo=(
                nome_acabou_de_ser_salvo
            ),
            nova_conversa=nova_conversa,
        )

    # =====================================================
    # 9. FALTA NOME
    # =====================================================

    elif pergunta_nome:

        atendimento.status = (
            Atendimento.Status.COLETANDO_DADOS
        )

        atendimento.save(
            update_fields=[
                "status",
                "atualizado_em",
            ]
        )

        mensagem_bot = salvar_mensagem_bot(
            conversa=conversa,
            cliente=cliente,
            conteudo=pergunta_nome,
            nome_acabou_de_ser_salvo=(
                nome_acabou_de_ser_salvo
            ),
            nova_conversa=nova_conversa,
        )

    # =====================================================
    # 10. FALTA VEÍCULO
    # =====================================================

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

        mensagem_bot = salvar_mensagem_bot(
            conversa=conversa,
            cliente=cliente,
            conteudo=pergunta_veiculo,
            nome_acabou_de_ser_salvo=(
                nome_acabou_de_ser_salvo
            ),
            nova_conversa=nova_conversa,
        )

    # =====================================================
    # 11. FALTAM DADOS TÉCNICOS
    # =====================================================

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

            mensagem_bot = salvar_mensagem_bot(
                conversa=conversa,
                cliente=cliente,
                conteudo=(
                    analise.proxima_pergunta
                ),
                nome_acabou_de_ser_salvo=(
                    nome_acabou_de_ser_salvo
                ),
                nova_conversa=nova_conversa,
            )

    # =====================================================
    # 12. TRIAGEM CONCLUÍDA
    # =====================================================

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

        mensagem_bot = salvar_mensagem_bot(
            conversa=conversa,
            cliente=cliente,
            conteudo=(
                "Perfeito! Já deixei as informações "
                "do seu atendimento registradas para "
                "a equipe da oficina. 👍"
            ),
            nome_acabou_de_ser_salvo=(
                nome_acabou_de_ser_salvo
            ),
            nova_conversa=nova_conversa,
        )

    # =====================================================
    # 13. RETORNO
    # =====================================================

    return {
        "atendimento": atendimento,
        "analise": analise,
        "mensagem_cliente": mensagem_cliente,
        "mensagem_bot": mensagem_bot,
        "situacao_veiculo": situacao_veiculo,
    }


# =========================================================
# PONTO DE ENTRADA
# =========================================================


def receber_mensagem(
    telefone,
    conteudo,
    canal=Conversa.Canal.WHATSAPP,
):
    """
    Ponto de entrada para mensagens externas.

    Futuramente o webhook do WhatsApp chamará essa função.

    Responsabilidades:

    1. Identificar ou criar cliente
    2. Encontrar ou criar conversa
    3. Processar a mensagem
    """

    # =====================================================
    # 1. CLIENTE
    # =====================================================

    cliente, cliente_criado = (
        obter_ou_criar_cliente_por_telefone(
            telefone
        )
    )

    # =====================================================
    # 2. CONVERSA
    # =====================================================

    conversa, conversa_criada = (
        obter_ou_criar_conversa(
            cliente=cliente,
            canal=canal,
        )
    )

    # =====================================================
    # 3. CONVERSA ESTÁ COM ATENDIMENTO HUMANO
    # =====================================================

    if (
        conversa.status
        == Conversa.Status.AGUARDANDO_HUMANO
    ):

        mensagem_cliente = salvar_mensagem(
            conversa=conversa,
            remetente=Mensagem.Remetente.CLIENTE,
            conteudo=conteudo,
        )

        return {
            "cliente": cliente,
            "cliente_criado": cliente_criado,
            "conversa": conversa,
            "conversa_criada": conversa_criada,
            "mensagem_cliente": mensagem_cliente,
            "mensagem_bot": None,
            "atendimento": None,
            "analise": None,
            "situacao_veiculo": None,
        }

    # =====================================================
    # 4. MOTOR NORMAL DA CONVERSA
    # =====================================================

    resultado = processar_mensagem_cliente(
        conversa=conversa,
        conteudo=conteudo,

        # Esse é o ponto importante:
        # só haverá saudação se esta conversa acabou
        # de ser criada.
        nova_conversa=conversa_criada,
    )

    resultado.update({
        "cliente": cliente,
        "cliente_criado": cliente_criado,
        "conversa": conversa,
        "conversa_criada": conversa_criada,
    })

    return resultado