const app = document.querySelector("#app");
const params = new URLSearchParams(location.search);

function element(tag, text, parent = app) {
    const node = document.createElement(tag);
    if (text !== null) node.textContent = text;
    parent.append(node);
    return node;
}

function link(text, href, parent) {
    const anchor = element("a", text, parent);
    anchor.href = href;
    return anchor;
}

async function api(path, method = "GET", input) {
    const response = await fetch("/api/" + path, input ? {
        method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(input)
    } : {});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    return data;
}

let options;

async function pickUser(parent, allowed = () => true) {
    options ??= await api("options");
    const label = element("label", "Навчальний профіль", parent);
    const select = element("select", null, label);
    for (const user of options.users.filter(allowed)) {
        const choice = element("option", user.name + " (" + user.role + ")", select);
        choice.value = user._id;
    }
    select.value = localStorage.getItem("lab7-user") ?? select.value;
    if (!select.value) select.selectedIndex = 0;
    select.addEventListener("change", () => localStorage.setItem("lab7-user", select.value));
    return select;
}

async function editor(post) {
    element("h1", post ? "Редагувати допис" : "Новий допис");
    const form = element("form", null);
    form.className = "editor";
    const user = await pickUser(form, u => u.role === "admin" || (u.role === "author" && (!post || u._id === post.authorId)));
    const fields = {};
    for (const [key, caption] of [["title", "Назва"], ["body", "Текст"], ["tags", "Теги через кому"], ["longitude", "Довгота (необов’язково)"], ["latitude", "Широта (необов’язково)"]]) {
        const label = element("label", caption, form);
        const input = element(key === "body" ? "textarea" : "input", null, label);
        input.value = key === "tags" ? post?.tags.join(", ") ?? "" : post?.[key] ?? "";
        input.required = key === "title" || key === "body";
        if (key === "longitude" || key === "latitude") {
            input.type = "number";
            input.step = "any";
            input.value = post?.location?.coordinates[key === "longitude" ? 0 : 1] ?? "";
        }
        fields[key] = input;
    }
    const category = element("select", null, element("label", "Категорія", form));
    for (const item of options.categories) {
        const choice = element("option", item.name, category);
        choice.value = item._id;
    }
    if (post) category.value = post.categoryId;
    element("button", "Зберегти", form);
    const feedback = element("p", "");
    form.addEventListener("submit", async event => {
        event.preventDefault();
        try {
            const result = await api(post ? "posts/" + post._id : "posts", post ? "PATCH" : "POST", {
                title: fields.title.value, body: fields.body.value, tags: fields.tags.value,
                longitude: fields.longitude.value === "" ? null : Number(fields.longitude.value),
                latitude: fields.latitude.value === "" ? null : Number(fields.latitude.value),
                categoryId: Number(category.value), userId: Number(user.value)
            });
            location.href = "/?post=" + result._id;
        } catch (error) { feedback.textContent = error.message; }
    });
}

function renderComments(comments, parent, reply) {
    const list = element("ul", null, parent);
    for (const comment of comments) {
        const item = element("li", comment.body, list);
        const button = element("button", "Відповісти", item);
        button.addEventListener("click", () => reply(comment));
        if (comment.replies.length) renderComments(comment.replies, item, reply);
    }
}

async function listPosts() {
    element("h1", "Дописи");
    link("Новий допис", "/?view=new", app);
    const form = element("form", null);
    for (const [name, title] of [["q", "Пошук у назві й тексті"], ["tag", "Теги через кому"]]) {
        const label = element("label", title, form);
        const input = element("input", null, label);
        input.name = name;
        input.value = params.get(name) ?? "";
    }
    element("button", "Знайти", form);

    const { items, page, total } = await api("posts?" + params);
    element("p", "Знайдено дописів: " + total);
    for (const post of items) {
        const card = element("article", null);
        link(post.title, "/?post=" + post._id, element("h2", null, card));
        element("small", [post.author, post.category, ...post.tags].join(" · "), card);
    }

    const nav = element("nav", null);
    const pageLink = (label, number) => {
        const query = new URLSearchParams(params);
        query.set("page", number);
        link(label, "/?" + query, nav);
    };
    if (page > 1) pageLink("Назад", page - 1);
    element("span", "Сторінка " + page, nav);
    if (page * 10 < total) pageLink("Далі", page + 1);
}

