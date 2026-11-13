"""Дополняет существующие таблицы базы «projet corse» колонками, нужными приложению.

Выполняется только на SQL Server и только один раз (каждая команда
проверяет, не сделано ли это уже). Данные в таблицах не удаляются.

  Заказ            + Статус
  Задача           + Статус, Сложная, Комментарий
  График_примерок  + Номер_мастера, Результат; снят CHECK «Дата >= сегодня»
                     (иначе нельзя записать результат прошедшей примерки)
  Мастер           + Работает, user_id
  Клиент           + user_id
  Запись           Тип_записи: VARCHAR → NVARCHAR (русский текст при любой кодировке)
"""
from django.conf import settings
from django.db import migrations

STATUSY_ZAKAZA = "N'новый', N'в работе', N'примерка', N'готов', N'выдан', N'отменён'"
STATUSY_ZADACHI = "N'назначена', N'в работе', N'выполнена', N'проблема'"
TIPY_ZAPISI = "N'снятие мерок', N'примерка', N'консультация'"


def add_column(table, column, definition):
    return (f"IF COL_LENGTH(N'dbo.{table}', N'{column}') IS NULL "
            f"ALTER TABLE dbo.[{table}] ADD [{column}] {definition};")


def drop_checks(table, like):
    """Удаляет CHECK-ограничения таблицы, текст которых содержит `like`."""
    return f"""
DECLARE @sql NVARCHAR(MAX) = N'';
SELECT @sql += N'ALTER TABLE dbo.[{table}] DROP CONSTRAINT ' + QUOTENAME(name) + N';'
FROM sys.check_constraints
WHERE parent_object_id = OBJECT_ID(N'dbo.{table}') AND definition LIKE N'%{like}%';
EXEC sp_executesql @sql;"""


SQL = [
    # --- Заказ ---------------------------------------------------------------
    add_column("Заказ", "Статус",
               "NVARCHAR(20) NOT NULL CONSTRAINT DF_Заказ_Статус DEFAULT N'новый' "
               f"CONSTRAINT CK_Заказ_Статус CHECK ([Статус] IN ({STATUSY_ZAKAZA}))"),
    # --- Задача --------------------------------------------------------------
    add_column("Задача", "Статус",
               "NVARCHAR(20) NOT NULL CONSTRAINT DF_Задача_Статус DEFAULT N'назначена' "
               f"CONSTRAINT CK_Задача_Статус CHECK ([Статус] IN ({STATUSY_ZADACHI}))"),
    add_column("Задача", "Сложная", "BIT NOT NULL CONSTRAINT DF_Задача_Сложная DEFAULT 0"),
    add_column("Задача", "Комментарий",
               "NVARCHAR(500) NOT NULL CONSTRAINT DF_Задача_Комментарий DEFAULT N''"),
    # --- График_примерок -----------------------------------------------------
    add_column("График_примерок", "Номер_мастера",
               "INT NULL CONSTRAINT FK_Примерка_Мастер "
               "FOREIGN KEY REFERENCES dbo.[Мастер]([Номер_мастера])"),
    add_column("График_примерок", "Результат",
               "NVARCHAR(500) NOT NULL CONSTRAINT DF_Примерка_Результат DEFAULT N''"),
    drop_checks("График_примерок", "getdate"),
    # --- Мастер / Клиент: увольнение и учётные записи ------------------------
    add_column("Мастер", "Работает", "BIT NOT NULL CONSTRAINT DF_Мастер_Работает DEFAULT 1"),
    add_column("Мастер", "user_id",
               "INT NULL CONSTRAINT FK_Мастер_user FOREIGN KEY REFERENCES dbo.auth_user(id)"),
    add_column("Клиент", "user_id",
               "INT NULL CONSTRAINT FK_Клиент_user FOREIGN KEY REFERENCES dbo.auth_user(id)"),
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_Мастер_user') "
    "CREATE UNIQUE INDEX UX_Мастер_user ON dbo.[Мастер](user_id) WHERE user_id IS NOT NULL;",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_Клиент_user') "
    "CREATE UNIQUE INDEX UX_Клиент_user ON dbo.[Клиент](user_id) WHERE user_id IS NOT NULL;",
    # --- Запись: Тип_записи в NVARCHAR ---------------------------------------
    f"""
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID(N'dbo.Запись')
           AND name = N'Тип_записи' AND system_type_id = TYPE_ID('varchar'))
BEGIN
    {drop_checks("Запись", "Тип_записи")}
    EXEC(N'ALTER TABLE dbo.[Запись] ALTER COLUMN [Тип_записи] NVARCHAR(30) NOT NULL');
    EXEC(N'ALTER TABLE dbo.[Запись] ADD CONSTRAINT CK_Запись_Тип
           CHECK ([Тип_записи] IN ({TIPY_ZAPISI.replace("'", "''")}))');
END""",
]


def dopolnit(apps, schema_editor):
    if schema_editor.connection.vendor != "microsoft":
        return  # на других СУБД таблицы создаются Django целиком
    with schema_editor.connection.cursor() as cursor:
        for statement in SQL:
            cursor.execute(statement)


class Migration(migrations.Migration):
    dependencies = [
        ("atelier", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [migrations.RunPython(dopolnit, migrations.RunPython.noop)]
