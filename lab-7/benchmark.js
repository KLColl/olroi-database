import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { performance } from "node:perf_hooks";
import { fileURLToPath } from "node:url";
import { MongoClient } from "mongodb";
import pg from "pg";

const lab4Env = fileURLToPath(new URL("../lab-4/.env", import.meta.url));
if (existsSync(lab4Env)) process.loadEnvFile(lab4Env);

const mongo = new MongoClient(process.env.MONGO_URI ?? "mongodb://127.0.0.1:27017", {
    serverSelectionTimeoutMS: 5000
});
const sql = new pg.Client({
    host: process.env.PGHOST ?? process.env.DB_HOST ?? "localhost",
    port: Number(process.env.PGPORT ?? process.env.DB_PORT ?? 5432),
    user: process.env.PGUSER ?? process.env.DB_USER ?? "postgres",
    password: process.env.PGPASSWORD ?? process.env.DB_PASSWORD,
    database: process.env.PGDATABASE ?? "postgres",
    connectionTimeoutMillis: 5000
});

async function insert(name, columns, rows) {
    if (!rows.length) return;
    const values = rows.flat();
    const placeholders = rows.map((row, i) =>
        "(" + row.map((_, j) => "$" + (i * columns.length + j + 1)).join(", ") + ")"
    );
    await sql.query(
        "INSERT INTO " + name + " (" + columns.join(", ") + ") VALUES " + placeholders.join(", "),
        values
    );
}

function commentRows(postId, comments, parentId = null) {
    return comments.flatMap(comment => [
        [postId, comment.id, parentId, comment.userId, comment.body, comment.status, comment.createdAt],
        ...commentRows(postId, comment.replies ?? [], comment.id)
    ]);
}

async function compare(label, mongoQuery, postgresQuery) {
    const expected = await postgresQuery();
    assert.deepEqual(await mongoQuery(), expected);
    const samples = [[], []];
    const queries = [mongoQuery, postgresQuery];
    for (let run = 0; run < 25; run++) {
        for (const n of run % 2 ? [1, 0] : [0, 1]) {
            const start = performance.now();
            await queries[n]();
            samples[n].push(performance.now() - start);
        }
    }
    return {
        query: label,
        rows: expected.length,
        MongoDB_ms: Number(samples[0].sort((a, b) => a - b)[12].toFixed(3)),
        PostgreSQL_ms: Number(samples[1].sort((a, b) => a - b)[12].toFixed(3))
    };
}

try {
    await mongo.connect();
    await sql.connect();
    const db = mongo.db(process.env.MONGO_DB ?? "blog_lab7");
    const [users, categories, posts] = await Promise.all(
        ["users", "categories", "posts"].map(name => db.collection(name).find().toArray())
    );
    const comments = posts.flatMap(post => commentRows(post._id.toHexString(), post.comments));
    await sql.query(await readFile(new URL("./benchmark.sql", import.meta.url), "utf8"));
    await insert("authors", ["id", "name", "role"], users.map(u => [u._id, u.name, u.role]));
    await insert("categories", ["id", "name", "tags"], categories.map(c => [c._id, c.name, c.tags]));
    await insert("posts", ["id", "author_id", "category_id", "title", "body", "created_at", "tags", "views"],
        posts.map(p => [p._id.toHexString(), p.authorId, p.categoryId, p.title, p.body, p.createdAt, p.tags, p.views]));
    // Батьківський коментар іде перед відповідями в тому самому INSERT.
    await insert("comments", ["post_id", "id", "parent_id", "user_id", "body", "status", "created_at"], comments);
    await sql.query("ANALYZE authors; ANALYZE categories; ANALYZE posts; ANALYZE comments;");
    console.log({ posts: posts.length, comments: comments.length, users: users.length, categories: categories.length });
    const author = 1;
    const collection = db.collection("posts");
    const results = [
        await compare("Дописи автора", async () => (await collection
            .find({ authorId: author }, { projection: { _id: 1, title: 1 } })
            .sort({ createdAt: -1, _id: -1 }).limit(10).toArray())
            .map(p => ({ id: p._id.toHexString(), title: p.title })),
        async () => (await sql.query(`
            SELECT id, title FROM posts WHERE author_id = $1
            ORDER BY created_at DESC, id DESC LIMIT 10
        `, [author])).rows),
        await compare("Кількість за категоріями", () => collection.aggregate([
            { $group: { _id: "$categoryId", count: { $sum: 1 } } },
            { $sort: { _id: 1 } }, { $project: { _id: 0, id: "$_id", count: 1 } }
        ]).toArray(),
        async () => (await sql.query(`
            SELECT category_id AS id, COUNT(*)::integer AS count
            FROM posts GROUP BY category_id ORDER BY category_id
        `)).rows)
    ];
    console.log("Результати запитів збігаються. Медіана з 25 запусків:");
    console.table(results);
} finally {
    await Promise.allSettled([mongo.close(), sql.end()]);
}