async function showPost(id) {
    const post = await api("posts/" + encodeURIComponent(id));
    if (params.get("view") === "edit") return editor(post);
    const card = element("article", null);
    element("h1", post.title, card);
    element("small", [post.author, post.category, "Переглядів: " + post.views].join(" · "), card);
    element("p", post.body, card);
    link("Редагувати", "/?view=edit&post=" + id, card);
    const details = element("details", null, card);
    element("summary", "Версія " + post.version + " · Історія змін", details);
    for (const previous of post.history) {
        element("p", "Версія " + previous.version + " · " + previous.title, details);
        element("p", previous.body, details);
    }

    const user = await pickUser(card);
    const feedback = element("p", "", card);
    const action = async (name, data) => api("posts/" + id + "/" + name, "POST", {
        ...data, userId: Number(user.value)
    });
    for (const [label, value, count] of [["Подобається", 1, post.likes], ["Не подобається", -1, post.dislikes]]) {
        const button = element("button", label + " · " + count, card);
        button.addEventListener("click", async () => {
            try { await action("vote", { value }); location.reload(); }
            catch (error) { feedback.textContent = error.message; }
        });
    }
    element("h2", "Коментарі", card);
    const thread = element("section", null, card);
    const form = element("form", null, card);
    const commentLabel = element("label", null, form);
    const caption = element("span", "Новий коментар", commentLabel);
    const input = element("textarea", null, commentLabel);
    let parentId = null;
    renderComments(post.comments, thread, comment => {
        parentId = comment.id;
        caption.textContent = "Відповідь на коментар №" + parentId;
        input.focus();
    });
    input.required = true;
    element("button", "Надіслати", form);
    form.addEventListener("submit", async event => {
        event.preventDefault();
        try {
            await action("comments", { body: input.value, parentId });
            input.value = "";
            parentId = null;
            caption.textContent = "Новий коментар";
            feedback.textContent = "Коментар очікує перевірки.";
            await refreshReview();
        } catch (error) { feedback.textContent = error.message; }
    });

    const moderation = element("section", null, card);
    async function refreshReview() {
        moderation.replaceChildren();
        if (options.users.find(item => item._id === Number(user.value))?.role !== "admin") return;
        element("h2", "Модерація", moderation);
        const pending = await api("posts/" + id + "/review?userId=" + user.value);
        if (!pending.length) element("p", "Немає коментарів на перевірці.", moderation);
        for (const comment of pending) {
            element("p", comment.body, moderation);
            for (const [label, status] of [["Схвалити", "approved"], ["Відхилити", "rejected"]]) {
                const button = element("button", label, moderation);
                button.addEventListener("click", async () => {
                    try { await action("moderate", { commentId: comment.id, status }); location.reload(); }
                    catch (error) { feedback.textContent = error.message; }
                });
            }
        }
    }
    user.addEventListener("change", () => refreshReview().catch(error => { feedback.textContent = error.message; }));
    await refreshReview();
}

async function showNotifications() {
    element("h1", "Сповіщення автора");
    const user = await pickUser(app, account => account.role !== "reader");
    const list = element("section", null);
    async function refresh() {
        const items = await api("notifications?userId=" + user.value);
        list.replaceChildren();
        if (!items.length) element("p", "Сповіщень немає.", list);
        for (const item of items) {
            const card = element("article", null, list);
            link(item.title, "/?post=" + item.postId, card);
            element("p", item.body, card);
            element("small", new Date(item.createdAt).toLocaleString("uk-UA"), card);
        }
    }
    user.addEventListener("change", () => refresh().catch(error => { list.textContent = error.message; }));
    await refresh();
}

async function nearby() {
    element("h1", "Дописи в радіусі 20 км");
    const form = element("form", null);
    const latitude = element("input", null, element("label", "Широта", form));
    const longitude = element("input", null, element("label", "Довгота", form));
    for (const input of [latitude, longitude]) {
        input.type = "number";
        input.step = "any";
        input.required = true;
    }
    element("button", "Знайти", form);
    const list = element("section", null);
    form.addEventListener("submit", async event => {
        event.preventDefault();
        list.replaceChildren();
        try {
            const items = await api("nearby?" + new URLSearchParams({ lon: longitude.value, lat: latitude.value }));
            if (!items.length) element("p", "Поблизу немає дописів.", list);
            for (const item of items) {
                const card = element("article", null, list);
                link(item.title, "/?post=" + item._id, card);
                element("p", Math.round(item.distance) + " м", card);
            }
        } catch (error) { list.textContent = error.message; }
    });
}

async function showStatistics() {
    const stats = await api("statistics");
    const summary = stats.activity[0];
    element("h1", "Статистика блогу");
    if (summary) {
        element("p", `Дописів: ${summary.posts} · Коментарів: ${summary.comments} · У середньому на допис: ${summary.averagePerPost} · Переглядів: ${summary.views}`);
    }

    for (const [heading, rows] of [["Десять авторів за кількістю дописів", stats.authors], ["Популярні категорії", stats.categories]]) {
        const section = element("article", null);
        element("h2", heading, section);
        const list = element("ul", null, section);
        list.className = "chart";
        const maximum = Math.max(1, ...rows.map(row => row.posts));
        for (const row of rows) {
            const item = element("li", null, list);
            element("span", row.name, item);
            const bar = element("meter", null, item);
            bar.max = maximum;
            bar.value = row.posts;
            bar.setAttribute("aria-label", row.name);
            element("span", row.posts, item);
        }
    }
}

try {
    if (params.has("post")) await showPost(params.get("post"));
    else if (params.get("view") === "new") await editor();
    else if (params.get("view") === "notifications") await showNotifications();
    else if (params.get("view") === "nearby") await nearby();
    else if (params.get("view") === "stats") await showStatistics();
    else await listPosts();
} catch (error) {
    element("p", error.message);
}
