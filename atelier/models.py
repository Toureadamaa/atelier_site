"""Модели базы данных швейного ателье.

Модели привязаны к УЖЕ СУЩЕСТВУЮЩИМ таблицам базы «projet corse»
(Клиент, Заказ, … с колонками Номер_клиента, Номер_заказа, …):
  * db_table / db_column — имена таблиц и колонок из SQL Server;
  * managed = False — Django не создаёт и не удаляет эти таблицы.
Недостающие колонки (Статус, Работает, user_id, …) добавляет
миграция atelier/migrations/0002_dopolnit_tablicy.py.

Ограничения предметной области (глава 3.3) проверяет SQL Server:
CHECK, UNIQUE и триггеры, созданные вашим скриптом. Пока включена настройка
PROVERKA_V_BAZE (config/settings.py), Django эти правила НЕ проверяет:
данные сразу уходят в базу, а если база их отклоняет, сайт показывает её сообщение.
Если PROVERKA_V_BAZE выключить, правила проверяет и Django:
Meta.constraints, clean() и минимальные значения полей.
"""
from datetime import datetime, timedelta
from decimal import Decimal                              

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import connection, models, transaction
from django.db.models import F, Q
from django.utils import timezone


def proverka_v_baze():
    """True — правила п. 3.3 проверяет только SQL Server (настройка PROVERKA_V_BAZE)."""
    return getattr(settings, "PROVERKA_V_BAZE", False)


class Minimum(MinValueValidator):
    """Минимальное значение поля (цена > 0, количество >= 1, остаток >= 0 …).
    Если правила проверяет SQL Server, Django его не проверяет: это делает CHECK в базе."""

    def __call__(self, value):
        if not proverka_v_baze():
            super().__call__(value)


POSITIVE = [Minimum(Decimal("0.01"))]
MIN_ODIN = [Minimum(1)]
# В SQL Server таблицы уже есть → Django ими не управляет.
# При проверке на SQLite (DB_ENGINE=sqlite) таблицы создаются автоматически.
MANAGED = getattr(settings, "ATELIER_TABLES_MANAGED", False)


def today():
    return timezone.localdate()


class ModelAteliera(models.Model):
    """Общий предок моделей ателье.
    Если правила проверяет SQL Server, Django не проверяет уникальность (unique=True)
    и Meta.constraints: это делают ограничения UNIQUE и CHECK в базе."""

    class Meta:
        abstract = True

    def validate_unique(self, exclude=None):
        if not proverka_v_baze():
            super().validate_unique(exclude)

    def validate_constraints(self, exclude=None):
        if not proverka_v_baze():
            super().validate_constraints(exclude)


# Допустимые значения (списки из главы 3.3)
class KategoriyaModeli(models.TextChoices):
    PLATE = "платье", "Платье"
    KOSTYUM = "костюм", "Костюм"
    PALTO = "пальто", "Пальто"
    YUBKA = "юбка", "Юбка"
    BRYUKI = "брюки", "Брюки"
    RUBASHKA = "рубашка", "Рубашка"


class StatusZakaza(models.TextChoices):
    NOVYI = "новый", "Новый"
    V_RABOTE = "в работе", "В работе"
    PRIMERKA = "примерка", "На примерке"
    GOTOV = "готов", "Готов"
    VYDAN = "выдан", "Выдан"
    OTMENEN = "отменён", "Отменён"


class TipZapisi(models.TextChoices):
    MERKI = "снятие мерок", "Снятие мерок"
    PRIMERKA = "примерка", "Примерка"
    KONSULTACIYA = "консультация", "Консультация"


class DolzhnostMastera(models.TextChoices):
    PORTNOI = "портной", "Портной"
    ZAKROISHIK = "закройщик", "Закройщик"
    VYSHIVALSHIK = "вышивальщик", "Вышивальщик"
    OTDELOCHNIK = "отделочник", "Отделочник"


class StatusZadachi(models.TextChoices):
    NAZNACHENA = "назначена", "Назначена"
    V_RABOTE = "в работе", "В работе"
    VYPOLNENA = "выполнена", "Выполнена"
    PROBLEMA = "проблема", "Проблема"


class EdinicaIzmereniya(models.TextChoices):
    M = "м", "м"
    M2 = "м²", "м²"
    KG = "кг", "кг"
    SHT = "шт", "шт"
    KATUSHKA = "катушка", "катушка"


