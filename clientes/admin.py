from django.contrib import admin
from .models import Cliente, Veiculo


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nome",
        "telefone",
        "email",
        "criado_em",
    )

    search_fields = (
        "nome",
        "telefone",
        "email",
    )


@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "placa",
        "marca",
        "modelo",
        "ano",
        "cliente",
    )

    search_fields = (
        "placa",
        "marca",
        "modelo",
        "cliente__nome",
        "cliente__telefone",
    )

    list_filter = (
        "marca",
        "ano",
    )