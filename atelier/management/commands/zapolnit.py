"""Заполнение БД тестовыми данными (Приложение Б отчёта).

Запуск:  python manage.py zapolnit
"""
from datetime import time, timedelta
from decimal import Decimal as D

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from atelier import roles
from atelier.models import (Klient, Master, Material, Merki, Model, PoziciyaZakaza,
                            PoziciyaZakupki, Primerka, Zadacha, Zakaz, Zakupka, Zapis)


class Command(BaseCommand):
    help = "Создаёт роли, пользователей и тестовые данные ателье"

    def user(self, login, parol, rol=None, superuser=False):
        u, created = User.objects.get_or_create(username=login)
        if created:
            u.set_password(parol)
            u.is_superuser = u.is_staff = superuser
            u.save()
        if rol:
            u.groups.add(Group.objects.get(name=rol))
        return u

    @transaction.atomic
    def handle(self, *args, **opts):
        for r in roles.VSE_ROLI:
            Group.objects.get_or_create(name=r)
        self.user("admin", "admin", superuser=True)
        self.user("upravlyayushii", "upr12345", roles.UPRAVLYAYUSHII)
        self.user("agent", "agent12345", roles.AGENT)

        if Klient.objects.exists():
            self.stdout.write("В базе уже есть данные — тестовые записи не добавляются.")
        else:
            self.testovye_dannye()
        self.privyazat_uchetki()

        self.stdout.write(self.style.SUCCESS(
            "Готово! Пользователи: admin/admin, upravlyayushii/upr12345, agent/agent12345, "
            "master/master12345, zakroishik/master12345, klient/klient12345"))

    def privyazat_uchetki(self):
        """Связывает тестовые учётные записи с карточками клиента и мастеров."""
        if not Klient.objects.filter(user__username="klient").exists():
            k = Klient.objects.filter(user__isnull=True).order_by("id").first()
            if k:
                k.user = self.user("klient", "klient12345", roles.KLIENT)
                k.save(update_fields=["user"])
        for login in ("master", "zakroishik"):
            if Master.objects.filter(user__username=login).exists():
                continue
            m = Master.objects.filter(user__isnull=True, rabotaet=True).order_by("-stazh", "id").first()
            if m:
                m.user = self.user(login, "master12345", roles.MASTER)
                m.save(update_fields=["user"])

    def testovye_dannye(self):
        t = timezone.localdate()
        d = lambda n: t + timedelta(days=n)  # noqa: E731

        # --- Модели ---------------------------------------------------------
        for naz, kat, cena, op in [
            ("Вечернее платье «Аврора»", "платье", 18500, "Длинное платье из атласа, открытая спина"),
            ("Платье-футляр «Классика»", "платье", 9800, "Офисное платье до колена"),
            ("Деловой костюм «Премьер»", "костюм", 32000, "Пиджак и брюки, шерсть"),
            ("Пальто «Вена»", "пальто", 27500, "Прямое пальто из кашемира"),
            ("Юбка-карандаш", "юбка", 4500, "Классическая юбка миди"),
            ("Брюки палаццо", "брюки", 6200, "Широкие брюки с высокой посадкой"),
            ("Рубашка оверсайз", "рубашка", 5300, "Хлопковая рубашка свободного кроя"),
        ]:
            Model.objects.create(nazvanie=naz, kategoriya=kat, cena=D(cena), opisanie=op)
        M = list(Model.objects.order_by("id"))

        # --- Клиенты (первый — с учётной записью) --------------------------
        kl = []
        for i, (fio, tel, mail) in enumerate([
            ("Иванова Анна Сергеевна", "+7 916 111-22-33", "ivanova@mail.ru"),
            ("Петров Дмитрий Олегович", "+7 903 222-33-44", "petrov@yandex.ru"),
            ("Смирнова Елена Викторовна", "+7 925 333-44-55", None),
            ("Кузнецова Мария Андреевна", "+7 977 444-55-66", "kuznetsova@gmail.com"),
            ("Соколов Артём Игоревич", "+7 915 555-66-77", "sokolov@mail.ru"),
            ("Попова Ольга Николаевна", "+7 926 666-77-88", None),
        ]):
            k = Klient.objects.create(fio=fio, telefon=tel, email=mail, data_registracii=d(-60 + i * 7))
            kl.append(k)

        for k, (g, ta, b) in zip(kl, [(88, 66, 94), (102, 88, 100), (92, 72, 98),
                                      (84, 62, 90), (98, 84, 96)]):
            Merki.objects.create(klient=k, grud=g, taliya=ta, bedra=b, data_snyatiya=k.data_registracii)

        # --- Мастера --------------------------------------------------------
        ms = []
        for fio, dl, st, tel in [
            ("Фёдорова Галина Петровна", "портной", 15, "+7 901 100-00-01"),
            ("Морозов Игорь Васильевич", "закройщик", 8, "+7 901 100-00-02"),
            ("Волкова Светлана Ильинична", "вышивальщик", 4, "+7 901 100-00-03"),
            ("Лебедева Ксения Алексеевна", "отделочник", 0, "+7 901 100-00-04"),
        ]:
            ms.append(Master.objects.create(fio=fio, dolzhnost=dl, stazh=st, nomer_telefona=tel))

        # --- Материалы и закупки (остаток формируется закупками) ------------
        mat = [Material.objects.create(nazvanie=n, tip=tp, edinica_izmereniya=e) for n, tp, e in [
            ("Атлас бордовый", "ткань", "м"), ("Шерсть костюмная серая", "ткань", "м"),
            ("Кашемир пальтовый", "ткань", "м"), ("Хлопок рубашечный белый", "ткань", "м"),
            ("Подкладка вискоза", "ткань", "м"), ("Пуговицы костяные 20 мм", "фурнитура", "шт"),
            ("Молния потайная 60 см", "фурнитура", "шт"), ("Нитки полиэстер", "фурнитура", "катушка"),
            ("Флизелин клеевой", "прокладка", "м²"),
        ]]
        for dn, post, poz in [
            (-45, "ООО «Текстиль-Опт»", [(0, 20), (1, 30), (2, 15), (3, 25), (4, 40)]),
            (-20, "ИП Сидоров (фурнитура)", [(5, 200), (6, 50), (7, 60), (8, 10)]),
            (-5, "ООО «Текстиль-Опт»", [(0, 10), (2, 5)]),
        ]:
            z = Zakupka.objects.create(data=d(dn), postavshik=post)
            for i, q in poz:
                PoziciyaZakupki.objects.create(zakupka=z, material=mat[i], kolichestvo=D(q))

        # --- Заказы ---------------------------------------------------------
        def zakaz(k, model, dn, status, stoimost=None, zav=None):
            return Zakaz.objects.create(klient=k, model=model, data_oformleniya=d(dn), status=status,
                                        stoimost=stoimost or model.cena,
                                        data_zaversheniya=d(zav) if zav is not None else None)

        z1 = zakaz(kl[0], M[0], -30, "выдан", D(19900), zav=-3)
        z2 = zakaz(kl[0], M[4], -6, "в работе")
        z3 = zakaz(kl[1], M[2], -14, "примерка", D(34500))
        z4 = zakaz(kl[2], M[3], -10, "в работе")
        z5 = zakaz(kl[3], M[1], -2, "новый")
        z6 = zakaz(kl[4], M[6], -25, "готов")
        zakaz(kl[5], M[5], -40, "отменён")

        for z, items in [(z1, [(0, 4.5), (4, 3), (6, 1), (7, 2)]),
                         (z2, [(1, 1.2), (6, 1)]),
                         (z3, [(1, 3.5), (4, 2), (5, 6), (8, 1.5)]),
                         (z4, [(2, 3.2), (4, 2.5), (5, 5)]),
                         (z6, [(3, 2.8), (5, 9), (7, 1)])]:
            for i, q in items:
                PoziciyaZakaza.objects.create(zakaz=z, material=mat[i], kolichestvo=D(str(q)))

        for z, m, op, st, sl, dn, kom in [
            (z1, ms[1], "Раскрой платья", "выполнена", True, -28, ""),
            (z1, ms[0], "Пошив и сборка", "выполнена", True, -25, ""),
            (z1, ms[3], "Отделка, ВТО", "выполнена", False, -8, ""),
            (z2, ms[1], "Раскрой юбки", "выполнена", False, -5, ""),
            (z2, ms[0], "Пошив юбки", "в работе", False, -3, ""),
            (z3, ms[1], "Раскрой костюма", "выполнена", True, -12, ""),
            (z3, ms[0], "Пошив пиджака и брюк", "выполнена", True, -10, ""),
            (z4, ms[1], "Раскрой пальто", "в работе", True, -8, ""),
            (z4, ms[2], "Вышивка монограммы на подкладке", "проблема", False, -7,
             "Нет ниток нужного оттенка, нужна закупка"),
            (z6, ms[0], "Пошив рубашки", "выполнена", False, -20, ""),
        ]:
            Zadacha.objects.create(zakaz=z, master=m, opisanie=op, status=st, slozhnaya=sl,
                                   data_naznacheniya=d(dn), kommentarii=kom)

        for z, dn, h, m, rez in [
            (z1, -12, 15, ms[0], "Ушить по талии на 1 см"),
            (z1, -5, 16, ms[0], "Изделие соответствует, готово к выдаче"),
            (z3, -2, 18, ms[0], "Укоротить рукава на 1,5 см"),
            (z3, 2, 18, ms[0], ""),
            (z2, 3, 11, ms[0], ""),
            (z4, 7, 12, ms[1], ""),
        ]:
            Primerka.objects.create(zakaz=z, data=d(dn), vremya=time(h), master=m, rezultat=rez)

        for k, dn, h, tip in [
            (kl[0], 3, 11, "примерка"), (kl[3], 1, 10, "снятие мерок"),
            (kl[5], 2, 14, "консультация"), (kl[1], 2, 18, "примерка"),
            (kl[4], 4, 17, "консультация"),
        ]:
            Zapis.objects.create(klient=k, data=d(dn), vremya=time(h), tip_zapisi=tip)
