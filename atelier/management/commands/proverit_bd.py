"""Проверяет, что модели Django совпадают с таблицами в SQL Server.

Запуск:  python manage.py proverit_bd
Для каждой таблицы читается одна строка со всеми колонками; если имя
колонки в базе отличается, команда покажет, какой именно.
"""
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import DatabaseError


class Command(BaseCommand):
    help = "Проверка соответствия моделей и таблиц базы данных"

    def handle(self, *args, **opts):
        oshibki = 0
        for model in apps.get_app_config("atelier").get_models():
            table = model._meta.db_table
            try:
                n = model.objects.count()
                model.objects.all()[:1].exists()
                list(model.objects.all()[:1])
                self.stdout.write(self.style.SUCCESS(f"OK   {table:<18} строк: {n}"))
            except DatabaseError as e:
                oshibki += 1
                kolonki = ", ".join(f.column for f in model._meta.concrete_fields)
                self.stdout.write(self.style.ERROR(f"ОШИБКА {table}: {e}"))
                self.stdout.write(f"       ожидаемые колонки: {kolonki}")
        if oshibki:
            self.stdout.write(self.style.ERROR(
                f"\nНайдено ошибок: {oshibki}. Пришлите этот вывод — поправим имена колонок."))
        else:
            self.stdout.write(self.style.SUCCESS("\nВсе 12 таблиц совпадают с моделями."))