# ---------------------------------------------------------------------------
# Таблица 1. Клиент
# ---------------------------------------------------------------------------
class Klient(ModelAteliera):
    id = models.AutoField("№ клиента", primary_key=True, db_column="Номер_клиента")
    fio = models.CharField("ФИО", max_length=50, db_column="ФИО")
    telefon = models.CharField("Телефон", max_length=20, unique=True, db_column="Телефон",
                               error_messages={"unique": "Клиент с таким номером телефона уже существует."})
    email = models.EmailField("Email", max_length=50, null=True, blank=True, db_column="Email")
    data_registracii = models.DateField("Дата регистрации", default=today,
                                        db_column="Дата_регистрации")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="klient", verbose_name="Учётная запись", db_column="user_id",
    )

    MAX_AKTIVNYH_ZAKAZOV = 2

    class Meta:
        managed = MANAGED
        db_table = "Клиент"
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"
        ordering = ["fio"]
        constraints = [
            # уникальный e-mail (NULL допускается у нескольких клиентов)
            models.UniqueConstraint(fields=["email"], condition=Q(email__isnull=False),
                                    name="uq_klient_email"),
        ]

    def __str__(self):
        return f"{self.fio} ({self.telefon})"

    def save(self, *args, **kwargs):
        if self.email == "":
            self.email = None
        super().save(*args, **kwargs)

    def aktivnye_zakazy(self):
        return self.zakazy.filter(status__in=Zakaz.AKTIVNYE_STATUSY)


# ---------------------------------------------------------------------------
# Таблица 4. Модель
# ---------------------------------------------------------------------------
class Model(ModelAteliera):
    Kategoriya = KategoriyaModeli

    id = models.AutoField("№ модели", primary_key=True, db_column="Номер_модели")
    nazvanie = models.CharField("Название", max_length=80, db_column="Название")
    kategoriya = models.CharField("Категория", max_length=30, choices=Kategoriya.choices,
                                  db_column="Категория")
    cena = models.DecimalField("Цена", max_digits=10, decimal_places=2, validators=POSITIVE,
                               db_column="Цена")
    opisanie = models.CharField("Описание", max_length=500, null=True,   # ограничение 7: обязательно
                                db_column="Описание")

    class Meta:
        managed = MANAGED
        db_table = "Модель"
        verbose_name = "Модель"
        verbose_name_plural = "Модели"
        ordering = ["kategoriya", "nazvanie"]
        constraints = [
            models.CheckConstraint(condition=Q(cena__gt=0), name="ck_model_cena"),
            models.CheckConstraint(
                condition=Q(kategoriya__in=[c[0] for c in KategoriyaModeli.choices]),
                name="ck_model_kategoriya"),
        ]

    def __str__(self):
        return f"{self.nazvanie} ({self.get_kategoriya_display().lower()})"


