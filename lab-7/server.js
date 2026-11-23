import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { Int32, MongoClient, ObjectId } from "mongodb";

const client = new MongoClient(process.env.MONGO_URI ?? "mongodb://127.0.0.1:27017", {
    serverSelectionTimeoutMS: 5000
});
await client.connect();
const db = client.db(process.env.MONGO_DB ?? "blog_lab7");
const posts = db.collection("posts");
const port = Number(process.env.PORT ?? 8070);
const listCache = new Map();
let cacheRevision = 0;

function invalidateList() {
    cacheRevision++;
    listCache.clear();
}

function point(longitude, latitude) {
    if (!Number.isFinite(longitude) || !Number.isFinite(latitude) ||
        Math.abs(longitude) > 180 || Math.abs(latitude) > 90) return null;
    return { type: "Point", coordinates: [longitude, latitude] };
}

function flatten(comments, depth = 0) {
    return comments.flatMap(comment => [
        { ...comment, depth },
        ...flatten(comment.replies ?? [], depth + 1)
    ]);
}

function countTree(input, remaining = 7) {
    if (!remaining) return { $size: input };
    return {
        $reduce: {
            input,
            initialValue: 0,
            in: { $add: ["$$value", 1, countTree({ $ifNull: ["$$this.replies", []] }, remaining - 1)] }
        }
    };
}

async function bodyOf(request) {
    let data = "";
    for await (const chunk of request.setEncoding("utf8")) {
        data += chunk;
        if (data.length > 64000) throw new Error("Запит завеликий.");
    }
    const value = JSON.parse(data);
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        throw new Error("Очікується JSON-об’єкт.");
    }
    return value;
}

async function write(request, response, path) {
    const match = /^\/api\/posts\/([a-f\d]{24})(?:\/(vote|comments|moderate))?$/i.exec(path);
    if (!(path === "/api/posts" && request.method === "POST") &&
        !(match && request.method === (match[2] ? "POST" : "PATCH"))) {
        return json(response, 404, { error: "Маршрут не знайдено." });
    }

    let data;
    try { data = await bodyOf(request); }
    catch { return json(response, 400, { error: "Некоректні дані запиту." }); }

    const user = Number.isInteger(data.userId) && await db.collection("users").findOne({ _id: data.userId });
    if (!user) return json(response, 400, { error: "Виберіть користувача." });
    const _id = match ? new ObjectId(match[1]) : null;
    const action = match?.[2];

    if (!action) {
        if (user.role === "reader") return json(response, 403, { error: "Потрібна роль автора." });
        if (typeof data.title !== "string" || typeof data.body !== "string" ||
            !data.title.trim() || !data.body.trim() || data.title.length > 160 ||
            data.body.length > 12000 || !Number.isInteger(data.categoryId) ||
            !(await db.collection("categories").findOne({ _id: data.categoryId }))) {
            return json(response, 400, { error: "Перевірте назву, текст і категорію." });
        }
        const fields = {
            title: data.title.trim(), body: data.body.trim(),
            categoryId: new Int32(data.categoryId),
            tags: [...new Set(String(data.tags ?? "").split(",").map(tag => tag.trim()).filter(Boolean))].slice(0, 10)
        };
        if (data.longitude != null || data.latitude != null) {
            const location = point(data.longitude, data.latitude);
            if (!location) return json(response, 400, { error: "Некоректні координати." });
            fields.location = location;
        }
        if (!_id) {
            const result = await posts.insertOne({
                ...fields, authorId: new Int32(user._id), views: new Int32(0),
                version: new Int32(1), createdAt: new Date(), votes: [], comments: [], history: []
            });
            invalidateList();
            return json(response, 201, { _id: result.insertedId });
        }
        const filter = { _id, ...(user.role === "admin" ? {} : { authorId: user._id }) };
        const result = await posts.updateOne(filter, [{
            $set: {
                ...Object.fromEntries(Object.entries(fields).map(([key, value]) => [key, { $literal: value }])),
                history: { $concatArrays: ["$history", [{
                    version: "$version", title: "$title", body: "$body",
                    categoryId: "$categoryId", tags: "$tags",
                    location: { $ifNull: ["$location", null] }, savedAt: "$$NOW"
                }]] },
                version: { $add: ["$version", 1] }
            }
        }]);
        if (result.matchedCount) invalidateList();
        return result.matchedCount ? json(response, 200, { _id }) :
            json(response, 404, { error: "Допис недоступний для редагування." });
    }

    if (action === "vote") {
        if (![1, -1].includes(data.value)) return json(response, 400, { error: "Некоректний голос." });
        const result = await posts.updateOne({ _id }, [{
            $set: {
                votes: { $concatArrays: [
                    { $filter: { input: "$votes", cond: { $ne: ["$$this.userId", user._id] } } },
                    [{ userId: user._id, value: data.value }]
                ] }
            }
        }]);
        return result.matchedCount ? json(response, 200, { ok: true }) :
            json(response, 404, { error: "Допис не знайдено." });
    }

    if (action === "comments") {
        if (typeof data.body !== "string" || !data.body.trim() || data.body.length > 2000) {
            return json(response, 400, { error: "Введіть текст коментаря до 2000 символів." });
        }
        const comment = {
            userId: new Int32(user._id), body: data.body.trim(), status: "pending",
            createdAt: new Date(), replies: []
        };
        const post = await posts.findOne({ _id }, { projection: { comments: 1 } });
        if (!post) return json(response, 404, { error: "Допис не знайдено." });
        const existing = flatten(post.comments);
        const updated = structuredClone(post.comments);
        let target = updated;
        if (data.parentId != null) {
            const parent = existing.find(item => item.id === data.parentId && item.status === "approved");
            if (!parent || parent.depth >= 7) {
                return json(response, 400, { error: "Відповідь на цей коментар недоступна." });
            }
            function find(items) {
                for (const item of items) {
                    if (item.id === data.parentId) return item;
                    const nested = find(item.replies);
                    if (nested) return nested;
                }
            }
            target = find(updated).replies;
        }
        target.push({ ...comment, id: new Int32(Math.max(0, ...existing.map(item => item.id)) + 1) });
        // Порівнюємо попередній стан, щоб не затерти паралельний коментар чи модерацію.
        const result = await posts.updateOne({ _id, comments: post.comments }, { $set: { comments: updated } });
        return result.matchedCount ? json(response, 201, { status: "pending" }) :
            json(response, 409, { error: "Коментарі змінилися. Повторіть дію." });
    }

    if (user.role !== "admin") return json(response, 403, { error: "Потрібна роль адміністратора." });
    if (!Number.isInteger(data.commentId) || !["approved", "rejected"].includes(data.status)) {
        return json(response, 400, { error: "Некоректний стан модерації." });
    }
    const post = await posts.findOne({ _id }, { projection: { comments: 1 } });
    const updated = structuredClone(post?.comments ?? []);
    function moderate(items) {
        for (const item of items) {
            if (item.id === data.commentId && item.status === "pending") {
                item.status = data.status;
                return true;
            }
            if (moderate(item.replies)) return true;
        }
        return false;
    }
    if (!moderate(updated)) return json(response, 404, { error: "Коментар не знайдено." });
    const result = await posts.updateOne({ _id, comments: post.comments }, { $set: { comments: updated } });
    return result.matchedCount ? json(response, 200, { ok: true }) :
        json(response, 409, { error: "Коментарі змінилися. Повторіть дію." });
}

