import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from . import forms as f
from .models import (Klient, Master, Material, Merki, Model, PoziciyaZakupki, Primerka,
                     Zadacha, Zakaz, Zakupka, Zapis)
from .roles import AGENT, KLIENT, MASTER, UPRAVLYAYUSHII, est_rol, rol_required

PERSONAL = (AGENT, UPRAVLYAYUSHII)


def form_page(request, form, title, back=None, extra=None):
    """Общая страница с одной формой."""
    ctx = {"form": form, "title": title, "back": back}
    ctx.update(extra or {})
    return render(request, "atelier/form.html", ctx)


def soobshenie_bd(e):
    """Сообщение SQL Server без технических приставок драйвера ODBC.

    Драйвер склеивает все сообщения сервера:
        «[SQL Server]текст (номер) (SQLExecDirectW); [SQL Server]текст (номер)».
    Если триггер вывел свой текст (print — номер 0, raiserror — номер 50000),
    показываем его: он понятнее служебного «Транзакция завершилась в триггере» (3609).
    """
    t = e.args[1] if len(e.args) > 1 and isinstance(e.args[1], str) else str(e)
    chasti = re.findall(r"\[SQL Server\](.*?)\s\((\d+)\)(?=\s*\(SQL|\s*;|\s*$)", t, flags=re.S)
    for tekst, nomer in chasti:
        if nomer in ("0", "50000"):
            return tekst.strip()
    if chasti:
        return chasti[0][0].strip()
    return t.strip(" '\")")


# Понятные сообщения вместо технического текста SQL Server.
# Имя ограничения в базе → (поле формы, под которым показать сообщение; текст).
POYASNENIYA = {
    "uq_клиент_телефон": ("telefon", "Клиент с таким номером телефона уже существует."),
    "uq_клиент_email": ("email", "Клиент с таким e-mail уже существует."),
    "uq_мастер_телефон": ("nomer_telefona", "Мастер с таким номером телефона уже существует."),
    "uq_запись_клиент_время": (None, "У клиента уже есть запись на это время."),
    "ck_заказ_датаоформления": ("data_oformleniya", "Дата оформления не может быть в будущем."),
    "ck_заказ_даты": ("data_zaversheniya", "Дата завершения не может быть раньше даты оформления."),
    "ck_заказ_стоимость": ("stoimost", "Стоимость заказа должна быть больше 0."),
    "ck_модель_цена": ("cena", "Цена модели должна быть больше 0."),
    "ck_модель_категория": ("kategoriya", "Такой категории нет в списке."),
    "ck_модель_описание": ("opisanie", "Укажите описание модели."),
    "ck_мерки_значения": (None, "Грудь, талия и бёдра должны быть больше 0."),
    "ck_материал_остаток": (None, "Остаток материала на складе не может быть отрицательным."),
    "ck_материал_единица": ("edinica_izmereniya", "Такой единицы измерения нет в списке."),
    "ck_позициязаказа_количество": ("kolichestvo", "Количество должно быть не меньше 1."),
    "ck_позициязакупки_количество": (None, "Количество в закупке должно быть не меньше 1."),
    "ck_мастер_должность": ("dolzhnost", "Такой должности нет в списке."),
    "ck_запись_тип": ("tip_zapisi", "Такого типа записи нет в списке."),
    "ck_запись_дата_время": (None, "Дата и время записи не могут быть в прошлом."),
    "ck_запись_дата": (None, "Дата записи не может быть в прошлом."),
}


def poyasnenie_bd(e):
    """Что показать пользователю, если SQL Server отклонил данные: (поле формы или None, текст)."""
    t = soobshenie_bd(e)
    for imya, (pole, tekst) in POYASNENIYA.items():
        if f'"{imya}"' in t.lower():          # SQL Server пишет имя ограничения в кавычках
            return pole, tekst
    if t.lower().startswith("ошибка:"):      # текст из триггера: print / raiserror
        t = t[len("ошибка:"):].strip()
        return None, t[:1].upper() + t[1:]
    return None, "База данных отклонила изменение: " + t


def save_or_error(form, posle=None):
    """Сохраняет форму в базу данных.

    Все правила п. 3.3 проверяет SQL Server. Если ограничение (CHECK, UNIQUE)
    или триггер отклоняет данные, транзакция отменяется, а сообщение базы
    показывается над формой. Возвращает сохранённый объект или None.
    posle(obj) — действие в той же транзакции (например, создать учётную запись).
    """
    try:
        with transaction.atomic():
            obj = form.save()
            if posle:
                posle(obj)
            return obj
    except ValidationError as e:
        form.add_error(None, e)
    except DatabaseError as e:
        pole, tekst = poyasnenie_bd(e)
        form.add_error(pole if pole in form.fields else None, tekst)
    return None