# ---------------------------------------------------------------------------
# Таблица 2. Заказ
# ---------------------------------------------------------------------------
class Zakaz(ModelAteliera):
    Status = StatusZakaza
    AKTIVNYE_STATUSY = [Status.NOVYI, Status.V_RABOTE, Status.PRIMERKA, Status.GOTOV]

    id = models.AutoField("№ заказа", primary_key=True, db_column="Номер_заказа")
    klient = models.ForeignKey(Klient, on_delete=models.PROTECT, related_name="zakazy",
                               verbose_name="Клиент", db_column="Номер_клиента")
    model = models.ForeignKey(Model, on_delete=models.PROTECT, related_name="zakazy",
                              verbose_name="Модель", db_column="Номер_модели")
    data_oformleniya = models.DateField("Дата оформления", default=today,
                                        db_column="Дата_оформления")
    data_zaversheniya = models.DateField("Дата завершения", null=True, blank=True,
                                         db_column="Дата_завершения")
    stoimost = models.DecimalField("Стоимость", max_digits=10, decimal_places=2,
                                   validators=POSITIVE, blank=True, db_column="Стоимость")
    status = models.CharField("Статус", max_length=20, choices=Status.choices,
                              default=Status.NOVYI, db_column="Статус")

    class Meta:
        managed = MANAGED
        db_table = "Заказ"
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-data_oformleniya", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(stoimost__gt=0), name="ck_zakaz_stoimost"),
            # ограничение 5: дата завершения не раньше даты оформления
            models.CheckConstraint(
                condition=Q(data_zaversheniya__isnull=True)
                | Q(data_zaversheniya__gte=F("data_oformleniya")),
                name="ck_zakaz_daty"),
            models.CheckConstraint(
                condition=Q(status__in=[c[0] for c in StatusZakaza.choices]),
                name="ck_zakaz_status"),
        ]

    def __str__(self):
        return f"Заказ №{self.pk} — {self.model.nazvanie}"

    @property
    def aktivnyi(self):
        return self.status in self.AKTIVNYE_STATUSY

    def clean(self):
        if proverka_v_baze():
            return   # ограничения 2, 4, 5, 7 проверяет SQL Server (CHECK и триггеры)
        errors = {}
        # ограничение 7: размер изделия — заказ оформляется только клиенту со снятыми мерками
        if self._state.adding and self.klient_id and not Merki.objects.filter(klient_id=self.klient_id).exists():
            errors["klient"] = "У клиента не сняты мерки (размер изделия) — сначала снимите мерки."
        if self.data_oformleniya and self.data_oformleniya > today():
            errors["data_oformleniya"] = "Дата оформления не может быть в будущем."
        if (self.data_oformleniya and self.data_zaversheniya
                and self.data_zaversheniya < self.data_oformleniya):
            errors["data_zaversheniya"] = "Дата завершения не может быть раньше даты оформления."
        # не более двух активных заказов у клиента
        if self.klient_id and self.status in self.AKTIVNYE_STATUSY:
            drugie = self.klient.aktivnye_zakazy().exclude(pk=self.pk).count()
            if drugie >= Klient.MAX_AKTIVNYH_ZAKAZOV:
                errors["klient"] = (f"У клиента уже {drugie} активных заказа — "
                                    f"больше {Klient.MAX_AKTIVNYH_ZAKAZOV} нельзя.")
        if errors:
            raise ValidationError(errors)

    SROK_DNEI = 21   # плановый срок нового заказа, дней

    def save(self, *args, **kwargs):
        # стоимость по умолчанию — цена выбранной модели
        if self.stoimost is None and self.model_id:
            self.stoimost = self.model.cena
        # новый заказ без даты завершения: плановая дата — через SROK_DNEI дней
        if self._state.adding and not self.data_zaversheniya and self.status in self.AKTIVNYE_STATUSY:
            self.data_zaversheniya = today() + timedelta(days=self.SROK_DNEI)
        # заказ выдают: дата завершения становится фактической датой выдачи (сегодня)
        if self.status == self.Status.VYDAN:
            staryi_status = None if self._state.adding else (
                Zakaz.objects.filter(pk=self.pk).values_list("status", flat=True).first())
            if staryi_status != self.Status.VYDAN:
                self.data_zaversheniya = today()
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Таблица 3. Запись (на приём)
# ---------------------------------------------------------------------------
class Zapis(ModelAteliera):
    Tip = TipZapisi

    id = models.AutoField("№ записи", primary_key=True, db_column="Номер_записи")
    klient = models.ForeignKey(Klient, on_delete=models.CASCADE, related_name="zapisi",
                               verbose_name="Клиент", db_column="Номер_клиента")
    data = models.DateField("Дата", db_column="Дата")
    vremya = models.TimeField("Время", db_column="Время")
    tip_zapisi = models.CharField("Тип записи", max_length=30, choices=Tip.choices,
                                  db_column="Тип_записи")

    class Meta:
        managed = MANAGED
        db_table = "Запись"
        verbose_name = "Запись"
        verbose_name_plural = "Записи"
        ordering = ["data", "vremya"]
        constraints = [
            # клиент не может иметь 2 записи на одно и то же время
            models.UniqueConstraint(fields=["klient", "data", "vremya"],
                                    name="uq_zapis_klient_vremya"),
            models.CheckConstraint(
                condition=Q(tip_zapisi__in=[c[0] for c in TipZapisi.choices]),
                name="ck_zapis_tip"),
        ]

    def __str__(self):
        return f"{self.data:%d.%m.%Y} {self.vremya:%H:%M} — {self.tip_zapisi} ({self.klient.fio})"

    def validate_constraints(self, exclude=None):
        # уникальность «клиент + дата + время» проверяется в clean() с понятным сообщением
        super().validate_constraints(exclude=set(exclude or ()) | {"vremya"})

    def clean(self):
        if proverka_v_baze():
            return   # ограничения 3 и 26 проверяет SQL Server (UNIQUE и CHECK)
        # дата и время записи не могут быть в прошлом (проверяем при создании)
        if self._state.adding and self.data and self.vremya:
            moment = timezone.make_aware(datetime.combine(self.data, self.vremya))
            if moment < timezone.now():
                raise ValidationError("Дата и время записи не могут быть в прошлом.")
        # клиент не может иметь 2 записи на одно и то же время
        # (проверка здесь, т.к. в форме клиента поле «клиент» не показывается)
        if (self.klient_id and self.data and self.vremya and Zapis.objects.filter(
                klient_id=self.klient_id, data=self.data, vremya=self.vremya
        ).exclude(pk=self.pk).exists()):
            raise ValidationError("У клиента уже есть запись на это время.")


