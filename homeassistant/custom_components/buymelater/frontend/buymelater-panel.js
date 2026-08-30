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
.edit-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; align-items: center; }
.edit-row select, .edit-row input { padding: 4px 8px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }
.empty { opacity: 0.7; padding: 8px 0; }
`;

const BML_BYDAY = { MO: "пн", TU: "вт", WE: "ср", TH: "чт", FR: "пт", SA: "сб", SU: "вс" };
const BML_PRESETS = {
  daily: "Ежедневно",
  weekdays: "По будням",
  weekly: "Еженедельно",
  monthly: "Ежемесячно",
};

function bmlFormatDue(iso) {
  if (!iso) return "без даты";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function bmlPresetFromRrule(rrule) {
  if (!rrule) return null;
  if (rrule.startsWith("FREQ=DAILY")) return "daily";
  if (rrule.includes("BYDAY=MO,TU,WE,TH,FR")) return "weekdays";
  if (rrule.startsWith("FREQ=WEEKLY")) return "weekly";
  if (rrule.startsWith("FREQ=MONTHLY")) return "monthly";
  return null;
}

function bmlFormatRecurrence(item) {
  if (item?.recurrence_label) return item.recurrence_label;
  if (!item?.is_recurring || !item?.rrule) return "";
  const rrule = item.rrule;
  const preset = bmlPresetFromRrule(rrule);
  if (preset === "weekly") {
    for (const [code, label] of Object.entries(BML_BYDAY)) {
      if (rrule.includes(`BYDAY=${code}`) && !rrule.includes("MO,TU")) {
        return `${BML_PRESETS.weekly} (${label})`;
      }
    }
  }
  if (preset === "monthly" && rrule.includes("BYMONTHDAY=")) {
    const day = rrule.split("BYMONTHDAY=")[1].split(";")[0];
    return `${BML_PRESETS.monthly} (${day}-го)`;
  }
  if (preset && BML_PRESETS[preset]) return BML_PRESETS[preset];
  return "да";
}

function bmlItemMeta(item) {
  const parts = [];
  if (item.due_at) parts.push(`📅 ${bmlFormatDue(item.due_at)}`);
  if (item.notifications_enabled) parts.push("🔔");
  const recur = bmlFormatRecurrence(item);
  if (recur) parts.push(`🔁 ${recur}`);
  return parts.join(" ");
}

function bmlBuildRrule(preset, byday, monthday) {
  if (!preset || preset === "once") return null;
  if (preset === "daily") return "FREQ=DAILY";
  if (preset === "weekdays") return "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR";
  if (preset === "weekly") return `FREQ=WEEKLY;BYDAY=${byday || "MO"}`;
  if (preset === "monthly") return `FREQ=MONTHLY;BYMONTHDAY=${monthday || 1}`;
  return null;
}

function bmlToLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function bmlWeekdayFromRrule(rrule) {
  if (!rrule || rrule.includes("MO,TU")) return "MO";
  for (const code of Object.keys(BML_BYDAY)) {
    if (rrule.includes(`BYDAY=${code}`)) return code;
  }
  return "MO";
}

function bmlMonthdayFromRrule(rrule) {
  if (!rrule || !rrule.includes("BYMONTHDAY=")) return "1";
  return rrule.split("BYMONTHDAY=")[1].split(";")[0];
}

function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

class BuyMeLaterPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._listType = "shopping";
    this._scopeFilter = "all";
    this._lists = [];
    this._userId = null;
    this._editId = null;
    this._loading = false;
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
    if (!this._hass || this._loading) return;
    this._loading = true;
    try {
      const result = await this._hass.connection.sendMessagePromise({ type: "buymelater/overview" });
      this._lists = result.lists || [];
      this._userId = result.user_id;
      this._render();
    } catch (err) {
      this._lists = [];
      this._render(err.message || String(err));
    } finally {
      this._loading = false;
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

  _replaceItem(item) {
    if (!item?.id) return;
    this._lists = (this._lists || []).map((lst) => {
      const items = (lst.items || []).map((existing) =>
        String(existing.id) === String(item.id) ? { ...existing, ...item } : existing,
      );
      if (String(lst.list_id) === String(item.list_id) && !items.some((existing) => String(existing.id) === String(item.id))) {
        return { ...lst, items: [...items, item] };
      }
      return { ...lst, items };
    });
  }

  async _send(msg) {
    const result = await this._hass.connection.sendMessagePromise(msg);
    if (msg.type === "buymelater/delete_item") {
      const iid = String(msg.item_id);
      this._lists = (this._lists || []).map((lst) => ({
        ...lst,
        items: (lst.items || []).filter((existing) => String(existing.id) !== iid),
      }));
    } else if (result && result.id) {
      this._replaceItem(result);
    }
    this._render();
    await this._load();
    return result;
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
    const preset = form.querySelector("[name=preset]")?.value;
    const byday = form.querySelector("[name=byday]")?.value;
    const monthday = form.querySelector("[name=monthday]")?.value;
    const rrule = bmlBuildRrule(preset, byday, monthday);
    await this._send({
      type: "buymelater/create_item",
      list_id: listId,
      title,
      due_at: due ? new Date(due).toISOString() : null,
      is_recurring: Boolean(rrule),
      rrule,
      notifications_enabled: Boolean(due),
    });
    form.reset();
  }

  async _saveRecur(item, form) {
    const preset = form.querySelector("[name=preset]").value;
    const byday = form.querySelector("[name=byday]")?.value;
    const monthday = form.querySelector("[name=monthday]")?.value;
    const due = form.querySelector("[name=due]").value;
    const rrule = bmlBuildRrule(preset, byday, monthday);
    const payload = {
      type: "buymelater/update_item",
      item_id: item.id,
      due_at: due ? new Date(due).toISOString() : null,
      is_recurring: Boolean(rrule),
      rrule,
      notifications_enabled: Boolean(due),
    };
    this._editId = null;
    await this._send(payload);
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
    this.shadowRoot.querySelectorAll("[data-edit]").forEach((el) => {
      el.addEventListener("click", () => {
        const id = el.dataset.edit;
        this._editId = this._editId === id ? null : id;
        this._render();
      });
    });
    this.shadowRoot.querySelectorAll("form.edit-row").forEach((form) => {
      form.addEventListener("submit", (ev) => {
        ev.preventDefault();
        this._saveRecur(JSON.parse(form.dataset.item), form);
      });
      form.querySelector("[name=preset]")?.addEventListener("change", () => {
        this._presetDraft = form.querySelector("[name=preset]").value;
        const item = JSON.parse(form.dataset.item);
        this._editId = item.id;
        this._render();
      });
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
          <select name="preset">
            <option value="once">Разово</option>
            <option value="daily">Ежедневно</option>
            <option value="weekdays">По будням</option>
            <option value="weekly">Еженедельно</option>
            <option value="monthly">Ежемесячно</option>
          </select>
          <button type="submit">Добавить</button>
        </form>
      </section>
    `;
  }

  _itemHtml(item) {
    const done = item.status === "completed";
    const payload = esc(JSON.stringify(item));
    const editing = this._editId === String(item.id);
    const preset = editing && this._presetDraft ? this._presetDraft : (bmlPresetFromRrule(item.rrule) || "once");
    const weekOpts = Object.entries(BML_BYDAY)
      .map(([code, label]) => `<option value="${code}" ${bmlWeekdayFromRrule(item.rrule) === code ? "selected" : ""}>${label}</option>`)
      .join("");
    const monthday = bmlMonthdayFromRrule(item.rrule);
    const extra = preset === "weekly"
      ? `<select name="byday">${weekOpts}</select>`
      : preset === "monthly"
        ? `<input name="monthday" type="number" min="1" max="31" value="${esc(monthday)}" style="width:4.5em" />`
        : "";
    const editor = editing
      ? `<form class="edit-row" data-item="${payload}">
          <select name="preset">
            <option value="once" ${preset === "once" ? "selected" : ""}>Разово</option>
            <option value="daily" ${preset === "daily" ? "selected" : ""}>Ежедневно</option>
            <option value="weekdays" ${preset === "weekdays" ? "selected" : ""}>По будням</option>
            <option value="weekly" ${preset === "weekly" ? "selected" : ""}>Еженедельно</option>
            <option value="monthly" ${preset === "monthly" ? "selected" : ""}>Ежемесячно</option>
          </select>
          ${extra}
          <input name="due" type="datetime-local" value="${esc(bmlToLocalInput(item.due_at))}" />
          <button type="submit">Сохранить</button>
        </form>`
      : "";
    return `
      <div class="item">
        <input type="checkbox" data-toggle="${payload}" ${done ? "checked" : ""} />
        <div style="flex:1">
          <div style="${done ? "text-decoration:line-through;opacity:.7" : ""}">${esc(item.title)}</div>
          <div class="meta">${esc(bmlItemMeta(item))}</div>
          ${editor}
        </div>
        <div class="item-actions">
          <button data-notify="${payload}">${item.notifications_enabled ? "🔔" : "🔕"}</button>
          <button data-edit="${esc(item.id)}">🔁</button>
          <button data-del="${payload}">🗑</button>
        </div>
      </div>
    `;
  }
}

customElements.define("buymelater-panel", BuyMeLaterPanel);
