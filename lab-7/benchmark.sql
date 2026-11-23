CREATE TEMP TABLE authors (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL
);
CREATE TEMP TABLE categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    tags TEXT[] NOT NULL
);
CREATE TEMP TABLE posts (
    id TEXT PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES authors(id),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    tags TEXT[] NOT NULL,
    views INTEGER NOT NULL
);
CREATE TEMP TABLE comments (
    post_id TEXT NOT NULL REFERENCES posts(id),
    id INTEGER NOT NULL,
    parent_id INTEGER,
    user_id INTEGER NOT NULL REFERENCES authors(id),
    body TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (post_id, id),
    FOREIGN KEY (post_id, parent_id) REFERENCES comments(post_id, id)
);
CREATE INDEX ON posts (author_id, created_at DESC, id DESC);
CREATE INDEX ON posts (category_id, created_at DESC);
CREATE INDEX ON posts (created_at DESC, id DESC);
