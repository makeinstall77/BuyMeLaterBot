const STYLE = `
:host { display: block; }
.bml {
  font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
  color: var(--primary-text-color);
  padding: 16px;
}
.bml h1 { font-size: 1.4rem; margin: 0 0 12px; }
.tabs, .filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
button, .chip {
  background: var(--secondary-background-color);
  color: var(--primary-text-color);
  border: 1px solid var(--divider-color);
  border-radius: 20px;
  padding: 6px 14px;
  cursor: pointer;
}
button.active, .chip.active {
  background: var(--primary-color);
  color: var(--text-primary-color, #fff);
  border-color: transparent;
}
.list-block { margin-bottom: 20px; }
.list-block h2 { font-size: 1.05rem; margin: 0 0 8px; }
.item {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 8px 0; border-bottom: 1px solid var(--divider-color);
}
.item input[type=checkbox] { margin-top: 4px; }
.meta { font-size: 0.85rem; opacity: 0.8; margin-top: 2px; }
.add-row { display: flex; gap: 8px; margin-top: 8px; }
.add-row input[type=text] {
  flex: 1; padding: 8px 10px;
  border: 1px solid var(--divider-color);
  border-radius: 8px;
  background: var(--card-background-color);
  color: var(--primary-text-color);
}
.item-actions { margin-left: auto; display: flex; gap: 4px; }
.item-actions button { padding: 4px 8px; border-radius: 8px; }
.empty { opacity: 0.7; padding: 8px 0; }
`;

function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDue(iso) {
  if (!iso) return "без даты";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

class BuyMeLaterPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._listType = "shopping";
    this._scopeFilter = "all";
    this._lists = [];
    this._userId = null;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._subscribe();
      this._load();
    }
  }

  connectedCallback() {
    if (!this._hass) {
      const ha = document.querySelector("home-assistant");
      if (ha?.hass) this.hass = ha.hass;
    }
  }

  disconnectedCallback() {
    if (this._unsub) this._unsub();
  }

  _subscribe() {
    if (!this._hass) return;
    this._unsub = this._hass.connection.subscribeEvents(() => this._load(), "buymelater_event");
  }

  async _load() {
    if (!this._hass) return;
    try {
      const result = await this._hass.connection.sendMessagePromise({ type: "buymelater/overview" });
      this._lists = result.lists || [];
      this._userId = result.user_id;
      this._render();
    } catch (err) {
      this._lists = [];
      this._render(err.message || String(err));
    }
  }

  _filteredLists() {
    return this._lists.filter((lst) => {
      if (lst.list_type !== this._listType) return false;
      if (this._scopeFilter === "group") return lst.scope_type === "group";
      if (this._scopeFilter === "personal") {
        return lst.scope_type === "personal" && lst.ha_user_id === this._userId;
      }
      return true;
    });
  }

  async _send(msg) {
    await this._hass.connection.sendMessagePromise(msg);
    await this._load();
  }

  async _toggle(item) {
    const status = item.status === "completed" ? "active" : "completed";
    await this._send({ type: "buymelater/update_item", item_id: item.id, status });
  }

  async _notify(item) {
    await this._send({
      type: "buymelater/update_item",
      item_id: item.id,
      notifications_enabled: !item.notifications_enabled,
    });
  }

  async _delete(item) {
    if (!confirm(`Удалить «${item.title}»?`)) return;
    await this._send({ type: "buymelater/delete_item", item_id: item.id });
  }

  async _add(listId, form) {
    const title = form.querySelector("input[name=title]").value.trim();
    if (!title) return;
    const due = form.querySelector("input[name=due]").value;
    await this._send({
      type: "buymelater/create_item",
      list_id: listId,
      title,
      due_at: due ? new Date(due).toISOString() : null,
    });
    form.reset();
  }

  _render(error) {
    const lists = this._filteredLists();
    const blocks = lists.length
      ? lists.map((lst) => this._listHtml(lst)).join("")
      : `<p class="empty">Нет списков. Привяжите Telegram (/link) или добавьте бота в группу.</p>`;

    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <div class="bml">
        <h1>BuyMeLater</h1>
        <div class="tabs">
          <button class="${this._listType === "shopping" ? "active" : ""}" data-type="shopping">🛒 Покупки</button>
          <button class="${this._listType === "tasks" ? "active" : ""}" data-type="tasks">📋 Дела</button>
        </div>
        <div class="filters">
          <button class="${this._scopeFilter === "all" ? "active" : ""}" data-scope="all">Все</button>
          <button class="${this._scopeFilter === "group" ? "active" : ""}" data-scope="group">Групповые</button>
          <button class="${this._scopeFilter === "personal" ? "active" : ""}" data-scope="personal">Мои</button>
        </div>
        ${error ? `<p class="empty">${esc(error)}</p>` : blocks}
      </div>
    `;

    this.shadowRoot.querySelectorAll("[data-type]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._listType = btn.dataset.type;
        this._render();
      });
    });
    this.shadowRoot.querySelectorAll("[data-scope]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this._scopeFilter = btn.dataset.scope;
        this._render();
      });
    });
    this.shadowRoot.querySelectorAll("form.add-row").forEach((form) => {
      form.addEventListener("submit", (ev) => {
        ev.preventDefault();
        this._add(form.dataset.listId, form);
      });
    });
    this.shadowRoot.querySelectorAll("[data-toggle]").forEach((el) => {
      el.addEventListener("change", () => this._toggle(JSON.parse(el.dataset.toggle)));
    });
    this.shadowRoot.querySelectorAll("[data-notify]").forEach((el) => {
      el.addEventListener("click", () => this._notify(JSON.parse(el.dataset.notify)));
    });
    this.shadowRoot.querySelectorAll("[data-del]").forEach((el) => {
      el.addEventListener("click", () => this._delete(JSON.parse(el.dataset.del)));
    });
  }

  _listHtml(lst) {
    const items = (lst.items || []).filter((item) => item.status !== "cancelled");
    const rows = items.length
      ? items.map((item) => this._itemHtml(item)).join("")
      : `<p class="empty">Пусто</p>`;
    return `
      <section class="list-block">
        <h2>${esc(lst.scope_title)} — ${esc(lst.name)}</h2>
        ${rows}
        <form class="add-row" data-list-id="${esc(lst.list_id)}">
          <input name="title" type="text" placeholder="Новый элемент" required />
          <input name="due" type="datetime-local" />
          <button type="submit">Добавить</button>
        </form>
      </section>
    `;
  }

  _itemHtml(item) {
    const done = item.status === "completed";
    const payload = esc(JSON.stringify(item));
    return `
      <div class="item">
        <input type="checkbox" data-toggle="${payload}" ${done ? "checked" : ""} />
        <div>
          <div style="${done ? "text-decoration:line-through;opacity:.7" : ""}">${esc(item.title)}</div>
          <div class="meta">📅 ${esc(formatDue(item.due_at))} ${item.notifications_enabled ? "🔔" : ""} ${item.is_recurring ? "🔁" : ""}</div>
        </div>
        <div class="item-actions">
          <button data-notify="${payload}">${item.notifications_enabled ? "🔔" : "🔕"}</button>
          <button data-del="${payload}">🗑</button>
        </div>
      </div>
    `;
  }
}

customElements.define("buymelater-panel", BuyMeLaterPanel);
