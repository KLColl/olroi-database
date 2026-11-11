BEGIN;

INSERT INTO bookstore.authors(first_name,last_name,country) VALUES

    ('Тарас','Шевченко','Україна'),
    ('Леся','Українка','Україна'),
    ('Іван','Франко','Україна'),
    ('Ольга','Кобилянська','Україна'),
    ('Ліна','Костенко','Україна'),
    ('Юрій','Андрухович','Україна'),
    ('Сергій','Жадан','Україна'),
    ('Оксана','Забужко','Україна'),
    ('Валер’ян','Підмогильний','Україна'),
    ('Михайло','Коцюбинський','Україна');

INSERT INTO bookstore.categories(category_name,description) VALUES

    ('Поезія','Поетичні твори та збірки'),
    ('Драма','П’єси та драматичні поеми'),
    ('Роман','Великі прозові твори'),
    ('Історична проза','Художні твори на історичну тематику'),
    ('Сучасна проза','Проза сучасних українських авторів'),
    ('Повість','Прозові твори середнього обсягу'),
    ('Новела','Короткі прозові твори'),
    ('Збірка оповідань','Збірки короткої художньої прози'),
    ('Літературна критика','Дослідження літератури та культури'),
    ('Есеїстика','Есе та авторські роздуми');

INSERT INTO bookstore.books(isbn,title,author_id,category_id,publication_year,price,stock_quantity) VALUES

    ('9780000000019','Кобзар',1,1,1840,320.00,25),
    ('9780000000026','Гайдамаки',1,1,1841,240.00,18),
    ('9780000000033','Лісова пісня',2,2,1911,280.00,20),
    ('9780000000040','Кассандра',2,2,1908,260.00,12),
    ('9780000000057','Захар Беркут',3,4,1883,310.00,16),
    ('9780000000064','Перехресні стежки',3,3,1900,350.00,14),
    ('9780000000071','Земля',4,3,1902,290.00,15),
    ('9780000000088','Людина',4,6,1894,230.00,11),
    ('9780000000095','Маруся Чурай',5,1,1979,390.00,22),
    ('9780000000101','Записки українського самашедшого',5,3,2010,450.00,17),
    ('9780000000118','Московіада',6,3,1993,340.00,13),
    ('9780000000125','Дезорієнтація на місцевості',6,10,1999,300.00,10),
    ('9780000000132','Інтернат',7,5,2017,420.00,24),
    ('9780000000149','Біг Мак',7,8,2003,330.00,14),
    ('9780000000156','Польові дослідження з українського сексу',8,5,1996,360.00,16),
    ('9780000000163','Notre Dame d’Ukraine',8,9,2007,520.00,9),
    ('9780000000170','Місто',9,3,1928,380.00,19),
    ('9780000000187','Невеличка драма',9,3,1930,310.00,12),
    ('9780000000194','Тіні забутих предків',10,6,1911,270.00,21),
    ('9780000000200','Intermezzo',10,7,1908,220.00,15);

INSERT INTO bookstore.customers(full_name,email,phone,created_at) VALUES

    ('Ілля Якимов','illia@example.com','+380501110001',CURRENT_TIMESTAMP-INTERVAL '60 days'),
    ('Марія Коваль','maria@example.com','+380501110002',CURRENT_TIMESTAMP-INTERVAL '59 days'),
    ('Олег Бондар','oleh@example.com','+380501110003',CURRENT_TIMESTAMP-INTERVAL '58 days'),
    ('Анна Мельник','anna@example.com','+380501110004',CURRENT_TIMESTAMP-INTERVAL '57 days'),
    ('Дмитро Шевчук','dmytro@example.com','+380501110005',CURRENT_TIMESTAMP-INTERVAL '56 days'),
    ('Софія Ткачук','sofia@example.com','+380501110006',CURRENT_TIMESTAMP-INTERVAL '55 days'),
    ('Андрій Кравчук','andrii@example.com','+380501110007',CURRENT_TIMESTAMP-INTERVAL '54 days'),
    ('Олена Савчук','olena@example.com','+380501110008',CURRENT_TIMESTAMP-INTERVAL '53 days'),
    ('Максим Поліщук','maksym@example.com','+380501110009',CURRENT_TIMESTAMP-INTERVAL '52 days'),
    ('Ірина Романюк','iryna@example.com','+380501110010',CURRENT_TIMESTAMP-INTERVAL '51 days');

INSERT INTO bookstore.orders(customer_id,status,created_at) SELECT customer_id,'Draft',CURRENT_TIMESTAMP-make_interval(days=>customer_id::INTEGER) FROM bookstore.customers ORDER BY customer_id;

INSERT INTO bookstore.order_items(order_id,book_id,quantity,unit_price) SELECT o.order_id,b.book_id,(o.order_id%3+1)::INTEGER,ROUND(b.price*CASE WHEN o.order_id%2=0 THEN 0.95 ELSE 1.00 END,2) FROM bookstore.orders o JOIN bookstore.books b ON b.book_id IN(o.order_id*2-1,o.order_id*2) ORDER BY o.order_id,b.book_id;

COMMIT;
