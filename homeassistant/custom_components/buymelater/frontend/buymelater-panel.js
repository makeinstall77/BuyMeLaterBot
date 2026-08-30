class BuyMeLaterPanel extends HTMLElement {
  connectedCallback() {
    this._events = [];
    this._render();
    this._hass = document.querySelector("home-assistant")?.hass;
    if (this._hass) {
      this._unsub = this._hass.connection.subscribeEvents(
        (ev) => {
          if (ev.event_type !== "buymelater_event") return;
          this._events.unshift(ev.data);
          if (this._events.length > 20) this._events.length = 20;
          this._render();
        },
        "buymelater_event",
      );
    }
  }

  disconnectedCallback() {
    if (this._unsub) this._unsub();
  }

  _render() {
    const rows =
      this._events.length === 0
        ? "<p>Ожидание событий от API…</p>"
        : this._events
            .map(
              (e) =>
                `<li><code>${e.event || "?"}</code> ${e.data?.title || e.data?.id || ""}</li>`,
            )
            .join("");
    this.innerHTML = `
      <div style="padding:16px;font-family:sans-serif;">
        <h2>BuyMeLater</h2>
        <p>Списки доступны как <code>todo.*</code> entities. Ниже — live-события WebSocket.</p>
        <ul>${rows}</ul>
      </div>
    `;
  }
}

customElements.define("buymelater-panel", BuyMeLaterPanel);