# ---------------------------------------------------------------------------
# Общие страницы
# ---------------------------------------------------------------------------
@login_required
def home(request):
    u = request.user
    if est_rol(u, UPRAVLYAYUSHII):
        return redirect("panel")
    if est_rol(u, AGENT):
        return redirect("klienty")
    if est_rol(u, MASTER):
        return redirect("moi_zadachi")
    if est_rol(u, KLIENT):
        return redirect("moi_zakazy")
    return redirect("katalog")


def katalog(request):
    kategoriya = request.GET.get("kategoriya", "")
    vse = Model.objects.all()
    counts = dict(vse.values_list("kategoriya").annotate(n=Count("id")))
    modeli = vse.filter(kategoriya=kategoriya) if kategoriya else vse
    return render(request, "atelier/katalog.html", {
        "modeli": modeli, "tekushaya": kategoriya,
        "kategorii": [(k, label, counts.get(k, 0)) for k, label in Model.Kategoriya.choices],
        "n_modelei": vse.count(),
        "n_masterov": Master.objects.filter(rabotaet=True).count(),
        "n_vydano": Zakaz.objects.filter(status=Zakaz.Status.VYDAN).count(),
    })


@login_required
def zakaz_detail(request, pk):
    zakaz = get_object_or_404(Zakaz.objects.select_related("klient", "model"), pk=pk)
    u = request.user
    upr = est_rol(u, UPRAVLYAYUSHII)
    agent = est_rol(u, AGENT)
    master = getattr(u, "master", None) if est_rol(u, MASTER) else None
    klient = getattr(u, "klient", None) if est_rol(u, KLIENT) else None

    dostup = (upr or agent
              or (master and zakaz.zadachi.filter(master=master).exists())
              or (klient and zakaz.klient_id == klient.pk))
    if not dostup:
        raise PermissionDenied

    status_form = f.ZakazStatusForm(instance=zakaz, prefix="st") if upr else None
    zadacha_form = f.ZadachaForm(prefix="zd") if upr else None
    material_form = f.PoziciyaZakazaForm(prefix="mt") if upr else None
    primerka_form = f.PrimerkaForm(prefix="pr") if (upr or agent) else None

    if request.method == "POST":
        action = request.POST.get("action")
        ok = False
        if action == "status" and upr:
            status_form = f.ZakazStatusForm(request.POST, instance=zakaz, prefix="st")
            ok = status_form.is_valid() and save_or_error(status_form)
        elif action == "zadacha" and upr:
            zadacha_form = f.ZadachaForm(request.POST, prefix="zd")
            zadacha_form.instance.zakaz = zakaz
            ok = zadacha_form.is_valid() and save_or_error(zadacha_form)
            if ok and zakaz.status == Zakaz.Status.NOVYI:
                zakaz.status = Zakaz.Status.V_RABOTE
                zakaz.save(update_fields=["status"])
        elif action == "material" and upr:
            material_form = f.PoziciyaZakazaForm(request.POST, prefix="mt")
            material_form.instance.zakaz = zakaz
            ok = material_form.is_valid() and save_or_error(material_form)
        elif action == "primerka" and (upr or agent):
            primerka_form = f.PrimerkaForm(request.POST, prefix="pr")
            primerka_form.instance.zakaz = zakaz
            ok = primerka_form.is_valid() and save_or_error(primerka_form)
            if ok:
                messages.success(request, f"Примерка назначена: {ok.master.fio}, стаж {ok.master.stazh}.")
                return redirect("zakaz_detail", pk=zakaz.pk)
        if ok:
            messages.success(request, "Изменения сохранены.")
            return redirect("zakaz_detail", pk=zakaz.pk)
        messages.error(request, "Исправьте ошибки в форме.")

    return render(request, "atelier/zakaz_detail.html", {
        "zakaz": zakaz,
        "zadachi": zakaz.zadachi.select_related("master"),
        "primerki": zakaz.primerki.select_related("master"),
        "pozicii": zakaz.pozicii.select_related("material"),
        "status_form": status_form, "zadacha_form": zadacha_form,
        "material_form": material_form, "primerka_form": primerka_form,
        "merki": getattr(zakaz.klient, "merki", None) if (upr or agent or master) else None,
    })


