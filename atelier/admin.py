from django.contrib import admin

# Позиции (составной первичный ключ) админка Django не поддерживает —
# они ведутся на страницах заказа и закупки.
from .models import (Klient, Master, Material, Merki, Model, Primerka, Zadacha, Zakaz,
                     Zakupka, Zapis)

admin.site.site_header = "Швейное ателье — администрирование"
admin.site.site_title = "Ателье"


class ZadachaInline(admin.TabularInline):
    model = Zadacha
    extra = 0


class PrimerkaInline(admin.TabularInline):
    model = Primerka
    extra = 0


@admin.register(Klient)
class KlientAdmin(admin.ModelAdmin):
    list_display = ["id", "fio", "telefon", "email", "data_registracii"]
    search_fields = ["fio", "telefon", "email"]


@admin.register(Model)
class ModelAdmin(admin.ModelAdmin):
    list_display = ["id", "nazvanie", "kategoriya", "cena"]
    list_filter = ["kategoriya"]
    search_fields = ["nazvanie"]


@admin.register(Zakaz)
class ZakazAdmin(admin.ModelAdmin):
    list_display = ["id", "klient", "model", "data_oformleniya", "data_zaversheniya",
                    "stoimost", "status"]
    list_filter = ["status", "data_oformleniya"]
    search_fields = ["klient__fio", "model__nazvanie"]
    inlines = [ZadachaInline, PrimerkaInline]


@admin.register(Zapis)
class ZapisAdmin(admin.ModelAdmin):
    list_display = ["id", "klient", "data", "vremya", "tip_zapisi"]
    list_filter = ["tip_zapisi", "data"]


@admin.register(Merki)
class MerkiAdmin(admin.ModelAdmin):
    list_display = ["id", "klient", "grud", "taliya", "bedra", "data_snyatiya"]


@admin.register(Master)
class MasterAdmin(admin.ModelAdmin):
    list_display = ["id", "fio", "dolzhnost", "stazh", "nomer_telefona", "rabotaet"]
    list_filter = ["dolzhnost", "rabotaet"]


@admin.register(Zadacha)
class ZadachaAdmin(admin.ModelAdmin):
    list_display = ["id", "zakaz", "master", "opisanie", "data_naznacheniya", "status"]
    list_filter = ["status", "master"]


@admin.register(Primerka)
class PrimerkaAdmin(admin.ModelAdmin):
    list_display = ["id", "zakaz", "data", "vremya", "master"]


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ["id", "nazvanie", "tip", "ostatok", "edinica_izmereniya"]
    list_filter = ["tip"]
    readonly_fields = ["ostatok"]  # остаток меняется только закупками и заказами


@admin.register(Zakupka)
class ZakupkaAdmin(admin.ModelAdmin):
    list_display = ["id", "data", "postavshik"]
