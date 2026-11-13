# Ограничения предметной области (п. 3.3)

База данных швейного ателье «projet corse», Microsoft SQL Server. Туре А. А., группа ИДБ-24-07.

Весь код в одном файле: [`sql/ogranicheniya_p3_3.sql`](../sql/ogranicheniya_p3_3.sql).

## 1. У каждого клиента должен быть уникальный номер телефона и уникальный e-mail

```sql
alter table клиент add constraint uq_клиент_телефон unique (телефон)
alter table клиент add constraint uq_клиент_email unique (email)
```

## 2. Клиент не может иметь более двух активных заказов одновременно

```sql
create trigger tr_заказ_активные on заказ
after insert, update
as
begin
    declare @client int, @cnt int
    select @client = номер_клиента from inserted
    select @cnt = count(*) from заказ
    where номер_клиента = @client
      and статус in (N'новый', N'в работе', N'примерка', N'готов')

    if @cnt > 2
    begin
        print N'ошибка: не более двух активных заказов'
        rollback transaction
    end
end
```

## 3. Клиент не может иметь 2 записи на одно и то же время

```sql
alter table запись
add constraint uq_запись_клиент_время unique (номер_клиента, дата, время)
```

## 4. Заказ может быть оформлен только на текущую дату или ранее (дата оформления не может быть в будущем)

```sql
alter table заказ
add constraint ck_заказ_датаоформления check (дата_оформления <= getdate())
```

## 5. Дата завершения заказа не может быть раньше даты его оформления

```sql
alter table заказ
add constraint ck_заказ_даты check (дата_завершения >= дата_оформления)
```

## 6. Заказ должен содержать хотя бы одно изделие

```sql
alter table заказ alter column номер_модели int not null
```

## 7. Каждое изделие в заказе должно иметь описание (модель, размер, материал)

```sql
alter table модель
add constraint ck_модель_описание check (описание is not null and len(описание) > 0)

create trigger tr_заказ_мерки on заказ
after insert
as
begin
    declare @client int
    select @client = номер_клиента from inserted

    if not exists (select * from мерки where номер_клиента = @client)
    begin
        print N'ошибка: у клиента не сняты мерки'
        rollback transaction
    end
end
```

## 8. Стоимость заказа должна быть строго больше 0 (стоимость > 0)

```sql
alter table заказ add constraint ck_заказ_стоимость check (стоимость > 0)
```

## 9. Каждая задача заказа должна иметь назначенного ответственного мастера

```sql
alter table задача alter column номер_мастера int not null
```

## 10. Цена модели должна быть строго больше 0 (цена > 0)

```sql
alter table модель add constraint ck_модель_цена check (цена > 0)
```

## 11. Категория модели должна быть из допустимого списка: платье, костюм, пальто, юбка, брюки, рубашка

```sql
alter table модель
add constraint ck_модель_категория
check (категория in (N'платье', N'костюм', N'пальто', N'юбка', N'брюки', N'рубашка'))
```

## 12. Значения мерок (грудь, талия, бедра) должны быть строго больше 0

```sql
alter table мерки
add constraint ck_мерки_значения check (грудь > 0 and талия > 0 and бедра > 0)
```

## 13. Остаток материала на складе не может быть отрицательным (остаток >= 0)

```sql
alter table материал add constraint ck_материал_остаток check (остаток >= 0)
```

## 14. В заказ можно добавлять только те материалы, которые есть на складе в достаточном количестве

```sql
create trigger tr_позициязаказа_списание on позиция_заказа
after insert
as
begin
    declare @mat int, @kol decimal(10,2), @ost decimal(10,2)
    select @mat = номер_материала, @kol = количество from inserted
    select @ost = остаток from материал where номер_материала = @mat

    if @kol > @ost
    begin
        print N'ошибка: материала не хватает'
        rollback transaction
    end
    else
        update материал
        set остаток = остаток - @kol
        where номер_материала = @mat
end
```

## 15. При подтверждении заказа количество материалов на складе уменьшается в соответствии со спецификацией

```sql
-- тот же триггер tr_позициязаказа_списание (ограничение 14), часть else
else
    update материал
    set остаток = остаток - @kol
    where номер_материала = @mat
```

## 16. При поступлении новых материалов их количество на складе увеличивается

```sql
create trigger tr_позициязакупки_поступление on позиция_закупки
after insert
as
begin
    declare @mat int, @kol decimal(10,2)
    select @mat = номер_материала, @kol = количество from inserted

    update материал
    set остаток = остаток + @kol
    where номер_материала = @mat
end
```

## 17. Материал не может быть использован, если его недостаточно на складе

```sql
-- тот же триггер tr_позициязаказа_списание (ограничение 14), часть if
if @kol > @ost
begin
    print N'ошибка: материала не хватает'
    rollback transaction
end
```

## 18. Использованный материал не подлежит изменению

```sql
create trigger tr_позициязаказа_неизменна on позиция_заказа
instead of update, delete
as
begin
    print N'ошибка: использованный материал изменять нельзя'
end
```

## 19. Единица измерения материала должна быть из допустимого списка: м, м², кг, шт, катушка

```sql
alter table материал
add constraint ck_материал_единица
check (единица_измерения in (N'м', N'м²', N'кг', N'шт', N'катушка'))

alter table позиция_заказа
add constraint ck_позициязаказа_единица
check (единица_измерения in (N'м', N'м²', N'кг', N'шт', N'катушка'))
```

## 20. Количество в позиции закупки должно быть не менее 1 (количество >= 1)

```sql
alter table позиция_закупки
add constraint ck_позициязакупки_количество check (количество >= 1)
```

## 21. Количество в позиции заказа должно быть не менее 1 (количество >= 1)

```sql
alter table позиция_заказа
add constraint ck_позициязаказа_количество check (количество >= 1)
```

## 22. У каждого мастера должен быть уникальный номер телефона

```sql
alter table мастер
add constraint uq_мастер_телефон unique (номер_телефона)
```

## 23. Сотрудник должен иметь стаж работы не менее 1 года для выполнения сложных заказов

```sql
create trigger tr_задача_стаж on задача
after insert, update
as
begin
    declare @master int, @sl int, @st int
    select @master = номер_мастера, @sl = сложная from inserted
    select @st = стаж from мастер where номер_мастера = @master

    if @sl = 1 and @st < 1
    begin
        print N'ошибка: нужен стаж не менее 1 года'
        rollback transaction
    end
end
```

## 24. Должность мастера должна быть из допустимого списка: портной, закройщик, вышивальщик, отделочник

```sql
alter table мастер
add constraint ck_мастер_должность
check (должность in (N'портной', N'закройщик', N'вышивальщик', N'отделочник'))
```

## 25. Тип_записи должен быть из допустимого списка: снятие мерок, примерка, консультация

```sql
alter table запись
add constraint ck_запись_тип
check (тип_записи in (N'снятие мерок', N'примерка', N'консультация'))
```

## 26. Дата и время записи не могут быть в прошлом

```sql
-- with nocheck: старые записи не проверяются, новые и изменённые — проверяются
alter table запись with nocheck
add constraint ck_запись_дата_время
check (cast(дата as datetime) + cast(время as datetime) >= getdate())
```