# ---------------------------------------------------------------------------
# Клиент
# ---------------------------------------------------------------------------
def _moi_klient(request):
    klient = getattr(request.user, "klient", None)
    if klient is None:
        raise PermissionDenied("Учётная запись не связана с карточкой клиента.")
    return klient


@rol_required(KLIENT)
def moi_zakazy(request):
    klient = _moi_klient(request)
    zakazy = klient.zakazy.select_related("model").prefetch_related("zadachi", "primerki")
    return render(request, "atelier/moi_zakazy.html", {"klient": klient, "zakazy": zakazy})


@rol_required(KLIENT)
def moi_zapisi(request):
    klient = _moi_klient(request)
    form = f.ZapisKlientaForm()
    if request.method == "POST":
        form = f.ZapisKlientaForm(request.POST)
        form.instance.klient = klient
        if form.is_valid() and save_or_error(form):
            messages.success(request, "Вы записаны.")
            return redirect("moi_zapisi")
    zapisi = klient.zapisi.filter(data__gte=timezone.localdate())
    primerki = Primerka.objects.filter(zakaz__klient=klient).select_related("zakaz__model")
    return render(request, "atelier/moi_zapisi.html", {
        "form": form, "zapisi": zapisi, "primerki": primerki,
    })


@login_required
def zapis_delete(request, pk):
    zapis = get_object_or_404(Zapis, pk=pk)
    svoya = est_rol(request.user, KLIENT) and zapis.klient.user_id == request.user.pk
    if not (svoya or est_rol(request.user, *PERSONAL)):
        raise PermissionDenied
    if request.method == "POST":
        zapis.delete()
        messages.success(request, "Запись отменена.")
    return redirect(request.POST.get("next") or "home")


# ---------------------------------------------------------------------------
# Агент приёма
# ---------------------------------------------------------------------------
# Поле поиска выбирает сам сотрудник («Искать по»): сайт ничего не угадывает.
POLYA_POISKA = {
    "fio": ("ФИО", "Фамилия, имя или отчество",
            "Начало фамилии, имени или отчества. Можно несколько слов: «коз мар» — Козлова Мария."),
    "telefon": ("Телефон", "Цифры телефона",
                "Любые цифры номера, дефисы и пробелы не важны. Сначала — номера, которые начинаются с этих цифр."),
    "nomer": ("№ клиента", "Номер клиента",
              "Точный номер: 6, 06 и 006 — это клиент № 006."),
    "email": ("E-mail", "Часть адреса e-mail",
              "Любая часть адреса: «gmail» — все клиенты с почтой на gmail.com."),
}


def poisk_klientov(qs, q, po="fio"):
    """Поиск клиентов по выбранному полю.

    po = "fio"      каждое слово запроса — начало фамилии, имени или отчества (ё = е);
         "telefon"  цифры в любом месте номера (дефисы и пробелы не важны), сначала — с начала номера;
         "nomer"    точный номер клиента;
         "email"    часть адреса, сначала — адреса, которые с неё начинаются.
    Возвращает список клиентов: сначала самые точные совпадения, внутри — по ФИО.
    """
    po = po if po in POLYA_POISKA else "fio"
    s = q.strip().lower().replace("ё", "е")
    vse = list(qs.order_by("fio"))
    if not s:
        return vse
    if po == "nomer":
        cifry = re.sub(r"\D", "", s)
        return [k for k in vse if cifry and k.pk == int(cifry)]
    naideno = []
    if po == "telefon":
        cifry = re.sub(r"\D", "", s)
        for k in vse if cifry else []:
            t = re.sub(r"\D", "", k.telefon)
            if t.startswith(cifry) or t[1:].startswith(cifry):   # с начала номера (с +7 или без)
                naideno.append((1, k))
            elif cifry in t:
                naideno.append((2, k))
    elif po == "email":
        for k in vse:
            e = (k.email or "").lower()
            if e.startswith(s):
                naideno.append((1, k))
            elif s in e:
                naideno.append((2, k))
    else:
        slova = s.split()
        for k in vse:
            w = k.fio.lower().replace("ё", "е").split()
            if all(any(x.startswith(sl) for x in w) for sl in slova):
                naideno.append((1 if w and w[0].startswith(slova[0]) else 2, k))   # совпала фамилия — выше
    naideno.sort(key=lambda p: p[0])          # сортировка устойчива: внутри — по ФИО
    return [k for _, k in naideno]


