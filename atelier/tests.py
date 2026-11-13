from datetime import time, timedelta
from decimal import Decimal as D

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import DatabaseError, IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (Klient, Master, Material, Model, PoziciyaZakaza, Primerka, Zadacha, Zakaz,
                     Zapis)
from .views import poisk_klientov, soobshenie_bd


class OgranicheniyaTest(TestCase):
    """Проверка ограничений предметной области (глава 3.3)."""

    @classmethod
    def setUpTestData(cls):
        call_command("zapolnit", stdout=open("/dev/null", "w"))

    def test_cena_modeli_bolshe_nulya(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Model.objects.create(nazvanie="X", kategoriya="юбка", cena=0)

    def test_kategoriya_iz_spiska(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Model.objects.create(nazvanie="X", kategoriya="шорты", cena=10)

    def test_unikalnyi_telefon_i_email(self):
        k = Klient.objects.first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Klient.objects.create(fio="Дубль", telefon=k.telefon)
        k2 = Klient.objects.exclude(email=None).first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Klient.objects.create(fio="Дубль", telefon="+7 000", email=k2.email)
        # несколько клиентов без email допустимы
        Klient.objects.create(fio="Без почты", telefon="+7 001")

    def test_ne_bolee_dvuh_aktivnyh_zakazov(self):
        k = Klient.objects.get(user__username="klient")  # уже 1 активный
        Zakaz.objects.create(klient=k, model=Model.objects.first())
        z = Zakaz(klient=k, model=Model.objects.first())
        with self.assertRaises(ValidationError):
            z.full_clean()

    def test_data_zaversheniya_ne_ranshe_oformleniya(self):
        z = Zakaz.objects.first()
        z.data_zaversheniya = z.data_oformleniya  # должна быть строго позже
        with self.assertRaises(ValidationError):
            z.full_clean()

    def test_data_oformleniya_ne_v_budushem(self):
        z = Zakaz(klient=Klient.objects.last(), model=Model.objects.first(),
                  data_oformleniya=timezone.localdate() + timedelta(days=1))
        with self.assertRaises(ValidationError):
            z.full_clean()

    def test_zapis_ne_v_proshlom_i_bez_dubley(self):
        k = Klient.objects.last()
        with self.assertRaises(ValidationError):
            Zapis(klient=k, data=timezone.localdate() - timedelta(days=1), vremya=time(10),
                  tip_zapisi="консультация").full_clean()
        d = timezone.localdate() + timedelta(days=9)
        Zapis.objects.create(klient=k, data=d, vremya=time(10), tip_zapisi="консультация")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Zapis.objects.create(klient=k, data=d, vremya=time(10), tip_zapisi="примерка")

    def test_spisanie_so_sklada(self):
        m = Material.objects.get(nazvanie="Атлас бордовый")
        do = m.ostatok
        z = Zakaz.objects.get(status="новый")
        PoziciyaZakaza.objects.create(zakaz=z, material=m, kolichestvo=D("2.5"))
        m.refresh_from_db()
        self.assertEqual(m.ostatok, do - D("2.5"))

    def test_nelzya_spisat_bolshe_ostatka(self):
        m = Material.objects.get(nazvanie="Флизелин клеевой")
        z = Zakaz.objects.get(status="новый")
        p = PoziciyaZakaza(zakaz=z, material=m, kolichestvo=m.ostatok + 1)
        with self.assertRaises(ValidationError):
            p.full_clean()
        with self.assertRaises(ValidationError):
            p.save()
        m.refresh_from_db()
        self.assertGreaterEqual(m.ostatok, 0)

    def test_poziciya_neizmenyaema(self):
        p = PoziciyaZakaza.objects.first()
        p.kolichestvo = D(1)
        with self.assertRaises(ValidationError):
            p.save()
        with self.assertRaises(ValidationError):
            p.delete()

    def test_slozhnaya_zadacha_trebuet_stazh(self):
        novichok = Master.objects.get(stazh=0)
        z = Zadacha(zakaz=Zakaz.objects.first(), master=novichok, opisanie="x", slozhnaya=True)
        with self.assertRaises(ValidationError):
            z.full_clean()


class StranicyTest(TestCase):
    """Каждая роль видит свои страницы и не видит чужие."""

    @classmethod
    def setUpTestData(cls):
        call_command("zapolnit", stdout=open("/dev/null", "w"))

    def login(self, user, parol):
        self.assertTrue(self.client.login(username=user, password=parol))

    def test_katalog_publichnyi(self):
        self.assertContains(self.client.get(reverse("katalog")), "Аврора")

    def test_klient(self):
        self.login("klient", "klient12345")
        self.assertContains(self.client.get(reverse("moi_zakazy")), "Юбка-карандаш")
        self.assertEqual(self.client.get(reverse("moi_zapisi")).status_code, 200)
        chuzhoi = Zakaz.objects.exclude(klient__user__username="klient").first()
        self.assertEqual(self.client.get(reverse("zakaz_detail", args=[chuzhoi.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("sklad")).status_code, 403)
        r = self.client.post(reverse("moi_zapisi"), {
            "data": (timezone.localdate() + timedelta(days=5)).isoformat(),
            "vremya": "12:00", "tip_zapisi": "консультация"})
        self.assertEqual(r.status_code, 302)

    def test_agent(self):
        self.login("agent", "agent12345")
        for name in ["klienty", "zakazy", "zapisi", "klient_new", "zakaz_new"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.get(reverse("mastera")).status_code, 403)
        r = self.client.post(reverse("klient_new"), {
            "fio": "Новый Клиент", "telefon": "+7 999 000-00-00", "email": "",
            "login": "novyi", "parol": "pass12345"})
        self.assertEqual(r.status_code, 302)
        k = Klient.objects.get(fio="Новый Клиент")
        self.assertIsNotNone(k.user)
        r = self.client.post(reverse("merki_edit", args=[k.pk]), {
            "grud": "90", "taliya": "70", "bedra": "95",
            "data_snyatiya": timezone.localdate().isoformat()})
        self.assertEqual(r.status_code, 302)
        r = self.client.post(reverse("zakaz_new"), {
            "klient": k.pk, "model": Model.objects.first().pk,
            "data_oformleniya": timezone.localdate().isoformat(), "stoimost": ""})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(k.zakazy.get().stoimost, Model.objects.first().cena)

    def test_upravlyayushii(self):
        self.login("upravlyayushii", "upr12345")
        for name in ["panel", "zakazy", "modeli", "mastera", "sklad", "zakupki",
                     "zakupka_new", "model_new", "master_new", "material_new"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        z = Zakaz.objects.get(status="новый")
        url = reverse("zakaz_detail", args=[z.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        master = Master.objects.get(stazh=15)
        r = self.client.post(url, {"action": "zadacha", "zd-master": master.pk,
                                   "zd-opisanie": "Раскрой", "zd-slozhnaya": ""})
        self.assertEqual(r.status_code, 302)
        z.refresh_from_db()
        self.assertEqual(z.status, "в работе")
        # списание больше остатка — ошибка в форме, остаток не меняется
        m = Material.objects.get(nazvanie="Флизелин клеевой")
        r = self.client.post(url, {"action": "material", "mt-material": m.pk,
                                   "mt-kolichestvo": "999"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Недостаточно материала")
        # закупка увеличивает остаток
        do = m.ostatok
        r = self.client.post(reverse("zakupka_new"), {
            "data": timezone.localdate().isoformat(), "postavshik": "Тест",
            "material_0": m.pk, "kolichestvo_0": "5",
        })
        self.assertEqual(r.status_code, 302)
        m.refresh_from_db()
        self.assertEqual(m.ostatok, do + 5)

    def test_master(self):
        self.login("master", "master12345")
        self.assertContains(self.client.get(reverse("moi_zadachi")), "Пошив юбки")
        self.assertEqual(self.client.get(reverse("moi_primerki")).status_code, 200)
        self.assertEqual(self.client.get(reverse("klienty")).status_code, 403)
        z = Zadacha.objects.get(opisanie="Пошив юбки")
        r = self.client.post(reverse("moi_zadachi"), {"zadacha": z.pk, "status": "выполнена",
                                                      "kommentarii": "Готово"})
        self.assertEqual(r.status_code, 302)
        z.refresh_from_db()
        self.assertEqual(z.status, "выполнена")
        self.assertEqual(self.client.get(reverse("zakaz_detail", args=[z.zakaz_id])).status_code, 200)


class SostavnoiKlyuchTest(TestCase):
    """Позиции с составным первичным ключом (Номер_заказа, Номер_материала)."""

    @classmethod
    def setUpTestData(cls):
        call_command("zapolnit", stdout=open("/dev/null", "w"))

    def test_edinica_iz_materiala_i_pk(self):
        p = PoziciyaZakaza.objects.select_related("material").first()
        self.assertEqual(p.edinica_izmereniya, p.material.edinica_izmereniya)
        self.assertEqual(p.pk, (p.zakaz_id, p.material_id))
        self.assertEqual(PoziciyaZakaza.objects.get(pk=p.pk), p)

    def test_kolichestvo_ne_menshe_odnogo(self):
        z = Zakaz.objects.get(status="новый")
        p = PoziciyaZakaza(zakaz=z, material=Material.objects.first(), kolichestvo=D("0.5"))
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_zapolnit_povtorno_ne_dubliruet(self):
        n = Klient.objects.count()
        call_command("zapolnit", stdout=open("/dev/null", "w"))
        self.assertEqual(Klient.objects.count(), n)


class ZapisKlientaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("zapolnit", stdout=open("/dev/null", "w"))

    def test_klient_ne_mozhet_zapisatsya_dvazhdy_na_odno_vremya(self):
        self.client.login(username="klient", password="klient12345")
        data = {"data": (timezone.localdate() + timedelta(days=8)).isoformat(),
                "vremya": "12:00", "tip_zapisi": "консультация"}
        self.assertEqual(self.client.post(reverse("moi_zapisi"), data).status_code, 302)
        r = self.client.post(reverse("moi_zapisi"), data)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "уже есть запись")


class PrimerkaMasterTest(TestCase):
    """Примерку проводит самый опытный свободный мастер (портной или закройщик)."""

    @classmethod
    def setUpTestData(cls):
        call_command("zapolnit", stdout=open("/dev/null", "w"))

    def test_samyi_opytnyi_svobodnyi(self):
        den, chas = timezone.localdate() + timedelta(days=30), time(11)
        kandidaty = list(Master.objects.filter(rabotaet=True, dolzhnost__in=Primerka.DOLZHNOSTI_PRIMERKI)
                         .order_by("-stazh", "fio"))
        self.assertGreaterEqual(len(kandidaty), 2)
        z = Zakaz.objects.first()
        p1 = Primerka(zakaz=z, data=den, vremya=chas)
        p1.full_clean(); p1.save()
        self.assertEqual(p1.master, kandidaty[0])           # самый опытный
        p2 = Primerka(zakaz=z, data=den, vremya=chas)
        p2.full_clean(); p2.save()
        self.assertEqual(p2.master, kandidaty[1])           # первый занят — следующий по стажу
        with self.assertRaises(ValidationError):            # двух примерок одновременно у мастера быть не может
            Primerka(zakaz=z, data=den, vremya=chas, master=kandidaty[0]).full_clean()
        # причина назначения видна мастеру
        self.assertEqual(p1.pochemu_master(), ("opytnyi", []))
        self.assertEqual(p2.pochemu_master(), ("zanyaty", [kandidaty[0]]))
        p3 = Primerka(zakaz=z, data=den + timedelta(days=1), vremya=chas, master=kandidaty[1])
        p3.full_clean(); p3.save()
        self.assertEqual(p3.pochemu_master()[0], "vruchnuyu")  # самый опытный был свободен — выбрал управляющий

    def test_stranica_moi_zadachi_po_opytu(self):
        from django.contrib.auth.models import User
        u = User.objects.filter(master__isnull=False).first()
        self.client.force_login(u)
        r = self.client.get(reverse("moi_zadachi"))
        self.assertContains(r, "Мастера по опыту")
        stazhi = [s["m"].stazh for s in r.context["po_opytu"]]
        self.assertEqual(stazhi, sorted(stazhi, reverse=True))                 # от большего стажа к меньшему
        for s in r.context["po_opytu"]:
            if s["m"].stazh < 1:
                self.assertEqual(s["m"].n_slozh, 0)                               # ограничение 23
        if any(z.slozhnaya for z, _ in r.context["aktivnye"]):
            self.assertContains(r, "поручена вам по опыту")

    def test_stranica_moi_primerki(self):
        from django.contrib.auth.models import User
        u = User.objects.filter(master__isnull=False).first()
        self.client.force_login(u)
        r = self.client.get(reverse("moi_primerki"))
        self.assertContains(r, "Очередь на примерки")
        self.assertContains(r, "is-me")
        ochered = list(Primerka.ochered())
        self.assertEqual([s["m"] for s in r.context["ochered"]], ochered)
        if u.master in ochered:
            self.assertEqual(r.context["mesto"], ochered.index(u.master) + 1)


class PoiskKlientovTest(TestCase):
    """Поиск по полю, которое выбрал сотрудник: ФИО, телефон, № клиента, e-mail."""

    @classmethod
    def setUpTestData(cls):
        call_command("zapolnit", stdout=open("/dev/null", "w"))

    def test_poisk_po_polyam(self):
        vse = Klient.objects.all()
        k = Klient.objects.order_by("pk").first()
        self.assertEqual(poisk_klientov(vse, str(k.pk), "nomer"), [k])                   # «6» → только клиент № 6
        self.assertEqual(poisk_klientov(vse, f"№ 00{k.pk}", "nomer"), [k])
        cifry = "".join(c for c in k.telefon if c.isdigit())
        self.assertEqual(poisk_klientov(vse, cifry[1:4], "telefon")[0].telefon[:6], k.telefon[:6])  # 3 цифры — уже телефон
        self.assertIn(k, poisk_klientov(vse, cifry[-4:], "telefon"))                      # конец номера тоже находится
        self.assertEqual(poisk_klientov(vse, str(k.pk), "fio"), [])                       # цифры в поле ФИО — ничего
        fam = k.fio.split()[0]
        nashli = poisk_klientov(vse, fam[:4], "fio")
        self.assertIn(k, nashli)
        self.assertTrue(all(any(w.lower().startswith(fam[:4].lower()) for w in x.fio.split()) for x in nashli))
        domen = k.email.split("@")[1]
        self.assertTrue(all(domen in x.email for x in poisk_klientov(vse, domen, "email")))
        self.assertEqual(len(poisk_klientov(vse, "", "telefon")), vse.count())             # пусто — все клиенты

    def test_stranica(self):
        call_command("zapolnit", stdout=open("/dev/null", "w"))
        from django.contrib.auth.models import User
        self.client.force_login(User.objects.get(username="agent"))
        r = self.client.get(reverse("klienty"), {"po": "telefon", "q": "916"})
        self.assertContains(r, 'value="telefon" data-ph')
        self.assertContains(r, "Искать по")
        self.assertEqual(self.client.get(reverse("klienty"), {"po": "чужое", "q": "а"}).context["po"], "fio")


class Ogranichenie7i23Test(TestCase):
    """Ограничение 7 (описание и размер изделия) и 23 (стаж при сложных задачах)."""

    @classmethod
    def setUpTestData(cls):
        call_command("zapolnit", stdout=open("/dev/null", "w"))

    def test_zakaz_bez_merok_zapreshen(self):
        k = Klient.objects.create(fio="Новый Клиент", telefon="+7 999 000-00-01", email="new.client@mail.ru")
        with self.assertRaises(ValidationError) as cm:
            Zakaz(klient=k, model=Model.objects.first()).full_clean()
        self.assertIn("klient", cm.exception.message_dict)

    def test_opisanie_modeli_obyazatelno(self):
        from .forms import ModelForm
        f = ModelForm(data={"nazvanie": "Тест", "kategoriya": "юбка", "cena": "5000", "opisanie": ""})
        self.assertFalse(f.is_valid())
        self.assertIn("opisanie", f.errors)

    def test_stazh_pri_slozhnyh_zadachah(self):
        z = Zadacha.objects.filter(slozhnaya=True).exclude(status="выполнена").select_related("master").first()
        if z is None:  # в тестовых данных нет — создаём
            m = Master.objects.filter(stazh__gte=1).first()
            z = Zadacha.objects.create(zakaz=Zakaz.objects.first(), master=m, opisanie="Пошив", slozhnaya=True)
        m = z.master
        m.stazh = 0
        with self.assertRaises(ValidationError):
            m.full_clean()


@override_settings(PROVERKA_V_BAZE=True)
class ProverkaVBazeTest(TestCase):
    """PROVERKA_V_BAZE: правила п. 3.3 Django не проверяет — их проверяет база,
    а сообщение базы показывается над формой."""

    @classmethod
    def setUpTestData(cls):
        call_command("zapolnit", stdout=open("/dev/null", "w"))

    def test_django_ne_proveryaet_pravila(self):
        # дата оформления в будущем и цена 0: Django пропускает, решает база
        Zakaz(klient=Klient.objects.last(), model=Model.objects.first(), stoimost=D("10"),
              data_oformleniya=timezone.localdate() + timedelta(days=1)).full_clean()
        Model(nazvanie="X", kategoriya="юбка", cena=0, opisanie="тест").full_clean()

    def test_cena_0_otvet_bazy_nad_formoi(self):
        self.client.login(username="upravlyayushii", password="upr12345")
        n = Model.objects.count()
        r = self.client.post(reverse("model_new"), {"nazvanie": "X", "kategoriya": "юбка",
                                                    "cena": "0", "opisanie": "тест"})
        self.assertContains(r, "База данных отклонила изменение")
        self.assertEqual(Model.objects.count(), n)

    def test_dubl_telefona_otvet_bazy_nad_formoi(self):
        self.client.login(username="agent", password="agent12345")
        r = self.client.post(reverse("klient_new"),
                             {"fio": "Дубль", "telefon": Klient.objects.first().telefon, "email": ""})
        self.assertContains(r, "База данных отклонила изменение")

    def test_tekst_iz_triggera(self):
        d = "[Microsoft][ODBC Driver 17 for SQL Server][SQL Server]"
        e = DatabaseError("42000", f"[42000] {d}Транзакция завершилась в триггере. Выполнение пакета "
                                   f"прервано. (3609) (SQLExecDirectW); [01000] {d}ошибка: не более двух "
                                   f"активных заказов (0)")
        self.assertEqual(soobshenie_bd(e), "ошибка: не более двух активных заказов")
        e = IntegrityError("23000", f"[23000] {d}Конфликт инструкции INSERT с ограничением CHECK "
                                    f"\"ck_модель_цена\". (547) (SQLExecDirectW); [01000] {d}Выполнение "
                                    f"данной инструкции было прервано. (3621)")
        self.assertEqual(soobshenie_bd(e), 'Конфликт инструкции INSERT с ограничением CHECK "ck_модель_цена".')
