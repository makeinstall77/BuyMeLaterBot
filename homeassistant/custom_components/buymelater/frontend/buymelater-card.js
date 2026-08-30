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
    const result = await this._hass.connection.sendMessagePromise(msg);
    if (msg.type === "buymelater/delete_item") {
      const iid = String(msg.item_id);
      this._lists = (this._lists || []).map((lst) => ({
        ...lst,
        items: (lst.items || []).filter((existing) => String(existing.id) !== iid),
      }));
    } else if (result && result.id) {
      this._lists = (this._lists || []).map((lst) => ({
        ...lst,
        items: (lst.items || []).map((existing) =>
          String(existing.id) === String(result.id) ? { ...existing, ...result } : existing,
        ),
      }));
    }
    this._render();
    await this._load();
  }

  async _toggle(item) {
    await this._send({
      type: "buymelater/update_item",
      item_id: item.id,
      status: item.status === "completed" ? "active" : "completed",
    });
  }

  async _notify(item) {
    await this._send({
      type: "buymelater/update_item",
      item_id: item.id,
      notifications_enabled: !item.notifications_enabled,
    });
  }

  async _saveRecur(item, form) {
    const preset = form.querySelector("[name=preset]").value;
    const byday = form.querySelector("[name=byday]")?.value;
    const monthday = form.querySelector("[name=monthday]")?.value;
    const due = form.querySelector("[name=due]").value;
    const rrule = bmlBuildRrule(preset, byday, monthday);
    this._editId = null;
    await this._send({
      type: "buymelater/update_item",
      item_id: item.id,
      due_at: due ? new Date(due).toISOString() : null,
      is_recurring: Boolean(rrule),
      rrule,
      notifications_enabled: Boolean(due),
    });
  }

  async _add(listId, form) {
    const title = form.querySelector("input[name=title]").value.trim();
    if (!title) return;
    const due = form.querySelector("input[name=due]")?.value;
    const preset = form.querySelector("[name=preset]")?.value;
    const rrule = bmlBuildRrule(preset);
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
          .item-actions { margin-left: auto; display: flex; gap: 4px; }
          .item-actions button { padding: 2px 6px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--secondary-background-color); color: var(--primary-text-color); cursor: pointer; }
          .edit-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
          .edit-row select, .edit-row input { padding: 4px 6px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }
          .add { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
          .add input, .add select { padding: 6px 8px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }
          .add input[name=title] { flex: 1; min-width: 8rem; }
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
    this.querySelectorAll("[data-notify]").forEach((el) => {
      el.addEventListener("click", () => this._notify(JSON.parse(el.dataset.notify)));
    });
    this.querySelectorAll("[data-edit]").forEach((el) => {
      el.addEventListener("click", () => {
        const id = el.dataset.edit;
        this._editId = this._editId === id ? null : id;
        this._render();
      });
    });
    this.querySelectorAll("form.edit-row").forEach((form) => {
      form.addEventListener("submit", (ev) => {
        ev.preventDefault();
        this._saveRecur(JSON.parse(form.dataset.item), form);
      });
    });
    this.querySelectorAll("form.add").forEach((form) => {
      form.addEventListener("submit", (ev) => {
        ev.preventDefault();
        this._add(form.dataset.listId, form);
      });
    });
  }

  _listHtml(lst) {
    const items = (lst.items || []).filter((item) => item.status !== "cancelled" && item.status !== "completed");
    const rows = items.length
      ? items.map((item) => this._itemHtml(item)).join("")
      : `<p class="empty">Пусто</p>`;
    return `
      <div class="bml-list">
        <h3>${esc(lst.scope_title)} — ${esc(lst.name)}</h3>
        ${rows}
        <form class="add" data-list-id="${esc(lst.list_id)}">
          <input name="title" type="text" placeholder="Добавить…" />
          <input name="due" type="datetime-local" />
          <select name="preset">
            <option value="once">Разово</option>
            <option value="daily">Ежедневно</option>
            <option value="weekdays">По будням</option>
            <option value="weekly">Еженедельно</option>
            <option value="monthly">Ежемесячно</option>
          </select>
        </form>
      </div>
    `;
  }

  _itemHtml(item) {
    const payload = esc(JSON.stringify(item));
    const editing = this._editId === String(item.id);
    const preset = bmlPresetFromRrule(item.rrule) || "once";
    const weekOpts = Object.entries(BML_BYDAY)
      .map(([code, label]) => `<option value="${code}" ${bmlWeekdayFromRrule(item.rrule) === code ? "selected" : ""}>${label}</option>`)
      .join("");
    const extra = preset === "weekly"
      ? `<select name="byday">${weekOpts}</select>`
      : preset === "monthly"
        ? `<input name="monthday" type="number" min="1" max="31" value="${esc(bmlMonthdayFromRrule(item.rrule))}" style="width:4.5em" />`
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
          <button type="submit">OK</button>
        </form>`
      : "";
    return `
      <div class="item">
        <input type="checkbox" data-toggle="${payload}" />
        <div style="flex:1">
          <div>${esc(item.title)}</div>
          <div class="meta">${esc(bmlItemMeta(item))}</div>
          ${editor}
        </div>
        <div class="item-actions">
          <button data-notify="${payload}">${item.notifications_enabled ? "🔔" : "🔕"}</button>
          <button data-edit="${esc(item.id)}">🔁</button>
        </div>
      </div>`;
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
