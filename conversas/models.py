from django.db import models
from clientes.models import Cliente


class Conversa(models.Model):

    class Canal(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        SISTEMA = "sistema", "Sistema"

    class Status(models.TextChoices):
        ABERTA = "aberta", "Aberta"
        FINALIZADA = "finalizada", "Finalizada"
        AGUARDANDO_HUMANO = "aguardando_humano", "Aguardando humano"

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="conversas",
    )

    canal = models.CharField(
        max_length=20,
        choices=Canal.choices,
        default=Canal.WHATSAPP,
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.ABERTA,
    )

    identificador_externo = models.CharField(
        max_length=255,
        blank=True,
    )

    iniciada_em = models.DateTimeField(
        auto_now_add=True,
    )

    atualizada_em = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"Conversa #{self.id} - {self.cliente}"

class Mensagem(models.Model):

    class Remetente(models.TextChoices):
        CLIENTE = "cliente", "Cliente"
        BOT = "bot", "Bot"
        FUNCIONARIO = "funcionario", "Funcionário"

    class Tipo(models.TextChoices):
        TEXTO = "texto", "Texto"
        IMAGEM = "imagem", "Imagem"
        AUDIO = "audio", "Áudio"
        DOCUMENTO = "documento", "Documento"
        OUTRO = "outro", "Outro"

    conversa = models.ForeignKey(
        Conversa,
        on_delete=models.CASCADE,
        related_name="mensagens",
    )

    remetente = models.CharField(
        max_length=20,
        choices=Remetente.choices,
    )

    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
        default=Tipo.TEXTO,
    )

    conteudo = models.TextField(
        blank=True,
    )

    identificador_externo = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
    )

    dados_extras = models.JSONField(
        default=dict,
        blank=True,
    )

    criada_em = models.DateTimeField(
        auto_now_add=True,
    )

    processada_por_ia = models.BooleanField(
        default=False,
    )

    def __str__(self):
        return f"{self.get_remetente_display()} - {self.conteudo[:50]}"


   