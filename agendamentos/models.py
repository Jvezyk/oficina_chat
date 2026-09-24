from django.db import models

from atendimentos.models import Atendimento


class Agendamento(models.Model):

    class Status(models.TextChoices):
        SOLICITADO = "solicitado", "Solicitado"
        AGUARDANDO_CONFIRMACAO = (
            "aguardando_confirmacao",
            "Aguardando confirmação",
        )
        CONFIRMADO = "confirmado", "Confirmado"
        REMARCADO = "remarcado", "Remarcado"
        CANCELADO = "cancelado", "Cancelado"
        CONCLUIDO = "concluido", "Concluído"
        RECUSADO = "recusado", "Recusado" 

    class Periodo(models.TextChoices):
        MANHA = "manha", "Manhã"
        TARDE = "tarde", "Tarde"
        NOITE = "noite", "Noite"

    atendimento = models.ForeignKey(
        Atendimento,
        on_delete=models.CASCADE,
        related_name="agendamentos",
    )

    # Data que o cliente gostaria de levar o veículo
    data_solicitada = models.DateField(
        null=True,
        blank=True,
    )

    # Horário exato solicitado, se informado
    horario_solicitado = models.TimeField(
        null=True,
        blank=True,
    )

    # Período preferido, caso não haja horário exato
    periodo_preferido = models.CharField(
        max_length=10,
        choices=Periodo.choices,
        blank=True,
    )

    # Data/hora realmente confirmada pela oficina
    data_hora_confirmada = models.DateTimeField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.SOLICITADO,
    )

    observacoes = models.TextField(
        blank=True,
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
    )

    atualizado_em = models.DateTimeField(
        auto_now=True,
    )

    observacao_retorno = models.TextField(
        blank=True,
    )

    def __str__(self):
        return (
            f"Agendamento #{self.id} - "
            f"Atendimento #{self.atendimento_id}"
        )