@rol_required(*PERSONAL)
def klienty(request):
    q = request.GET.get("q", "").strip()
    po = request.GET.get("po", "fio")
    po = po if po in POLYA_POISKA else "fio"
    klienty_ = poisk_klientov(Klient.objects.annotate(n_zakazov=Count("zakazy")), q, po)
    return render(request, "atelier/klienty.html", {
        "klienty": klienty_, "q": q, "po": po, "pole": POLYA_POISKA[po],
        "polya": [(kod, nazv, ph, hint) for kod, (nazv, ph, hint) in POLYA_POISKA.items()]})


@rol_required(*PERSONAL)
def klient_new(request):
    form = f.KlientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        klient = save_or_error(form, posle=lambda k: form.sozdat_uchetku(k, KLIENT))
        if klient:
            messages.success(request, "Клиент зарегистрирован.")
            return redirect("klient_detail", pk=klient.pk)
    return form_page(request, form, "Регистрация клиента", back="klienty")


@rol_required(*PERSONAL)
def klient_edit(request, pk):
    klient = get_object_or_404(Klient, pk=pk)
    form = f.KlientEditForm(request.POST or None, instance=klient)
    if request.method == "POST" and form.is_valid() and save_or_error(form):
        return redirect("klient_detail", pk=pk)
    return form_page(request, form, f"Клиент: {klient.fio}")


@rol_required(*PERSONAL)
def klient_detail(request, pk):
    klient = get_object_or_404(Klient, pk=pk)
    return render(request, "atelier/klient_detail.html", {
        "klient": klient,
        "merki": getattr(klient, "merki", None),
        "zakazy": klient.zakazy.select_related("model"),
        "zapisi": klient.zapisi.filter(data__gte=timezone.localdate()),
    })


@rol_required(*PERSONAL)
def merki_edit(request, pk):
    klient = get_object_or_404(Klient, pk=pk)
    merki = getattr(klient, "merki", None) or Merki(klient=klient)
    form = f.MerkiForm(request.POST or None, instance=merki)
    if request.method == "POST" and form.is_valid() and save_or_error(form):
        messages.success(request, "Мерки сохранены.")
        return redirect("klient_detail", pk=pk)
    return form_page(request, form, f"Мерки: {klient.fio}")


@rol_required(*PERSONAL)
def zakaz_new(request):
    initial = {}
    if request.GET.get("klient"):
        initial["klient"] = request.GET["klient"]
    if request.GET.get("model"):
        initial["model"] = request.GET["model"]
    form = f.ZakazForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        zakaz = save_or_error(form)
        if zakaz:
            messages.success(request, f"Заказ №{zakaz.pk} оформлен.")
            return redirect("zakaz_detail", pk=zakaz.pk)
    return form_page(request, form, "Оформление заказа")


@rol_required(*PERSONAL)
def zapisi(request):
    form = f.ZapisForm(request.POST or None, initial={"klient": request.GET.get("klient")})
    if request.method == "POST" and form.is_valid() and save_or_error(form):
        messages.success(request, "Запись создана.")
        return redirect("zapisi")
    return render(request, "atelier/zapisi.html", {
        "form": form,
        "zapisi": Zapis.objects.filter(data__gte=timezone.localdate()).select_related("klient"),
        "primerki": Primerka.objects.filter(data__gte=timezone.localdate())
                                    .select_related("zakaz__klient", "master"),
    })


