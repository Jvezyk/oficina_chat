from django.db import models

from clientes.models import Cliente, Veiculo
from conversas.models import Conversa


class Atendimento(models.Model):

    class Status(models.TextChoices):
        NOVO = "novo", "Novo"
        COLETANDO_DADOS = "coletando_dados", "Coletando dados"
        AGUARDANDO_CLIENTE = "aguardando_cliente", "Aguardando cliente"
        AGUARDANDO_OFICINA = "aguardando_oficina", "Aguardando oficina"
        AGENDADO = "agendado", "Agendado"
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        FINALIZADO = "finalizado", "Finalizado"
        CANCELADO = "cancelado", "Cancelado"

    class Prioridade(models.TextChoices):
        BAIXA = "baixa", "Baixa"
        NORMAL = "normal", "Normal"
        ALTA = "alta", "Alta"

    class Categoria(models.TextChoices):
        REVISAO = "revisao", "Revisão"
        OLEO = "oleo", "Óleo e filtros"
        FREIOS = "freios", "Freios"
        SUSPENSAO = "suspensao", "Suspensão"
        DIRECAO = "direcao", "Direção"
        MOTOR = "motor", "Motor"
        ELETRICA = "eletrica", "Elétrica"
        AR_CONDICIONADO = "ar_condicionado", "Ar-condicionado"
        ORCAMENTO = "orcamento", "Orçamento"
        OUTRO = "outro", "Outro"

    class Intencao(models.TextChoices):
        SOLICITAR_SERVICO = "solicitar_servico", "Solicitar serviço"
        SOLICITAR_ORCAMENTO = "solicitar_orcamento", "Solicitar orçamento"
        AGENDAR = "agendar", "Agendar"
        CONSULTAR_STATUS = "consultar_status", "Consultar status"
        DUVIDA = "duvida", "Dúvida"
        FALAR_COM_HUMANO = "falar_com_humano", "Falar com humano"
        OUTRO = "outro", "Outro"

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name="atendimentos",
    )

    veiculo = models.ForeignKey(
        Veiculo,
        on_delete=models.PROTECT,
        related_name="atendimentos",
        null=True,
        blank=True,
    )

    conversa = models.ForeignKey(
        Conversa,
        on_delete=models.SET_NULL,
        related_name="atendimentos",
        null=True,
        blank=True,
    )

    categoria = models.CharField(
        max_length=30,
        choices=Categoria.choices,
        default=Categoria.OUTRO,
    )

    intencao = models.CharField(
        max_length=30,
        choices=Intencao.choices,
        default=Intencao.OUTRO,
    )

    resumo = models.TextField(
        blank=True,
    )

    sintomas = models.JSONField(
        default=list,
        blank=True,
    )

    condicoes = models.JSONField(
        default=list,
        blank=True,
    )

    tempo_problema = models.CharField(
        max_length=150,
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.NOVO,
    )

    prioridade = models.CharField(
        max_length=10,
        choices=Prioridade.choices,
        default=Prioridade.NORMAL,
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"Atendimento #{self.id} - {self.cliente}"