# ---------------------------------------------------------------------------
# Таблица 5. Мерки (связь 1:1 с клиентом)
# ---------------------------------------------------------------------------
class Merki(ModelAteliera):
    id = models.AutoField("№ мерки", primary_key=True, db_column="Номер_мерки")
    klient = models.OneToOneField(Klient, on_delete=models.CASCADE, related_name="merki",
                                  verbose_name="Клиент", db_column="Номер_клиента")
    grud = models.DecimalField("Грудь, см", max_digits=5, decimal_places=1,
                               validators=POSITIVE, db_column="Грудь")
    taliya = models.DecimalField("Талия, см", max_digits=5, decimal_places=1,
                                 validators=POSITIVE, db_column="Талия")
    bedra = models.DecimalField("Бёдра, см", max_digits=5, decimal_places=1,
                                validators=POSITIVE, db_column="Бедра")
    data_snyatiya = models.DateField("Дата снятия", default=today, db_column="Дата_снятия")

    class Meta:
        managed = MANAGED
        db_table = "Мерки"
        verbose_name = "Мерки"
        verbose_name_plural = "Мерки"
        constraints = [
            models.CheckConstraint(condition=Q(grud__gt=0) & Q(taliya__gt=0) & Q(bedra__gt=0),
                                   name="ck_merki_polozhitelnye"),
        ]

    def __str__(self):
        return f"Мерки: {self.klient.fio}"


# ---------------------------------------------------------------------------
# Таблица 6. Мастер
# ---------------------------------------------------------------------------
class Master(ModelAteliera):
    Dolzhnost = DolzhnostMastera

    id = models.AutoField("№ мастера", primary_key=True, db_column="Номер_мастера")
    fio = models.CharField("ФИО", max_length=50, db_column="ФИО")
    dolzhnost = models.CharField("Должность", max_length=30, choices=Dolzhnost.choices,
                                 db_column="Должность")
    stazh = models.IntegerField("Стаж, лет", default=0, validators=[MinValueValidator(0)],
                                db_column="Стаж")
    nomer_telefona = models.CharField("Номер телефона", max_length=20, unique=True,
                                      error_messages={"unique": "Мастер с таким номером телефона уже существует."},
                                      db_column="Номер_телефона")
    rabotaet = models.BooleanField("Работает", default=True, db_column="Работает")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="master", verbose_name="Учётная запись", db_column="user_id",
    )

    class Meta:
        managed = MANAGED
        db_table = "Мастер"
        verbose_name = "Мастер"
        verbose_name_plural = "Мастера"
        ordering = ["fio"]
        constraints = [
            models.CheckConstraint(condition=Q(stazh__gte=0), name="ck_master_stazh"),
            models.CheckConstraint(
                condition=Q(dolzhnost__in=[c[0] for c in DolzhnostMastera.choices]),
                name="ck_master_dolzhnost"),
        ]

    def __str__(self):
        return f"{self.fio} — {self.dolzhnost}"

    def clean(self):
        # ограничение 23: при невыполненных сложных задачах стаж не может быть меньше года
        if self.pk and self.stazh is not None and self.stazh < 1 and self.zadachi.filter(
                slozhnaya=True).exclude(status=Zadacha.Status.VYPOLNENA).exists():
            raise ValidationError({"stazh": "У мастера есть невыполненные сложные задачи — стаж не может быть меньше 1 года."})


