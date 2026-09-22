from django.db import models


class Cliente(models.Model):
    nome = models.CharField(
        max_length=150,
        blank=True
    )

    telefone = models.CharField(
        max_length=20,
        unique=True
    )

    email = models.EmailField(
        blank=True
    )

    observacoes = models.TextField(
        blank=True
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    atualizado_em = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.nome or self.telefone

class Veiculo(models.Model):
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="veiculos"
    )

    # placa = models.CharField(
    #     max_length=10,
    #     unique=True
    # )
    
    marca = models.CharField(
        max_length=50,
        blank=True
    )

    modelo = models.CharField(
        max_length=100
    )

    ano = models.PositiveSmallIntegerField(
        null=True,
        blank=True
    )

    quilometragem = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    observacoes = models.TextField(
        blank=True
    )

    criado_em = models.DateTimeField(
        auto_now_add=True
    )

    atualizado_em = models.DateTimeField(
        auto_now=True
    )

def __str__(self):
    return f"{self.modelo} - {self.placa}"