import re

from clientes.models import Veiculo


def normalizar_placa(placa):
    """
    Normaliza a placa removendo espaços e hífens.

    Exemplos:
    ABC-1234 -> ABC1234
    abc1d23  -> ABC1D23
    """

    if not placa:
        return None

    return (
        placa
        .replace("-", "")
        .replace(" ", "")
        .upper()
        .strip()
    )


def placa_valida(placa):
    """
    Aceita os dois formatos brasileiros:

    Antigo:
    ABC1234

    Mercosul:
    ABC1D23
    """

    placa = normalizar_placa(placa)

    if not placa:
        return False

    padrao_antigo = r"^[A-Z]{3}[0-9]{4}$"
    padrao_mercosul = r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$"

    return bool(
        re.match(padrao_antigo, placa)
        or re.match(padrao_mercosul, placa)
    )


def buscar_veiculo_por_placa(placa):
    """
    Procura um veículo comparando placas normalizadas.

    Fazemos assim porque algum registro antigo pode estar salvo
    como ABC-1234 e outro pode chegar como ABC1234.
    """

    placa_normalizada = normalizar_placa(placa)

    if not placa_normalizada:
        return None

    veiculos = Veiculo.objects.exclude(
        placa__isnull=True
    ).exclude(
        placa=""
    )

    for veiculo in veiculos:

        if normalizar_placa(veiculo.placa) == placa_normalizada:
            return veiculo

    return None


def extrair_ano_veiculo(texto):
    """
    Procura um ano dentro do texto retornado pela IA.

    Exemplo:
    'Corolla XEI 2012' -> 2012
    """

    if not texto:
        return None

    resultado = re.search(
        r"\b(19|20)\d{2}\b",
        texto
    )

    if resultado:
        return int(resultado.group())

    return None


def extrair_modelo_veiculo(texto):
    """
    Remove o ano da descrição para usá-la como modelo.

    'Corolla XEI 2012' -> 'Corolla XEI'
    """

    if not texto:
        return ""

    modelo = re.sub(
        r"\b(19|20)\d{2}\b",
        "",
        texto
    )

    return " ".join(modelo.split())


def obter_ou_criar_veiculo(cliente, analise):
    """
    Tenta obter ou cadastrar o veículo informado durante
    a conversa.

    Retorna:

        veiculo, situacao

    Situações possíveis:
        existente
        criado
        incompleto
        placa_invalida
        conflito
    """

    placa = analise.placa_mencionada
    veiculo_mencionado = analise.veiculo_mencionado

    # Ainda faltam informações
    if not placa or not veiculo_mencionado:
        return None, "incompleto"

    # Validação da placa
    if not placa_valida(placa):
        return None, "placa_invalida"

    placa = normalizar_placa(placa)

    # ---------------------------------------------------------
    # Verificar se essa placa já existe
    # ---------------------------------------------------------

    veiculo_existente = buscar_veiculo_por_placa(
        placa
    )

    if veiculo_existente:

        # O veículo já pertence ao mesmo cliente
        if veiculo_existente.cliente_id == cliente.id:
            return veiculo_existente, "existente"

        # A mesma placa está ligada a outra pessoa.
        # Não fazemos nenhuma alteração automaticamente.
        return None, "conflito"

    # ---------------------------------------------------------
    # Criar veículo novo
    # ---------------------------------------------------------

    ano = extrair_ano_veiculo(
        veiculo_mencionado
    )

    modelo = extrair_modelo_veiculo(
        veiculo_mencionado
    )

    veiculo = Veiculo.objects.create(
        cliente=cliente,
        placa=placa,
        modelo=modelo,
        ano=ano,
    )

    return veiculo, "criado"