# ---------------------------------------------------------------------------
# Управляющий
# ---------------------------------------------------------------------------
@rol_required(UPRAVLYAYUSHII)
def panel(request):
    aktivnye = Zakaz.objects.filter(status__in=Zakaz.AKTIVNYE_STATUSY)
    counts = dict(Zakaz.objects.values_list("status").annotate(n=Count("id")))
    vsego = sum(counts.values()) or 1
    # статусы в порядке прохождения заказа (для полосы распределения)
    statusy = [{"code": code, "label": label, "n": counts.get(code, 0),
                "pct": round(counts.get(code, 0) * 100 / vsego, 1)}
               for code, label in Zakaz.Status.choices]
    vydannye = Zakaz.objects.filter(status=Zakaz.Status.VYDAN)
    vyruchka = vydannye.aggregate(s=Sum("stoimost"))["s"] or 0
    zagruzka = list(Master.objects.filter(rabotaet=True).annotate(
        n=Count("zadachi", filter=~Q(zadachi__status=Zadacha.Status.VYPOLNENA))
    ).filter(n__gt=0).order_by("-n", "fio")[:8])
    max_n = max([m.n for m in zagruzka], default=1)
    for m in zagruzka:
        m.pct = round(m.n * 100 / max_n)
    segodnya = timezone.localdate()
    return render(request, "atelier/panel.html", {
        "statusy": statusy,
        "vsego_zakazov": sum(counts.values()),
        "n_aktivnyh": aktivnye.count(),
        "n_klientov": Klient.objects.count(),
        "vyruchka": vyruchka,
        "sredniy_chek": (vyruchka / vydannye.count()) if vydannye.exists() else 0,
        "aktivnye": aktivnye.select_related("klient", "model")[:8],
        "bez_zadach": aktivnye.filter(zadachi__isnull=True).count(),
        "problemy": Zadacha.objects.filter(status=Zadacha.Status.PROBLEMA)
                                   .select_related("zakaz", "master"),
        "malo": Material.objects.filter(ostatok__lt=5),
        "zagruzka": zagruzka,
        "blizhaishie": Primerka.objects.filter(data__gte=segodnya)
                               .select_related("zakaz__klient", "master")[:6],
    })


@rol_required(*PERSONAL)
def zakazy(request):
    status = request.GET.get("status", "")
    qs = Zakaz.objects.select_related("klient", "model")
    if status:
        qs = qs.filter(status=status)
    return render(request, "atelier/zakazy.html", {
        "zakazy": qs, "statusy": Zakaz.Status.choices, "tekushii": status,
    })


@rol_required(UPRAVLYAYUSHII)
def modeli(request):
    return render(request, "atelier/modeli.html", {"modeli": Model.objects.all()})


@rol_required(UPRAVLYAYUSHII)
def model_edit(request, pk=None):
    obj = get_object_or_404(Model, pk=pk) if pk else None
    form = f.ModelForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid() and save_or_error(form):
        messages.success(request, "Модель сохранена.")
        return redirect("modeli")
    return form_page(request, form, "Модель" if obj else "Новая модель", back="modeli")


@rol_required(UPRAVLYAYUSHII)
def mastera(request):
    return render(request, "atelier/mastera.html", {
        "mastera": Master.objects.annotate(
            n=Count("zadachi", filter=~Q(zadachi__status=Zadacha.Status.VYPOLNENA))),
    })


@rol_required(UPRAVLYAYUSHII)
def master_new(request):
    form = f.MasterForm(request.POST or None)
    if request.method == "POST" and form.is_valid() and save_or_error(
            form, posle=lambda m: form.sozdat_uchetku(m, MASTER)):
        messages.success(request, "Мастер принят на работу.")
        return redirect("mastera")
    return form_page(request, form, "Приём мастера на работу", back="mastera")


@rol_required(UPRAVLYAYUSHII)
def master_edit(request, pk):
    m = get_object_or_404(Master, pk=pk)
    form = f.MasterEditForm(request.POST or None, instance=m)

    def vhod(m):
        if m.user:  # уволенный мастер не может войти в систему
            m.user.is_active = m.rabotaet
            m.user.save(update_fields=["is_active"])

    if request.method == "POST" and form.is_valid() and save_or_error(form, posle=vhod):
        return redirect("mastera")
    return form_page(request, form, f"Мастер: {m.fio}", back="mastera",
                     extra={"help": "Снимите «Работает», чтобы уволить мастера."})


@rol_required(UPRAVLYAYUSHII)
def sklad(request):
    return render(request, "atelier/sklad.html", {"materialy": Material.objects.all()})


@rol_required(UPRAVLYAYUSHII)
def material_edit(request, pk=None):
    obj = get_object_or_404(Material, pk=pk) if pk else None
    form = f.MaterialForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid() and save_or_error(form):
        return redirect("sklad")
    return form_page(request, form, "Материал" if obj else "Новый материал", back="sklad",
                     extra={"help": "Остаток меняется только через закупки и заказы."})


@rol_required(UPRAVLYAYUSHII)
def zakupki(request):
    return render(request, "atelier/zakupki.html", {
        "zakupki": Zakupka.objects.prefetch_related("pozicii__material"),
    })


