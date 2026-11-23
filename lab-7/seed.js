const lab7 = db.getSiblingDB("blog_lab7");

if (lab7.getCollectionNames().length) {
    throw new Error("blog_lab7 вже містить колекції");
}

const string = { bsonType: "string", minLength: 1 };
const id = { bsonType: "int", minimum: 1 };
const count = { bsonType: "int", minimum: 0 };
const date = { bsonType: "date" };
const strings = { bsonType: "array", items: string };

function schema(required, properties) {
    return { bsonType: "object", required, properties };
}

function create(name, definition) {
    lab7.createCollection(name, { validator: { $jsonSchema: definition } });
}

create("users", schema(["name", "role"], {
    _id: id,
    name: string,
    role: { enum: ["author", "reader", "admin"] }
}));

create("categories", schema(["name", "tags"], {
    _id: id, name: string, tags: strings
}));

const comment = schema(["id", "userId", "body", "status", "createdAt", "replies"], {
    id,
    userId: id,
    body: string,
    status: { enum: ["pending", "approved", "rejected"] },
    createdAt: date,
    replies: { bsonType: "array", items: { bsonType: "object" } }
});

create("posts", schema(
    ["title", "body", "authorId", "categoryId", "tags", "createdAt",
        "views", "comments", "votes", "version", "history"],
    {
        title: string,
        body: string,
        authorId: id,
        categoryId: id,
        tags: strings,
        createdAt: date,
        views: count,
        comments: { bsonType: "array", items: comment },
        votes: { bsonType: "array", items: { bsonType: "object" } },
        version: id,
        history: { bsonType: "array", items: { bsonType: "object" } }
    }
));

const topics = [
    ["Технології", "код", ["Перший REST API", "Як працює кеш", "Пошук у MongoDB", "Огляд Git", "Перевірка JSON"]],
    ["Подорожі", "маршрут", ["Вихідні у Львові", "Стежки Карпат", "День у Луцьку", "Поїздка до Чернівців", "Дорога до Шацьких озер"]],
    ["Освіта", "навчання", ["Конспект лекції", "Підготовка до іспиту", "Робота в команді", "План на семестр", "Як читати документацію"]],
    ["Книги", "читання", ["З чого почати читати Франка", "Повернення до Кобзаря", "Роман на вихідні", "Книжковий клуб", "Поезія для читання вголос"]],
    ["Культура", "події", ["Вечір у театрі", "Музей міста", "Виставка фотографій", "Концерт у парку", "День українського кіно"]],
    ["Кухня", "рецепти", ["Домашній борщ", "Хліб на заквасці", "Сніданок із сирниками", "Печені овочі", "Гарбузовий суп"]],
    ["Спорт", "рух", ["Ранкова пробіжка", "Перший веломаршрут", "Вправи для спини", "Підготовка до походу", "Тренування у дворі"]],
    ["Природа", "довкілля", ["Птахи біля озера", "Дерева міського парку", "Весняні квіти", "Сортування відходів", "Дощовий сад"]],
    ["Місто", "громада", ["Нова велодоріжка", "Бібліотека району", "Суботній ярмарок", "Доступний транспорт", "Громадський простір"]],
    ["Дозвілля", "хобі", ["Плівкова фотографія", "Настільні ігри", "Перший малюнок", "Ремонт старого велосипеда", "Вечір без телефона"]]
];
const names = [
    "Олена", "Андрій", "Ірина", "Максим", "Софія", "Дмитро", "Анна",
    "Богдан", "Марія", "Назар", "Вікторія", "Роман", "Катерина", "Іван",
    "Оксана", "Тарас", "Юлія", "Олег", "Наталія", "Петро"
];
const comments = [
    "Дякую за допис, збережу його на потім.",
    "Цікаво було б прочитати продовження.",
    "Я теж мав схожий досвід.",
    "Що порадите тому, хто тільки починає?"
];

lab7.users.insertMany(names.map((name, i) => ({
    _id: NumberInt(i + 1),
    name,
    role: i < 10 ? "author" : i < 19 ? "reader" : "admin"
})));

lab7.categories.insertMany(topics.map(([name, tag], i) => ({
    _id: NumberInt(i + 1), name, tags: [tag, "поради"]
})));

lab7.posts.insertMany(topics.flatMap(([category, tag, titles], g) =>
    titles.map((title, j) => {
        const n = g * 5 + j;
        const createdAt = new Date(Date.UTC(2026, 9, n + 1));

        return {
            _id: new ObjectId(),
            title,
            body: `Тема допису «${title}» належить до розділу «${category}». Почнімо з простого прикладу: сплануємо перший крок, перевіримо результат і запишемо, що можна поліпшити.`,
            authorId: NumberInt((g + j * j) % 10 + 1),
            categoryId: NumberInt(g + 1),
            tags: [tag, "поради"],
            createdAt,
            views: NumberInt(n * 3),
            votes: [],
            version: NumberInt(1),
            history: [],
            comments: comments.map((body, k) => ({
                id: NumberInt(k + 1),
                userId: NumberInt(11 + (n + k) % 9),
                body,
                status: k < 3 ? "approved" : "pending",
                createdAt: new Date(createdAt.getTime() + (k + 1) * 3600000),
                replies: []
            }))
        };
    })
));

lab7.posts.createIndex({ authorId: 1, createdAt: -1 });
lab7.posts.createIndex({ categoryId: 1, createdAt: -1 });
lab7.posts.createIndex({ createdAt: -1, _id: -1 });
lab7.posts.createIndex({ tags: 1 });
lab7.posts.createIndex({ title: "text", body: "text" }, { default_language: "none" });
lab7.posts.createIndex({ location: "2dsphere" });

printjson({
    database: lab7.getName(),
    posts: lab7.posts.countDocuments(),
    comments: lab7.posts.aggregate([
        { $group: { _id: null, total: { $sum: { $size: "$comments" } } } }
    ]).toArray()[0].total,
    users: lab7.users.countDocuments(),
    categories: lab7.categories.countDocuments()
});
