function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDue(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

class BuyMeLaterCard extends HTMLElement {
  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._loaded) {
      this._loaded = true;
      this._unsub = hass.connection.subscribeEvents(() => this._load(), "buymelater_event");
      this._load();
    } else if (this._lists) {
      this._render();
    }
  }

  disconnectedCallback() {
    if (this._unsub) this._unsub();
  }

  getCardSize() {
    return 4;
  }

  async _load() {
    if (!this._hass) return;
    try {
      const result = await this._hass.connection.sendMessagePromise({ type: "buymelater/overview" });
      this._lists = result.lists || [];
      this._userId = result.user_id;
      this._error = null;
    } catch (err) {
      this._error = err.message || String(err);
    }
    this._render();
  }

  _targetLists() {
    const lists = this._lists || [];
    if (this._config.list_id) {
      return lists.filter((lst) => lst.list_id === this._config.list_id);
    }
    if (this._config.list_type) {
      return lists.filter((lst) => lst.list_type === this._config.list_type);
    }
    if (this._config.entity) {
      const state = this._hass.states[this._config.entity];
      const name = state?.attributes?.friendly_name;
      if (name) {
        const matched = lists.filter((lst) => `${lst.scope_title} — ${lst.name}` === name);
        if (matched.length) return matched;
      }
    }
    return lists;
  }

  async _send(msg) {
    await this._hass.connection.sendMessagePromise(msg);
    await this._load();
  }

  async _toggle(item) {
    await this._send({
      type: "buymelater/update_item",
      item_id: item.id,
      status: item.status === "completed" ? "active" : "completed",
    });
  }

  async _add(listId, title) {
    if (!title.trim()) return;
    await this._send({ type: "buymelater/create_item", list_id: listId, title: title.trim() });
  }

  _render() {
    if (!this._config) return;
    const lists = this._targetLists();
    const title = this._config.title || "BuyMeLater";
    const body = this._error
      ? `<p class="empty">${esc(this._error)}</p>`
      : lists.map((lst) => this._listHtml(lst)).join("") || `<p class="empty">Нет списков</p>`;

    this.innerHTML = `
      <ha-card>
        <style>
          .bml-card { padding: 12px 16px 16px; }
          .bml-card h2 { margin: 0 0 10px; font-size: 1.15rem; }
          .bml-list { margin-bottom: 12px; }
          .bml-list h3 { font-size: 0.95rem; margin: 0 0 6px; opacity: 0.85; }
          .item { display: flex; gap: 8px; align-items: flex-start; padding: 6px 0; border-bottom: 1px solid var(--divider-color); }
          .meta { font-size: 0.8rem; opacity: 0.75; }
          .add { display: flex; gap: 6px; margin-top: 8px; }
          .add input { flex: 1; padding: 6px 8px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }
          .empty { opacity: 0.7; }
        </style>
        <div class="bml-card">
          <h2>${esc(title)}</h2>
          ${body}
        </div>
      </ha-card>
    `;

    this.querySelectorAll("[data-toggle]").forEach((el) => {
      el.addEventListener("change", () => this._toggle(JSON.parse(el.dataset.toggle)));
    });
    this.querySelectorAll("form.add").forEach((form) => {
      form.addEventListener("submit", (ev) => {
        ev.preventDefault();
        const input = form.querySelector("input");
        this._add(form.dataset.listId, input.value);
        input.value = "";
      });
    });
  }

  _listHtml(lst) {
    const items = (lst.items || []).filter((item) => item.status !== "cancelled" && item.status !== "completed");
    const rows = items.length
      ? items
          .map(
            (item) => `
          <div class="item">
            <input type="checkbox" data-toggle="${esc(JSON.stringify(item))}" />
            <div>
              <div>${esc(item.title)}</div>
              <div class="meta">${item.due_at ? `📅 ${esc(formatDue(item.due_at))}` : ""} ${item.notifications_enabled ? "🔔" : ""} ${item.is_recurring ? "🔁" : ""}</div>
            </div>
          </div>`,
          )
          .join("")
      : `<p class="empty">Пусто</p>`;
    return `
      <div class="bml-list">
        <h3>${esc(lst.scope_title)} — ${esc(lst.name)}</h3>
        ${rows}
        <form class="add" data-list-id="${esc(lst.list_id)}">
          <input type="text" placeholder="Добавить…" />
        </form>
      </div>
    `;
  }
}

customElements.define("buymelater-card", BuyMeLaterCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "buymelater-card",
  name: "BuyMeLater",
  description: "Семейные списки покупок и дел",
  preview: true,
});
