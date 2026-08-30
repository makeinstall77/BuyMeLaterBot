class BuyMeLaterPanel extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div style="padding:16px;font-family:sans-serif;">
        <h2>BuyMeLater</h2>
        <p>Списки доступны как <code>todo.*</code> entities.</p>
        <p>Добавьте карточку To-do List на дашборд или используйте боковое меню todo.</p>
      </div>
    `;
  }
}

customElements.define("buymelater-panel", BuyMeLaterPanel);
