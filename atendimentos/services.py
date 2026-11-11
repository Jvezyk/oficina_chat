from atendimentos.models import Atendimento
from integracoes.ia.services import analisar_conversa


def normalizar_placa(placa):
    """
    Remove espaços e hífens e transforma a placa em maiúsculo.

    Exemplos:
    ABC-1D23 -> ABC1D23
    abc1d23  -> ABC1D23
    """
    if not placa:
        return None

    return (
        placa
        .replace("-", "")
        .replace(" ", "")
        .upper()
    )


def identificar_veiculo(cliente, analise):
    """
    Tenta identificar qual veículo do cliente está sendo mencionado
    na conversa.

    Ordem de confiança:
    1. Placa
    2. Modelo/marca mencionados
    3. Único veículo cadastrado do cliente

    Se houver dúvida, retorna None.
    """

    veiculos = list(cliente.veiculos.all())

    # ---------------------------------------------------------
    # 1. Tentar identificar pela placa
    # ---------------------------------------------------------

    if analise.placa_mencionada:

        placa_mencionada = normalizar_placa(
            analise.placa_mencionada
        )

        for veiculo in veiculos:

            if not veiculo.placa:
                continue

            placa_banco = normalizar_placa(
                veiculo.placa
            )

            if placa_banco == placa_mencionada:
                return veiculo

    # ---------------------------------------------------------
    # 2. Tentar identificar pelo veículo mencionado pela IA
    # ---------------------------------------------------------

    if analise.veiculo_mencionado:

        mencionado = (
            analise.veiculo_mencionado
            .lower()
            .strip()
        )

        correspondencias = []

        for veiculo in veiculos:

            modelo = (
                veiculo.modelo
                .lower()
                .strip()
                if veiculo.modelo
                else ""
            )

            marca = (
                veiculo.marca
                .lower()
                .strip()
                if veiculo.marca
                else ""
            )

            encontrou = False

            # Exemplo:
            # modelo = "corolla"
            # mencionado = "toyota corolla 2020"

            if modelo and modelo in mencionado:
                encontrou = True

            # Também aceita caso o texto seja mais curto
            elif modelo and mencionado in modelo:
                encontrou = True

            # Marca ajuda como informação complementar.
            # Só tomamos cuidado porque um cliente pode ter
            # vários veículos da mesma marca.
            elif marca and marca in mencionado:
                encontrou = True

            if encontrou:
                correspondencias.append(veiculo)

        # Só escolhemos automaticamente se houver UMA
        # correspondência inequívoca.
        if len(correspondencias) == 1:
            return correspondencias[0]

    # ---------------------------------------------------------
    # 3. Se o cliente só possui um veículo
    # ---------------------------------------------------------


    if (
        len(veiculos) == 1
        and not analise.veiculo_mencionado
        and not analise.placa_mencionada
    ):
        return veiculos[0]

    return None
    # ---------------------------------------------------------
    # Não foi possível determinar com segurança
    # ---------------------------------------------------------

    return None


def buscar_atendimento_da_conversa(conversa):
    """
    Procura um atendimento já relacionado à conversa.

    Se a conversa continuar evoluindo, queremos atualizar o mesmo
    atendimento em vez de criar um novo a cada mensagem.
    """

    return Atendimento.objects.filter(
        conversa=conversa
    ).first()


def processar_conversa(conversa):
    """
    Analisa a conversa usando IA e cria ou atualiza
    um Atendimento.

    Fluxo:

        Conversa
            ↓
        OpenAI
            ↓
        AnaliseAtendimento
            ↓
        validações Django
            ↓
        Atendimento
            ↓
        PostgreSQL

    Retorna:
        atendimento, analise
    """

    # ---------------------------------------------------------
    # 1. A IA analisa a conversa
    # ---------------------------------------------------------

    analise = analisar_conversa(conversa)

    # ---------------------------------------------------------
    # 2. Cliente vem diretamente do banco
    # ---------------------------------------------------------

    cliente = conversa.cliente

    # ---------------------------------------------------------
    # 3. Tentamos identificar o veículo
    # ---------------------------------------------------------

    veiculo = identificar_veiculo(
        cliente=cliente,
        analise=analise,
    )

    # ---------------------------------------------------------
    # 4. Verificamos se já existe atendimento nessa conversa
    # ---------------------------------------------------------

    atendimento = buscar_atendimento_da_conversa(
        conversa
    )

    # ---------------------------------------------------------
    # 5. Caso ainda não exista, criamos o objeto
    # ---------------------------------------------------------

    if atendimento is None:

        atendimento = Atendimento(
            cliente=cliente,
            conversa=conversa,
        )

    # ---------------------------------------------------------
    # 6. Atualizamos os dados vindos da análise
    # ---------------------------------------------------------

    atendimento.intencao = analise.intencao

    atendimento.categoria = analise.categoria

    atendimento.prioridade = analise.prioridade

    atendimento.resumo = analise.resumo

    atendimento.sintomas = (
        analise.sintomas_identificados
    )

    atendimento.condicoes = (
        analise.condicoes_do_problema
    )

    atendimento.tempo_problema = (
        analise.tempo_do_problema or ""
    )

    # ---------------------------------------------------------
    # 7. Só substituímos o veículo se encontramos um
    # ---------------------------------------------------------

    if veiculo is not None:
        atendimento.veiculo = veiculo

    # ---------------------------------------------------------
    # 8. Salva no PostgreSQL
    # ---------------------------------------------------------

    atendimento.save()

    # ---------------------------------------------------------
    # 9. Retornamos os dois objetos
    # ---------------------------------------------------------

    return atendimento, analise