@rol_required(UPRAVLYAYUSHII)
def zakupka_new(request):
    form = f.ZakupkaForm(request.POST or None)
    pozicii = f.PoziciiZakupkiForm(request.POST or None)
    if request.method == "POST" and form.is_valid() and pozicii.is_valid():
        try:
            with transaction.atomic():
                zakupka = form.save()
                for material, kolichestvo in pozicii.cleaned_data["pozicii"]:
                    # каждая позиция увеличивает остаток на складе (в SQL Server — триггером)
                    PoziciyaZakupki.objects.create(zakupka=zakupka, material=material,
                                                   kolichestvo=kolichestvo)
        except DatabaseError as e:
            messages.error(request, poyasnenie_bd(e)[1])
        else:
            messages.success(request, "Закупка проведена, склад пополнен.")
            return redirect("zakupki")
    return render(request, "atelier/zakupka_form.html", {"form": form, "pozicii": pozicii})


# ---------------------------------------------------------------------------
# Мастер
# ---------------------------------------------------------------------------
def _moi_master(request):
    m = getattr(request.user, "master", None)
    if m is None:
        raise PermissionDenied("Учётная запись не связана с карточкой мастера.")
    return m


@rol_required(MASTER)
def moi_zadachi(request):
    master = _moi_master(request)
    if request.method == "POST":
        zadacha = get_object_or_404(Zadacha, pk=request.POST.get("zadacha"), master=master)
        form = f.ZadachaStatusForm(request.POST, instance=zadacha)
        if form.is_valid() and save_or_error(form):
            messages.success(request, f"Статус задачи №{zadacha.pk} обновлён.")
        else:
            messages.error(request, " ".join(["Не удалось обновить статус.", *form.non_field_errors()]))
        return redirect("moi_zadachi")
    zadachi = master.zadachi.select_related("zakaz__model", "zakaz__klient")
    # мастера по опыту: стаж, задачи в работе и сколько из них сложных (ограничение 23)
    ne_vyp = ~Q(zadachi__status=Zadacha.Status.VYPOLNENA)
    mastera = list(Master.objects.filter(rabotaet=True)
                   .annotate(n_otkr=Count("zadachi", filter=ne_vyp),
                             n_slozh=Count("zadachi", filter=ne_vyp & Q(zadachi__slozhnaya=True)))
                   .order_by("-stazh", "fio"))
    max_n = max([m.n_otkr for m in mastera] + [1])
    po_opytu = [{"m": m, "mesto": i, "ya": m.pk == master.pk, "pct": round(m.n_otkr * 100 / max_n)}
                for i, m in enumerate(mastera, 1)]
    return render(request, "atelier/moi_zadachi.html", {
        "aktivnye": [(z, f.ZadachaStatusForm(instance=z))
                     for z in zadachi.exclude(status=Zadacha.Status.VYPOLNENA)],
        "vypolnennye": zadachi.filter(status=Zadacha.Status.VYPOLNENA),
        "statusy": Zadacha.Status.choices,
        "master": master, "po_opytu": po_opytu,
        "mesto": next((s["mesto"] for s in po_opytu if s["ya"]), None),
    })


@rol_required(MASTER)
def moi_primerki(request):
    master = _moi_master(request)
    if request.method == "POST":
        p = get_object_or_404(Primerka, pk=request.POST.get("primerka"), master=master)
        p.rezultat = request.POST.get("rezultat", "")[:500]
        p.save(update_fields=["rezultat"])
        messages.success(request, "Результат примерки сохранён.")
        return redirect("moi_primerki")
    # очередь на примерки: кто следующий по стажу и сколько примерок у каждого впереди
    ochered = list(Primerka.ochered())
    vperedi = {}
    for mid in Primerka.objects.filter(data__gte=timezone.localdate(), master__in=ochered).values_list("master_id", flat=True):
        vperedi[mid] = vperedi.get(mid, 0) + 1
    max_n = max(vperedi.values(), default=0) or 1
    stroki = [{"m": m, "mesto": i, "n": vperedi.get(m.pk, 0), "ya": m.pk == master.pk,
               "pct": round(vperedi.get(m.pk, 0) * 100 / max_n)} for i, m in enumerate(ochered, 1)]
    mesto = next((s["mesto"] for s in stroki if s["ya"]), None)
    primerki = list(master.primerki.select_related("zakaz__klient", "zakaz__model").order_by("data", "vremya"))
    for p in primerki:
        p.prichina, p.zanyaty = p.pochemu_master(ochered)
    return render(request, "atelier/moi_primerki.html", {
        "primerki": primerki, "ochered": stroki, "mesto": mesto, "master": master,
        "n_vperedi": vperedi.get(master.pk, 0),
    })
