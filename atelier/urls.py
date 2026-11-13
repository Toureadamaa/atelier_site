from django.urls import path

from . import views as v

urlpatterns = [
    path("", v.home, name="home"),
    path("katalog/", v.katalog, name="katalog"),
    path("zakaz/<int:pk>/", v.zakaz_detail, name="zakaz_detail"),
    # клиент
    path("moi-zakazy/", v.moi_zakazy, name="moi_zakazy"),
    path("moi-zapisi/", v.moi_zapisi, name="moi_zapisi"),
    path("zapis/<int:pk>/otmena/", v.zapis_delete, name="zapis_delete"),
    # агент приёма
    path("klienty/", v.klienty, name="klienty"),
    path("klienty/novyi/", v.klient_new, name="klient_new"),
    path("klienty/<int:pk>/", v.klient_detail, name="klient_detail"),
    path("klienty/<int:pk>/izmenit/", v.klient_edit, name="klient_edit"),
    path("klienty/<int:pk>/merki/", v.merki_edit, name="merki_edit"),
    path("zakazy/novyi/", v.zakaz_new, name="zakaz_new"),
    path("zapisi/", v.zapisi, name="zapisi"),
    # управляющий
    path("panel/", v.panel, name="panel"),
    path("zakazy/", v.zakazy, name="zakazy"),
    path("modeli/", v.modeli, name="modeli"),
    path("modeli/novaya/", v.model_edit, name="model_new"),
    path("modeli/<int:pk>/", v.model_edit, name="model_edit"),
    path("mastera/", v.mastera, name="mastera"),
    path("mastera/novyi/", v.master_new, name="master_new"),
    path("mastera/<int:pk>/", v.master_edit, name="master_edit"),
    path("sklad/", v.sklad, name="sklad"),
    path("sklad/novyi/", v.material_edit, name="material_new"),
    path("sklad/<int:pk>/", v.material_edit, name="material_edit"),
    path("zakupki/", v.zakupki, name="zakupki"),
    path("zakupki/novaya/", v.zakupka_new, name="zakupka_new"),
    # мастер
    path("moi-zadachi/", v.moi_zadachi, name="moi_zadachi"),
    path("moi-primerki/", v.moi_primerki, name="moi_primerki"),
]