# ---------------------------------------------------------------------------
# Таблица 7. Задача
# ---------------------------------------------------------------------------
class Zadacha(ModelAteliera):
    Status = StatusZadachi
    MIN_STAZH_SLOZHNAYA = 1

    id = models.AutoField("№ задачи", primary_key=True, db_column="Номер_задачи")
    zakaz = models.ForeignKey(Zakaz, on_delete=models.CASCADE, related_name="zadachi",
                              verbose_name="Заказ", db_column="Номер_заказа")
    master = models.ForeignKey(Master, on_delete=models.PROTECT, related_name="zadachi",
                               verbose_name="Мастер", db_column="Номер_мастера")
    opisanie = models.CharField("Описание", max_length=500, db_column="Описание")
    data_naznacheniya = models.DateField("Дата назначения", default=today,
                                         db_column="Дата_назначения")
    slozhnaya = models.BooleanField("Сложная задача", default=False, db_column="Сложная")
    status = models.CharField("Статус", max_length=20, choices=Status.choices,
                              default=Status.NAZNACHENA, db_column="Статус")
    kommentarii = models.CharField("Комментарий мастера", max_length=500, blank=True,
                                   default="", db_column="Комментарий")

    class Meta:
        managed = MANAGED
        db_table = "Задача"
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"
        ordering = ["-data_naznacheniya", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=[c[0] for c in StatusZadachi.choices]),
                name="ck_zadacha_status"),
        ]

    def __str__(self):
        return f"Задача №{self.pk}: {self.opisanie[:40]}"

    def clean(self):
        if self.master_id:
            if not self.master.rabotaet:
                raise ValidationError({"master": "Мастер уволен — назначьте другого."})
            # ограничение 23 проверяет SQL Server (триггер tr_задача_стаж)
            if (not proverka_v_baze() and self.slozhnaya
                    and self.master.stazh < self.MIN_STAZH_SLOZHNAYA):
                raise ValidationError({"master": "Для сложной задачи нужен стаж не менее 1 года."})


