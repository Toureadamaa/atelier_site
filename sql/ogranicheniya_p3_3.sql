-- ограничения предметной области (п. 3.3), база данных projet corse (t-sql)
-- туре а. а., группа идб-24-07
-- каждый create trigger выполняется отдельным пакетом (go)

use [projet corse]
go

-- 1. у каждого клиента должен быть уникальный номер телефона и уникальный e-mail
alter table клиент add constraint uq_клиент_телефон unique (телефон)
alter table клиент add constraint uq_клиент_email unique (email)
go

-- 2. клиент не может иметь более двух активных заказов одновременно
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
go

-- 3. клиент не может иметь 2 записи на одно и то же время
alter table запись
add constraint uq_запись_клиент_время unique (номер_клиента, дата, время)
go

-- 4. дата оформления заказа не может быть в будущем
alter table заказ
add constraint ck_заказ_датаоформления check (дата_оформления <= getdate())
go

-- 5. дата завершения заказа не может быть раньше даты его оформления
alter table заказ
add constraint ck_заказ_даты check (дата_завершения >= дата_оформления)
go

-- 6. заказ должен содержать хотя бы одно изделие
alter table заказ alter column номер_модели int not null
go

-- 7. каждое изделие в заказе должно иметь описание (модель, размер, материал)
alter table модель
add constraint ck_модель_описание check (описание is not null and len(описание) > 0)
go

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
go

-- 8. стоимость заказа должна быть строго больше 0
alter table заказ add constraint ck_заказ_стоимость check (стоимость > 0)
go

-- 9. каждая задача заказа должна иметь назначенного ответственного мастера
alter table задача alter column номер_мастера int not null
go

-- 10. цена модели должна быть строго больше 0
alter table модель add constraint ck_модель_цена check (цена > 0)
go

-- 11. категория модели должна быть из допустимого списка
alter table модель
add constraint ck_модель_категория
check (категория in (N'платье', N'костюм', N'пальто', N'юбка', N'брюки', N'рубашка'))
go

-- 12. значения мерок (грудь, талия, бедра) должны быть строго больше 0
alter table мерки
add constraint ck_мерки_значения check (грудь > 0 and талия > 0 and бедра > 0)
go

-- 13. остаток материала на складе не может быть отрицательным
alter table материал add constraint ck_материал_остаток check (остаток >= 0)
go

-- 14. в заказ можно добавлять только материалы, которые есть на складе в достаточном количестве
-- 15. при подтверждении заказа количество материалов на складе уменьшается (часть else)
-- 17. материал не может быть использован, если его недостаточно на складе (часть if)
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
go

-- 16. при поступлении новых материалов их количество на складе увеличивается
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
go

-- 18. использованный материал не подлежит изменению
create trigger tr_позициязаказа_неизменна on позиция_заказа
instead of update, delete
as
begin
    print N'ошибка: использованный материал изменять нельзя'
end
go

-- 19. единица измерения материала должна быть из допустимого списка
alter table материал
add constraint ck_материал_единица
check (единица_измерения in (N'м', N'м²', N'кг', N'шт', N'катушка'))
go

alter table позиция_заказа
add constraint ck_позициязаказа_единица
check (единица_измерения in (N'м', N'м²', N'кг', N'шт', N'катушка'))
go

-- 20. количество в позиции закупки должно быть не менее 1
alter table позиция_закупки
add constraint ck_позициязакупки_количество check (количество >= 1)
go

-- 21. количество в позиции заказа должно быть не менее 1
alter table позиция_заказа
add constraint ck_позициязаказа_количество check (количество >= 1)
go

-- 22. у каждого мастера должен быть уникальный номер телефона
alter table мастер
add constraint uq_мастер_телефон unique (номер_телефона)
go

-- 23. сотрудник должен иметь стаж работы не менее 1 года для выполнения сложных заказов
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
go

-- 24. должность мастера должна быть из допустимого списка
alter table мастер
add constraint ck_мастер_должность
check (должность in (N'портной', N'закройщик', N'вышивальщик', N'отделочник'))
go

-- 25. тип записи должен быть из допустимого списка
alter table запись
add constraint ck_запись_тип
check (тип_записи in (N'снятие мерок', N'примерка', N'консультация'))
go

-- 26. дата и время записи не могут быть в прошлом
-- with nocheck: старые записи не проверяются, новые и изменённые — проверяются
alter table запись with nocheck
add constraint ck_запись_дата_время
check (cast(дата as datetime) + cast(время as datetime) >= getdate())
go
