"""Ограничения уникальности на уровне SQL Server:
  * уникальный e-mail клиента (NULL допускается у нескольких клиентов);
  * клиент не может иметь 2 записи на одно и то же время.
Индекс создаётся, только если в таблице сейчас нет дубликатов
(иначе приложение всё равно проверяет эти правила само).
"""
from django.db import migrations

SQL = [
    """IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_Клиент_Email')
   AND NOT EXISTS (SELECT [Email] FROM dbo.[Клиент] WHERE [Email] IS NOT NULL
                   GROUP BY [Email] HAVING COUNT(*) > 1)
    CREATE UNIQUE INDEX UX_Клиент_Email ON dbo.[Клиент]([Email]) WHERE [Email] IS NOT NULL;""",
    """IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_Запись_Клиент_Время')
   AND NOT EXISTS (SELECT 1 FROM dbo.[Запись]
                   GROUP BY [Номер_клиента], [Дата], [Время] HAVING COUNT(*) > 1)
    CREATE UNIQUE INDEX UX_Запись_Клиент_Время ON dbo.[Запись]([Номер_клиента], [Дата], [Время]);""",
]


def sozdat(apps, schema_editor):
    if schema_editor.connection.vendor != "microsoft":
        return
    with schema_editor.connection.cursor() as cursor:
        for statement in SQL:
            cursor.execute(statement)


class Migration(migrations.Migration):
    dependencies = [("atelier", "0002_dopolnit_tablicy")]
    operations = [migrations.RunPython(sozdat, migrations.RunPython.noop)]