# ---------------------------------------------------------------------------
# Таблица 8. График примерок
# ---------------------------------------------------------------------------
class Primerka(models.Model):
    id = models.AutoField("№ примерки", primary_key=True, db_column="Номер_примерки")
    zakaz = models.ForeignKey(Zakaz, on_delete=models.CASCADE, related_name="primerki",
                              verbose_name="Заказ", db_column="Номер_заказа")
    data = models.DateField("Дата", db_column="Дата")
    vremya = models.TimeField("Время", db_column="Время")
    master = models.ForeignKey(Master, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="primerki", verbose_name="Проводит мастер",
                               db_column="Номер_мастера")
    rezultat = models.CharField("Результат примерки", max_length=500, blank=True, default="",
                                db_column="Результат")

    class Meta:
        managed = MANAGED
        db_table = "График_примерок"
        verbose_name = "Примерка"
        verbose_name_plural = "График примерок"
        ordering = ["data", "vremya"]

    def __str__(self):
        return f"Примерка {self.data:%d.%m.%Y} {self.vremya:%H:%M} (заказ №{self.zakaz_id})"

    # примерку проводит портной или закройщик; по умолчанию — самый опытный из свободных
    DOLZHNOSTI_PRIMERKI = ["портной", "закройщик"]

    @classmethod
    def svobodnye_mastera(cls, data, vremya, krome=None):
        """Работающие портные и закройщики без другой примерки в это время — от большего стажа к меньшему."""
        zanyaty = cls.objects.filter(data=data, vremya=vremya, master__isnull=False)
        if krome:
            zanyaty = zanyaty.exclude(pk=krome)
        return (Master.objects.filter(rabotaet=True, dolzhnost__in=cls.DOLZHNOSTI_PRIMERKI)
                .exclude(pk__in=zanyaty.values("master")).order_by("-stazh", "fio"))

    @classmethod
    def ochered(cls):
        """Очередь на примерки: работающие портные и закройщики от большего стажа к меньшему
        (тот же порядок, что в процедуре Назначить_примерку: ORDER BY Стаж DESC, ФИО)."""
        return Master.objects.filter(rabotaet=True, dolzhnost__in=cls.DOLZHNOSTI_PRIMERKI).order_by("-stazh", "fio")

    def pochemu_master(self, ochered=None):
        """Почему примерку проводит этот мастер.

        ("opytnyi", [])          — он первый в очереди, самый опытный;
        ("zanyaty", [мастера])   — все более опытные мастера в это время заняты другими примерками;
        ("vruchnuyu", [...])     — более опытный был свободен: мастера выбрал управляющий.
        """
        ochered = list(Primerka.ochered() if ochered is None else ochered)
        ids = [m.pk for m in ochered]
        if self.master_id not in ids:
            return "vruchnuyu", []
        starshe = ochered[:ids.index(self.master_id)]
        if not starshe:
            return "opytnyi", []
        zanyaty_ids = set(Primerka.objects.filter(data=self.data, vremya=self.vremya, master__in=starshe)
                          .exclude(pk=self.pk).values_list("master_id", flat=True))
        zanyaty = [m for m in starshe if m.pk in zanyaty_ids]
        return ("zanyaty" if len(zanyaty) == len(starshe) else "vruchnuyu"), zanyaty

    def clean(self):
        if self._state.adding and self.data and self.data < today():
            raise ValidationError({"data": "Дата примерки не может быть в прошлом."})
        if self.master_id and self.data and self.vremya and Primerka.objects.filter(
                master_id=self.master_id, data=self.data, vremya=self.vremya).exclude(pk=self.pk).exists():
            raise ValidationError({"master": "У мастера уже есть примерка в это время."})
        if not self.master_id and self.data and self.vremya and self._state.adding \
                and not Primerka.svobodnye_mastera(self.data, self.vremya).exists():
            raise ValidationError({"vremya": "В это время все мастера заняты — выберите другое время."})

    def save(self, *args, **kwargs):
        # мастер не выбран — назначаем самого опытного свободного
        if not self.master_id and self.data and self.vremya:
            self.master = Primerka.svobodnye_mastera(self.data, self.vremya, krome=self.pk).first()
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Таблица 9. Материал
# ---------------------------------------------------------------------------
class Material(ModelAteliera):
    Edinica = EdinicaIzmereniya

    id = models.AutoField("№ материала", primary_key=True, db_column="Номер_материала")
    nazvanie = models.CharField("Название", max_length=150, db_column="Название")
    tip = models.CharField("Тип", max_length=50, db_column="Тип")
    ostatok = models.DecimalField("Остаток", max_digits=10, decimal_places=2, default=0,
                                  validators=[Minimum(0)], db_column="Остаток")
    edinica_izmereniya = models.CharField("Единица измерения", max_length=10,
                                          choices=Edinica.choices,
                                          db_column="Единица_измерения")

    class Meta:
        managed = MANAGED
        db_table = "Материал"
        verbose_name = "Материал"
        verbose_name_plural = "Материалы"
        ordering = ["tip", "nazvanie"]
        constraints = [
            models.CheckConstraint(condition=Q(ostatok__gte=0), name="ck_material_ostatok"),
            models.CheckConstraint(
                condition=Q(edinica_izmereniya__in=[c[0] for c in EdinicaIzmereniya.choices]),
                name="ck_material_edinica"),
        ]

    def __str__(self):
        return f"{self.nazvanie} (остаток {self.ostatok:g} {self.edinica_izmereniya})"


# ---------------------------------------------------------------------------
# Таблица 10. Закупка
# ---------------------------------------------------------------------------
class Zakupka(models.Model):
    id = models.AutoField("№ закупки", primary_key=True, db_column="Номер_закупки")
    data = models.DateField("Дата", default=today, db_column="Дата")
    postavshik = models.CharField("Поставщик", max_length=200, db_column="Поставщик")

    class Meta:
        managed = MANAGED
        db_table = "Закупка"
        verbose_name = "Закупка"
        verbose_name_plural = "Закупки"
        ordering = ["-data", "-id"]

    def __str__(self):
        return f"Закупка №{self.pk} от {self.data:%d.%m.%Y} — {self.postavshik}"


def trigger_vklyuchen(imya):
    """True, если в SQL Server есть включённый триггер с таким именем (скрипт contraintes_bd.sql).
    Тогда остаток на складе меняет сама база, и приложение не должно менять его второй раз."""
    if connection.vendor != "microsoft":
        return False
    with connection.cursor() as c:
        # имя без учёта регистра: tr_позициязаказа_списание = TR_ПозицияЗаказа_Списание
        c.execute("SELECT COUNT(*) FROM sys.triggers WHERE LOWER(name) = LOWER(%s) AND is_disabled = 0",
                  [imya])
        return c.fetchone()[0] > 0