const labels = [
    { $lookup: { from: "users", localField: "authorId", foreignField: "_id", as: "author" } },
    { $lookup: { from: "categories", localField: "categoryId", foreignField: "_id", as: "category" } },
    {
        $set: {
            author: { $first: "$author.name" },
            category: { $first: "$category.name" }
        }
    }
];

function json(response, status, value) {
    response.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
    response.end(JSON.stringify(value));
}

const assets = new Map([
    ["/", ["index.html", "text/html"]],
    ["/app.js", ["app.js", "text/javascript"]],
    ["/style.css", ["style.css", "text/css"]]
]);

const server = createServer(async (request, response) => {
    try {
        const url = new URL(request.url, "http://localhost");
        if (request.method !== "GET") return await write(request, response, url.pathname);

        if (url.pathname === "/api/options") {
            return json(response, 200, {
                users: await db.collection("users").find().sort({ _id: 1 }).toArray(),
                categories: await db.collection("categories").find().sort({ _id: 1 }).toArray()
            });
        }

        const review = /^\/api\/posts\/([a-f\d]{24})\/review$/i.exec(url.pathname);
        if (review) {
            const user = await db.collection("users").findOne({ _id: Number(url.searchParams.get("userId")) });
            if (user?.role !== "admin") return json(response, 403, { error: "Потрібна роль адміністратора." });
            const post = await posts.findOne({ _id: new ObjectId(review[1]) }, { projection: { comments: 1 } });
            return post ? json(response, 200, flatten(post.comments).filter(item => item.status === "pending")) :
                json(response, 404, { error: "Допис не знайдено." });
        }
        if (assets.has(url.pathname)) {
            const [file, type] = assets.get(url.pathname);
            const content = await readFile(new URL("./public/" + file, import.meta.url));
            response.writeHead(200, { "Content-Type": type + "; charset=utf-8" });
            return response.end(content);
        }

        if (url.pathname === "/api/posts") {
            const page = Number(url.searchParams.get("page") ?? 1);
            if (!Number.isSafeInteger(page) || page < 1 || page > 10000) {
                return json(response, 400, { error: "Некоректний номер сторінки." });
            }

            const search = (url.searchParams.get("q") ?? "").trim().slice(0, 200);
            const tags = url.searchParams.getAll("tag")
                .flatMap(value => value.split(",")).map(value => value.trim()).filter(Boolean);
            const match = {};
            if (search) match.$text = { $search: search };
            if (tags.length) match.tags = { $all: tags.slice(0, 10) };
            const key = JSON.stringify([page, search, match.tags?.$all ?? []]);
            const cached = listCache.get(key);
            if (cached && cached.expires > Date.now()) {
                response.setHeader("X-Cache", "HIT");
                return json(response, 200, cached.value);
            }
            const revision = cacheRevision;

            const [result] = await posts.aggregate([
                { $match: match },
                { $sort: { createdAt: -1, _id: -1 } },
                {
                    $facet: {
                        items: [
                            { $skip: (page - 1) * 10 },
                            { $limit: 10 },
                            ...labels,
                            { $project: { title: 1, tags: 1, author: 1, category: 1, createdAt: 1 } }
                        ],
                        count: [{ $count: "total" }]
                    }
                }
            ]).toArray();
            const value = { items: result.items, total: result.count[0]?.total ?? 0, page };
            if (revision === cacheRevision) {
                if (listCache.size >= 100) listCache.delete(listCache.keys().next().value);
                listCache.set(key, { value, expires: Date.now() + 30000 });
            }
            response.setHeader("X-Cache", "MISS");
            return json(response, 200, value);
        }

        if (url.pathname === "/api/nearby") {
            const coordinates = ["lon", "lat"].map(name => url.searchParams.get(name));
            const location = coordinates.some(value => !value?.trim()) ? null : point(...coordinates.map(Number));
            if (!location) return json(response, 400, { error: "Введіть довготу й широту." });
            const result = await posts.aggregate([
                { $geoNear: { near: location, key: "location", distanceField: "distance", maxDistance: 20000, spherical: true } },
                { $limit: 20 },
                { $project: { title: 1, distance: 1 } }
            ]).toArray();
            return json(response, 200, result);
        }

        if (url.pathname === "/api/notifications") {
            const userId = Number(url.searchParams.get("userId"));
            if (!Number.isInteger(userId) || userId < 1) return json(response, 400, { error: "Виберіть профіль." });
            const authored = await posts.find({ authorId: userId }, { projection: { title: 1, comments: 1 } }).toArray();
            const notifications = authored.flatMap(post => flatten(post.comments)
                .filter(comment => comment.userId !== userId && comment.status !== "rejected")
                .map(comment => ({ postId: post._id, title: post.title, body: comment.body, createdAt: comment.createdAt })));
            notifications.sort((a, b) => b.createdAt - a.createdAt);
            return json(response, 200, notifications.slice(0, 20));
        }

        const detail = /^\/api\/posts\/([a-f\d]{24})$/i.exec(url.pathname);
        if (detail) {
            const _id = new ObjectId(detail[1]);
            const updated = await posts.updateOne({ _id }, { $inc: { views: 1 } });
            if (!updated.matchedCount) return json(response, 404, { error: "Допис не знайдено." });
            const [post] = await posts.aggregate([
                { $match: { _id } }, ...labels,
            ]).toArray();

            function visible(comments) {
                return comments.filter(comment => comment.status === "approved").map(comment => ({
                    ...comment,
                    replies: visible(comment.replies ?? [])
                }));
            }

            const { votes, ...details } = post;
            return json(response, 200, {
                ...details, comments: visible(post.comments),
                likes: votes.filter(vote => vote.value === 1).length,
                dislikes: votes.filter(vote => vote.value === -1).length
            });
        }

        if (url.pathname === "/api/statistics") {
            const group = field => [
                { $group: { _id: "$" + field, posts: { $sum: 1 } } },
                { $sort: { posts: -1, _id: 1 } }, { $limit: 10 },
                { $lookup: {
                    from: field === "authorId" ? "users" : "categories",
                    localField: "_id", foreignField: "_id", as: "label"
                } },
                { $project: { _id: 0, name: { $first: "$label.name" }, posts: 1 } }
            ];
            const [stats] = await posts.aggregate([{
                $facet: {
                    authors: group("authorId"),
                    categories: group("categoryId"),
                    activity: [{
                        $group: {
                            _id: null, posts: { $sum: 1 }, views: { $sum: "$views" },
                            comments: { $sum: countTree("$comments") },
                            averagePerPost: { $avg: countTree("$comments") }
                        }
                    }]
                }
            }]).toArray();
            return json(response, 200, stats);
        }

        return json(response, 404, { error: "Сторінку не знайдено." });
    } catch (error) {
        console.error(error);
        return json(response, 500, { error: "Не вдалося виконати запит." });
    }
});

server.listen(port, "127.0.0.1", () => console.log("Блог доступний на http://127.0.0.1:" + port));