class _PoziciyaBase(models.Model):
    """Общая логика позиций: позиция неизменяема после создания
    («использованный материал не подлежит изменению»)."""

    material = models.ForeignKey(Material, on_delete=models.PROTECT, verbose_name="Материал",
                                 db_column="Номер_материала")
    kolichestvo = models.DecimalField("Количество", max_digits=10, decimal_places=2,
                                      validators=MIN_ODIN, db_column="Количество")

    class Meta:
        abstract = True

    TRIGGER = ""   # триггер SQL Server, который меняет остаток (ограничения 15, 16)

    def izmenit_ostatok(self):
        raise NotImplementedError

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Позицию нельзя изменить после проведения.")
        with transaction.atomic():
            if not trigger_vklyuchen(self.TRIGGER):
                self.izmenit_ostatok()
            kwargs["force_insert"] = True
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Проведённую позицию нельзя удалить.")


# ---------------------------------------------------------------------------
# Таблица 11. Позиция закупки (M:M Закупка — Материал, составной ключ)
# ---------------------------------------------------------------------------
class PoziciyaZakupki(_PoziciyaBase):
    pk = models.CompositePrimaryKey("zakupka", "material")
    TRIGGER = "TR_ПозицияЗакупки_Поступление"
    zakupka = models.ForeignKey(Zakupka, on_delete=models.PROTECT, related_name="pozicii",
                                verbose_name="Закупка", db_column="Номер_закупки")

    class Meta:
        managed = MANAGED
        db_table = "Позиция_закупки"
        verbose_name = "Позиция закупки"
        verbose_name_plural = "Позиции закупки"

    def __str__(self):
        return f"{self.material.nazvanie}: +{self.kolichestvo:g}"

    def izmenit_ostatok(self):
        # при поступлении материалов их количество на складе увеличивается
        Material.objects.filter(pk=self.material_id).update(
            ostatok=F("ostatok") + self.kolichestvo)


# ---------------------------------------------------------------------------
# Таблица 12. Позиция заказа (M:M Заказ — Материал, составной ключ)
# ---------------------------------------------------------------------------
class PoziciyaZakaza(_PoziciyaBase):
    pk = models.CompositePrimaryKey("zakaz", "material")
    TRIGGER = "TR_ПозицияЗаказа_Списание"
    zakaz = models.ForeignKey(Zakaz, on_delete=models.PROTECT, related_name="pozicii",
                              verbose_name="Заказ", db_column="Номер_заказа")
    edinica_izmereniya = models.CharField("Единица измерения", max_length=10,
                                          choices=EdinicaIzmereniya.choices, blank=True,
                                          db_column="Единица_измерения")

    class Meta:
        managed = MANAGED
        db_table = "Позиция_заказа"
        verbose_name = "Материал заказа"
        verbose_name_plural = "Материалы заказа"

    def __str__(self):
        return f"{self.material.nazvanie}: −{self.kolichestvo:g}"

    def clean(self):
        if self._state.adding and self.material_id and self.kolichestvo:
            # ограничения 14 и 17 проверяет SQL Server (триггер tr_позициязаказа_списание)
            if not proverka_v_baze() and self.material.ostatok < self.kolichestvo:
                raise ValidationError({"kolichestvo": (
                    f"Недостаточно материала на складе: есть {self.material.ostatok:g} "
                    f"{self.material.edinica_izmereniya}.")})
            if self.zakaz_id and PoziciyaZakaza.objects.filter(
                    zakaz_id=self.zakaz_id, material_id=self.material_id).exists():
                raise ValidationError({"material": "Этот материал уже добавлен в заказ."})

    def save(self, *args, **kwargs):
        # единица измерения берётся из карточки материала
        if not self.edinica_izmereniya and self.material_id:
            self.edinica_izmereniya = self.material.edinica_izmereniya
        super().save(*args, **kwargs)

    def izmenit_ostatok(self):
        # списание со склада; условие ostatok >= kol защищает от гонки
        updated = Material.objects.filter(
            pk=self.material_id, ostatok__gte=self.kolichestvo
        ).update(ostatok=F("ostatok") - self.kolichestvo)
        if not updated:
            raise ValidationError("Недостаточно материала на складе.")
