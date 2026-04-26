/*
 * Danish News Card
 * Home Assistant Lovelace custom card bundled with custom_components/danish_news
 */
const CARD_VERSION = "0.1.0";
const CARD_TAG = "danish-news-card";
const DOMAIN = "danish_news";

const DEFAULT_CONFIG = {
  title: "Dagens nyheder",
  entity: "",
  providers: ["tv2", "dr", "eb", "bt"],
  max_articles: 8,
  scale: 1,
  background_mode: "theme",
  frame_mode: "theme",
  show_summaries: true,
  show_source_link: false,
  compact: false
};

const PROVIDERS = {
  tv2: { name: "TV 2", shortName: "TV 2", accent: "#0b5fff", logo: "tv2" },
  dr: { name: "DR", shortName: "DR", accent: "#c70039", logo: "dr" },
  eb: { name: "Ekstra Bladet", shortName: "EB", accent: "#ffd200", logo: "eb" },
  bt: { name: "B.T.", shortName: "B.T.", accent: "#e30613", logo: "bt" }
};

const PROVIDER_OPTIONS = Object.entries(PROVIDERS)
  .map(([value, provider]) => ({ value, label: provider.name }));
const BACKGROUND_OPTIONS = [
  { value: "theme", label: "Følg Home Assistant-tema" },
  { value: "light", label: "Lys baggrund / mørk tekst" },
  { value: "dark", label: "Sort baggrund / hvid tekst" }
];
const FRAME_OPTIONS = [
  { value: "theme", label: "Følg Home Assistant-tema" },
  { value: "light", label: "Lys ramme" },
  { value: "dark", label: "Sort ramme" }
];

const CONFIG_LABELS = {
  title: "Titel",
  entity: "Nyhedssensor",
  providers: "Udbydere i kortet",
  max_articles: "Maks. overskrifter",
  scale: "Skalering",
  background_mode: "Baggrund",
  frame_mode: "Ramme",
  show_summaries: "Vis korte resumeer",
  show_source_link: "Vis kildelink",
  compact: "Kompakt layout"
};
const CONFIG_HELPERS = {
  providers: "Vælg de medier kortet må vise. Selve dashboardkortet viser kun nyhedsoverblikket.",
  scale: "Justér grundskaleringen. Kortet skalerer også automatisk efter dashboard-kolonnens bredde.",
  background_mode: "Tema bruger Home Assistants aktuelle farver. Sort baggrund giver hvid tekst i hele nyhedsoverblikket.",
  frame_mode: "Tema bruger Home Assistants kort-ramme. Lys og sort tvinger selve rammen omkring kortet."
};

class DanishNewsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = { ...DEFAULT_CONFIG };
    this._hass = undefined;
    this._article = undefined;
    this._articleLoading = false;
    this._articleError = "";
    this._renderQueued = false;
  }

  set hass(hass) {
    this._hass = hass;
    this._queueRender();
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("Invalid configuration");
    }

    const providers = normalizeProviders(config.providers);

    this._config = {
      ...DEFAULT_CONFIG,
      ...config,
      providers,
      max_articles: clampNumber(Number(config.max_articles) || DEFAULT_CONFIG.max_articles, 1, 40),
      scale: clampNumber(Number(config.scale) || DEFAULT_CONFIG.scale, 0.75, 1.35),
      background_mode: normalizeThemeMode(config.background_mode, "background_mode"),
      frame_mode: normalizeThemeMode(config.frame_mode, "frame_mode"),
      show_summaries: normalizeBoolean(config.show_summaries, DEFAULT_CONFIG.show_summaries),
      show_source_link: normalizeBoolean(config.show_source_link, DEFAULT_CONFIG.show_source_link),
      compact: normalizeBoolean(config.compact, DEFAULT_CONFIG.compact)
    };
    this._article = undefined;
    this._articleError = "";
    this._render();
  }

  getCardSize() {
    return this._article ? 7 : 5;
  }

  getGridOptions() {
    return {
      rows: this._article ? 7 : 5,
      columns: 12,
      min_rows: 4,
      min_columns: 6
    };
  }

  static getStubConfig() {
    return {
      type: `custom:${CARD_TAG}`,
      title: "Dagens nyheder",
      providers: ["tv2", "dr", "eb", "bt"],
      max_articles: 8,
      scale: 1,
      background_mode: "theme",
      frame_mode: "theme",
      show_summaries: true
    };
  }

  static getConfigForm() {
    return {
      schema: [
        { name: "title", selector: { text: {} } },
        { name: "entity", selector: { entity: { domain: "sensor" } } },
        {
          name: "providers",
          selector: {
            select: {
              multiple: true,
              mode: "dropdown",
              options: PROVIDER_OPTIONS
            }
          }
        },
        {
          name: "max_articles",
          selector: {
            number: {
              min: 1,
              max: 40,
              step: 1,
              mode: "slider"
            }
          }
        },
        {
          name: "scale",
          selector: {
            number: {
              min: 0.75,
              max: 1.35,
              step: 0.05,
              mode: "slider"
            }
          }
        },
        {
          name: "background_mode",
          selector: {
            select: {
              mode: "dropdown",
              options: BACKGROUND_OPTIONS
            }
          }
        },
        {
          name: "frame_mode",
          selector: {
            select: {
              mode: "dropdown",
              options: FRAME_OPTIONS
            }
          }
        },
        {
          type: "grid",
          name: "",
          flatten: true,
          column_min_width: "180px",
          schema: [
            { name: "show_summaries", selector: { boolean: {} } },
            { name: "show_source_link", selector: { boolean: {} } },
            { name: "compact", selector: { boolean: {} } }
          ]
        }
      ],
      computeLabel: (schema) => CONFIG_LABELS[schema.name],
      computeHelper: (schema) => CONFIG_HELPERS[schema.name]
    };
  }

  _queueRender() {
    if (this._renderQueued) {
      return;
    }
    this._renderQueued = true;
    requestAnimationFrame(() => {
      this._renderQueued = false;
      this._render();
    });
  }

  _render() {
    if (!this.shadowRoot) {
      return;
    }

    const sensor = this._getSensorState();
    const entryId = sensor?.attributes?.entry_id || "";
    const articles = this._getVisibleArticles(sensor);
    const updatedAt = sensor?.attributes?.updated_at || "";
    const status = this._statusText(sensor, articles, updatedAt);
    const scale = this._config.scale;
    const backgroundMode = normalizeThemeMode(this._config.background_mode, "background_mode");
    const frameMode = normalizeThemeMode(this._config.frame_mode, "frame_mode");
    const minFont = (11.5 * scale).toFixed(2);
    const maxFont = (16 * scale).toFixed(2);

    this.shadowRoot.innerHTML = `
      <style>${this._styles()}</style>
      <ha-card class="frame-${escapeAttr(frameMode)}">
        <div class="card background-${escapeAttr(backgroundMode)} ${this._config.compact ? "compact" : ""}" style="--news-min-font:${minFont}px;--news-max-font:${maxFont}px;">
          <header class="header">
            <div class="title-block">
              <h2>${escapeHtml(this._config.title)}</h2>
              <p>${escapeHtml(status)}</p>
            </div>
            <button class="icon-button" data-action="refresh" aria-label="Opdater nyheder" title="Opdater">
              <ha-icon icon="mdi:refresh"></ha-icon>
            </button>
          </header>

          ${this._article ? this._renderArticle(entryId) : this._renderOverview(sensor, articles)}
        </div>
      </ha-card>
    `;

    this._bindActions();
  }

  _renderOverview(sensor, articles) {
    if (!sensor) {
      return this._renderEmpty("Tilføj integrationen Danske nyheder, eller vælg sensoren manuelt i kortets indstillinger.");
    }

    return `
      ${articles.length ? `
        <section class="article-list" aria-label="Nyhedsoverblik">
          ${articles.map((article, index) => this._renderArticleButton(article, index)).join("")}
        </section>
      ` : this._renderEmpty("Ingen gratis artikler fundet for de valgte udbydere i dag.")}
    `;
  }

  _renderArticleButton(article, index) {
    const provider = providerFor(article);
    const breaking = isBreakingArticle(article);
    const summary = this._config.show_summaries && summaryText(article)
      ? `<p>${escapeHtml(summaryText(article))}</p>`
      : "";
    const sourceLink = this._config.show_source_link && article.url
      ? `<a class="overview-source-link" href="${escapeAttr(article.url)}" target="_blank" rel="noreferrer noopener">
          <ha-icon icon="mdi:open-in-new"></ha-icon>
          <span>Åbn kilde</span>
        </a>`
      : "";

    return `
      <article
        class="article-item ${breaking ? "breaking" : ""}"
        style="--provider-accent:${escapeAttr(provider.accent)}"
      >
        <button
          class="article-button"
          data-action="open-article"
          data-article-index="${index}"
        >
          <span class="source-row">
            ${this._renderProviderLogo(provider)}
            ${breaking ? `<span class="breaking-label">Breaking</span>` : ""}
            <time>${escapeHtml(formatTime(article.published))}</time>
            ${article.category ? `<span>${escapeHtml(article.category)}</span>` : ""}
          </span>
          <strong>${escapeHtml(article.title)}</strong>
          ${summary}
        </button>
        ${sourceLink}
      </article>
    `;
  }

  _renderArticle(entryId) {
    const article = this._article || {};
    const provider = providerFor(article);
    const breaking = isBreakingArticle(article);
    const body = Array.isArray(article.body) ? article.body : [];
    const hasBody = body.length > 0;
    const summary = summaryText(article);
    const sourceLink = this._config.show_source_link && article.url
      ? `<a class="source-link" href="${escapeAttr(article.url)}" target="_blank" rel="noreferrer noopener">
          <ha-icon icon="mdi:open-in-new"></ha-icon>
          <span>Åbn kilde</span>
        </a>`
      : "";

    return `
      <article class="article-view ${breaking ? "breaking" : ""}" style="--provider-accent:${escapeAttr(provider.accent)}">
        <button class="back-button" data-action="back">
          <ha-icon icon="mdi:arrow-left"></ha-icon>
          <span>Overblik</span>
        </button>

        <div class="article-heading">
          ${this._renderProviderLogo(provider)}
          ${breaking ? `<span class="breaking-label">Breaking</span>` : ""}
          <time>${escapeHtml(formatTime(article.published))}</time>
        </div>

        <h3>${escapeHtml(article.title || "Artikel")}</h3>
        ${this._config.show_summaries && summary ? `<p class="lead">${escapeHtml(summary)}</p>` : ""}
        ${article.byline ? `<p class="byline">${escapeHtml(article.byline)}</p>` : ""}

        ${this._articleLoading ? this._renderLoading() : ""}
        ${this._articleError ? this._renderInlineMessage(this._articleError) : ""}
        ${article.paywalled ? this._renderInlineMessage("Artiklen ser ud til at være bag betalingsmur og vises derfor ikke her.") : ""}
        ${!this._articleLoading && !article.paywalled && !this._articleError && !hasBody
          ? this._renderInlineMessage(entryId ? "Der blev kun fundet et kort resume for denne artikel." : "Artikelvisning kræver backend-integrationen.")
          : ""}

        ${hasBody ? `
          <div class="article-body">
            ${body.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("")}
          </div>
        ` : ""}

        ${sourceLink}
      </article>
    `;
  }

  _renderEmpty(message) {
    return `
      <div class="empty-state">
        <ha-icon icon="mdi:newspaper-variant-outline"></ha-icon>
        <span>${escapeHtml(message)}</span>
      </div>
    `;
  }

  _renderLoading() {
    return `
      <div class="inline-message loading">
        <ha-icon icon="mdi:loading"></ha-icon>
        <span>Henter artikel</span>
      </div>
    `;
  }

  _renderInlineMessage(message) {
    return `
      <div class="inline-message">
        <ha-icon icon="mdi:information-outline"></ha-icon>
        <span>${escapeHtml(message)}</span>
      </div>
    `;
  }

  _renderProviderLogo(provider) {
    const logo = provider.logo || "fallback";
    const label = provider.shortName || provider.name || "Nyhed";
    return `
      <span class="provider-logo logo-${escapeAttr(logo)}" aria-label="${escapeAttr(provider.name || label)}">
        <span>${escapeHtml(label)}</span>
      </span>
    `;
  }

  _bindActions() {
    this.shadowRoot.querySelectorAll("[data-action='open-article']").forEach((button) => {
      button.addEventListener("click", (event) => {
        const index = Number(event.currentTarget.dataset.articleIndex);
        const article = this._getVisibleArticles(this._getSensorState())[index];
        if (article) {
          this._openArticle(article);
        }
      });
    });

    this.shadowRoot.querySelector("[data-action='back']")?.addEventListener("click", () => {
      this._article = undefined;
      this._articleLoading = false;
      this._articleError = "";
      this._render();
    });

    this.shadowRoot.querySelector("[data-action='refresh']")?.addEventListener("click", () => {
      this._refreshSensor();
    });
  }

  async _openArticle(article) {
    const sensor = this._getSensorState();
    const entryId = sensor?.attributes?.entry_id;

    this._article = {
      ...article,
      body: Array.isArray(article.body) ? article.body : []
    };
    this._articleLoading = true;
    this._articleError = "";
    this._render();

    if (!this._hass?.callWS || !entryId) {
      const summary = summaryText(article);
      this._article = {
        ...this._article,
        body: summary ? [summary] : []
      };
      this._articleLoading = false;
      this._render();
      return;
    }

    try {
      const details = await this._hass.callWS({
        type: "danish_news/get_article",
        entry_id: entryId,
        provider: article.provider,
        article_id: article.id,
        url: article.url
      });
      this._article = {
        ...article,
        ...details
      };
    } catch (err) {
      this._articleError = readableError(err);
    } finally {
      this._articleLoading = false;
      this._render();
    }
  }

  _refreshSensor() {
    const entityId = this._getSensorEntityId();
    if (!entityId || !this._hass?.callService) {
      return;
    }

    this._hass.callService("homeassistant", "update_entity", {
      entity_id: entityId
    });
  }

  _getVisibleArticles(sensor) {
    return this._getArticles(sensor).slice(0, this._config.max_articles);
  }

  _getArticles(sensor) {
    const articles = sensor?.attributes?.articles || [];
    if (!Array.isArray(articles)) {
      return [];
    }

    return articles
      .filter((article) => this._config.providers.includes(article.provider))
      .filter((article) => !article.paywalled)
      .sort((a, b) => timestamp(b.published) - timestamp(a.published));
  }

  _getSensorState() {
    const entityId = this._getSensorEntityId();
    return entityId ? this._hass?.states?.[entityId] : undefined;
  }

  _getSensorEntityId() {
    if (this._config.entity && this._hass?.states?.[this._config.entity]) {
      return this._config.entity;
    }

    const states = this._hass?.states || {};
    return Object.keys(states).find((entityId) => {
      const state = states[entityId];
      return entityId.startsWith("sensor.") && state?.attributes?.integration === DOMAIN;
    }) || "";
  }

  _statusText(sensor, articles, updatedAt) {
    if (!sensor) {
      return "Venter på nyhedssensor";
    }

    const count = articles.length;
    const providerCount = this._config.providers.length;
    const provider = providerCount === 1
      ? PROVIDERS[this._config.providers[0]]?.name || this._config.providers[0]
      : `${providerCount} udbydere`;
    const updated = formatRelative(updatedAt);
    const suffix = updated ? ` · ${updated}` : "";
    return `${count} overskrifter fra ${provider}${suffix}`;
  }

  _styles() {
    return `
      :host {
        display: block;
      }

      ha-card {
        --news-frame-radius: var(--ha-card-border-radius, 12px);
        --news-frame-bg: var(--ha-card-background, var(--card-background-color, #fff));
        --news-frame-border: var(--ha-card-border-color, var(--divider-color, rgba(126, 138, 150, 0.24)));
        --news-frame-shadow: var(--ha-card-box-shadow, none);
        background: var(--news-frame-bg);
        border: var(--ha-card-border-width, 1px) solid var(--news-frame-border);
        border-radius: var(--news-frame-radius);
        box-shadow: var(--news-frame-shadow);
        overflow: hidden;
        padding: 0;
      }

      ha-card.frame-light {
        --news-frame-bg: #ffffff;
        --news-frame-border: rgba(114, 128, 144, 0.34);
        --news-frame-shadow: 0 10px 28px rgba(20, 31, 42, 0.12);
        border-width: 1px;
        padding: 2px;
      }

      ha-card.frame-dark {
        --news-frame-bg: #000000;
        --news-frame-border: rgba(255, 255, 255, 0.34);
        --news-frame-shadow: 0 12px 30px rgba(0, 0, 0, 0.48);
        border-width: 1px;
        padding: 2px;
      }

      ha-card.frame-light .card,
      ha-card.frame-dark .card {
        border-radius: calc(var(--news-frame-radius) - 2px);
      }

      .card {
        --news-card-radius: 8px;
        --news-bg: var(--ha-card-background, var(--card-background-color, #fff));
        --news-panel-bg: color-mix(in srgb, var(--news-bg) 86%, var(--secondary-background-color, #f1f4f6));
        --news-control-bg: var(--secondary-background-color, #f2f4f6);
        --news-hover-bg: color-mix(in srgb, var(--news-control-bg) 72%, var(--news-bg));
        --news-text: var(--primary-text-color, #1f2328);
        --news-muted: var(--secondary-text-color, #66717e);
        --news-link: var(--primary-color, #0b5fff);
        --news-border: var(--divider-color, rgba(126, 138, 150, 0.24));
        --news-strong-border: var(--divider-color, rgba(126, 138, 150, 0.28));
        background: var(--news-bg);
        color: var(--news-text);
        container-type: inline-size;
        font-size: clamp(var(--news-min-font), 3.15cqi, var(--news-max-font));
        padding: clamp(12px, 4cqi, 20px);
      }

      .card.background-light {
        --news-bg: #ffffff;
        --news-panel-bg: #f8fafc;
        --news-control-bg: #f2f5f8;
        --news-hover-bg: #edf2f7;
        --news-text: #1f2328;
        --news-muted: #5f6b7a;
        --news-link: #0b5fff;
        --news-border: rgba(114, 128, 144, 0.24);
        --news-strong-border: rgba(114, 128, 144, 0.32);
      }

      .card.background-dark {
        --news-bg: #000000;
        --news-panel-bg: #050505;
        --news-control-bg: #111111;
        --news-hover-bg: #1a1a1a;
        --news-text: #ffffff;
        --news-muted: #ffffff;
        --news-link: #93c5fd;
        --news-border: rgba(255, 255, 255, 0.24);
        --news-strong-border: rgba(255, 255, 255, 0.34);
      }

      .card.compact {
        padding: 0.85em;
      }

      button {
        color: inherit;
        font: inherit;
      }

      .header {
        align-items: flex-start;
        display: flex;
        gap: 0.85em;
        justify-content: space-between;
        margin-bottom: 1em;
      }

      .title-block {
        min-width: 0;
      }

      h2,
      h3,
      p {
        margin: 0;
      }

      h2 {
        font-size: 1.35em;
        font-weight: 700;
        letter-spacing: 0;
        line-height: 1.12;
      }

      .header p {
        color: var(--news-muted);
        font-size: 0.9em;
        line-height: 1.35;
        margin-top: 0.25em;
      }

      .icon-button,
      .back-button,
      .article-button {
        -webkit-tap-highlight-color: transparent;
        cursor: pointer;
      }

      .icon-button {
        align-items: center;
        background: var(--news-control-bg);
        border: 1px solid var(--news-strong-border);
        border-radius: var(--news-card-radius);
        display: inline-flex;
        flex: 0 0 auto;
        height: 2.7em;
        justify-content: center;
        padding: 0;
        width: 2.7em;
      }

      .icon-button ha-icon {
        --mdc-icon-size: 1.35em;
        color: var(--news-muted);
      }

      .article-list {
        display: grid;
        gap: 0.6em;
      }

      .article-item {
        background: var(--news-panel-bg);
        border: 1px solid var(--news-border);
        border-left: 0.32em solid var(--provider-accent);
        border-radius: var(--news-card-radius);
        color: var(--news-text);
        display: grid;
        overflow: hidden;
      }

      .article-button {
        background: transparent;
        border: 0;
        display: grid;
        gap: 0.4em;
        min-height: 5.3em;
        padding: 0.72em 0.85em;
        text-align: left;
        width: 100%;
      }

      .article-item.breaking {
        background: linear-gradient(90deg, #fff2a8, #fff8d5);
        border-color: #e4bc00;
        color: #2c2100;
        box-shadow: inset 0 0 0 1px rgba(171, 129, 0, 0.08);
      }

      .article-item.breaking .source-row,
      .article-item.breaking p,
      .article-item.breaking .overview-source-link {
        color: #61510f;
      }

      .article-item:hover,
      .icon-button:hover,
      .back-button:hover {
        background: var(--news-hover-bg);
      }

      .article-item.breaking:hover {
        background: linear-gradient(90deg, #ffec79, #fff4bd);
      }

      .article-button:focus-visible,
      .overview-source-link:focus-visible,
      .source-link:focus-visible,
      .icon-button:focus-visible,
      .back-button:focus-visible {
        outline: 2px solid var(--primary-color, #0b5fff);
        outline-offset: -2px;
      }

      .source-row,
      .article-heading {
        align-items: center;
        color: var(--news-muted);
        display: flex;
        flex-wrap: wrap;
        gap: 0.55em;
        font-size: 0.78em;
        line-height: 1.25;
      }

      .provider-logo {
        align-items: center;
        border-radius: 0.24em;
        box-shadow: 0 1px 2px rgba(20, 31, 42, 0.16);
        display: inline-flex;
        flex: 0 0 auto;
        font-size: 0.8em;
        font-weight: 800;
        height: 1.65em;
        justify-content: center;
        line-height: 1;
        min-width: 2.55em;
        padding: 0 0.48em;
      }

      .provider-logo span {
        display: block;
        white-space: nowrap;
      }

      .logo-tv2 {
        background: #075fff;
        color: #fff;
      }

      .logo-tv2 span {
        font-weight: 850;
      }

      .logo-dr {
        background: #c4002f;
        color: #fff;
        font-family: Arial, Helvetica, sans-serif;
        letter-spacing: 0;
      }

      .logo-eb {
        background: #ffd200;
        border: 1px solid #161616;
        color: #111;
      }

      .logo-bt {
        background: #e30613;
        color: #fff;
      }

      .logo-fallback {
        background: var(--news-control-bg);
        color: var(--news-text);
      }

      .breaking-label {
        background: #ffd200;
        border: 1px solid #c89200;
        border-radius: 0.24em;
        color: #2c2100;
        font-size: 0.9em;
        font-weight: 780;
        line-height: 1;
        padding: 0.28em 0.42em;
        text-transform: uppercase;
      }

      .article-button strong {
        font-size: 0.98em;
        font-weight: 690;
        letter-spacing: 0;
        line-height: 1.22;
      }

      .article-button p {
        color: var(--news-muted);
        font-size: 0.86em;
        line-height: 1.35;
      }

      .overview-source-link {
        align-items: center;
        border-top: 1px solid var(--news-border);
        color: var(--news-link);
        display: inline-flex;
        gap: 0.4em;
        justify-self: start;
        margin: 0 0.85em 0.75em;
        min-height: 1.8em;
        text-decoration: none;
        width: fit-content;
      }

      .overview-source-link ha-icon {
        --mdc-icon-size: 1em;
      }

      .article-view {
        display: grid;
        gap: 0.85em;
      }

      .article-view.breaking {
        background: linear-gradient(180deg, #fff7c7, rgba(255, 247, 199, 0.28));
        border: 1px solid #e4bc00;
        border-radius: var(--news-card-radius);
        color: #2c2100;
        padding: 0.85em;
      }

      .article-view.breaking .article-heading,
      .article-view.breaking .lead,
      .article-view.breaking .byline,
      .article-view.breaking .source-link {
        color: #61510f;
      }

      .back-button {
        align-items: center;
        background: var(--news-control-bg);
        border: 1px solid var(--news-strong-border);
        border-radius: var(--news-card-radius);
        display: inline-flex;
        gap: 0.55em;
        justify-self: start;
        min-height: 2.55em;
        padding: 0.5em 0.75em;
      }

      .back-button ha-icon {
        --mdc-icon-size: 1.25em;
      }

      .article-view h3 {
        font-size: 1.2em;
        font-weight: 730;
        letter-spacing: 0;
        line-height: 1.16;
      }

      .lead {
        color: var(--news-muted);
        font-size: 0.96em;
        font-weight: 560;
        line-height: 1.42;
      }

      .byline {
        color: var(--news-muted);
        font-size: 0.82em;
      }

      .article-body {
        border-top: 1px solid var(--news-border);
        display: grid;
        gap: 0.7em;
        padding-top: 0.85em;
      }

      .article-body p {
        font-size: 0.96em;
        line-height: 1.55;
      }

      .inline-message,
      .empty-state {
        align-items: center;
        background: var(--news-control-bg);
        border: 1px solid var(--news-border);
        border-radius: var(--news-card-radius);
        color: var(--news-muted);
        display: flex;
        gap: 0.72em;
        line-height: 1.4;
        padding: 0.85em;
      }

      .inline-message ha-icon,
      .empty-state ha-icon {
        --mdc-icon-size: 1.4em;
        flex: 0 0 auto;
      }

      .loading ha-icon {
        animation: spin 1s linear infinite;
      }

      .source-link {
        align-items: center;
        color: var(--news-link);
        display: inline-flex;
        gap: 0.4em;
        font-weight: 650;
        justify-self: start;
        text-decoration: none;
      }

      .source-link ha-icon {
        --mdc-icon-size: 1.05em;
      }

      .card.compact .header {
        gap: 0.65em;
        margin-bottom: 0.7em;
      }

      .card.compact h2 {
        font-size: 1.16em;
      }

      .card.compact .header p {
        font-size: 0.78em;
        margin-top: 0.15em;
      }

      .card.compact .icon-button {
        height: 2.25em;
        width: 2.25em;
      }

      .card.compact .article-list {
        gap: 0.42em;
      }

      .card.compact .article-button {
        gap: 0.24em;
        min-height: 3.85em;
        padding: 0.5em 0.62em;
      }

      .card.compact .source-row,
      .card.compact .article-heading {
        gap: 0.38em;
        font-size: 0.68em;
      }

      .card.compact .provider-logo {
        font-size: 0.72em;
        height: 1.45em;
        min-width: 2.25em;
        padding: 0 0.38em;
      }

      .card.compact .breaking-label {
        padding: 0.2em 0.32em;
      }

      .card.compact .article-button strong {
        font-size: 0.9em;
        line-height: 1.16;
      }

      .card.compact .article-button p {
        font-size: 0.78em;
        line-height: 1.25;
      }

      .card.compact .overview-source-link {
        font-size: 0.78em;
        margin: 0 0.62em 0.5em;
        min-height: 1.45em;
      }

      .card.compact .article-view {
        gap: 0.58em;
      }

      .card.compact .back-button {
        min-height: 2.2em;
        padding: 0.38em 0.58em;
      }

      .card.compact .article-view h3 {
        font-size: 1.05em;
      }

      .card.compact .lead,
      .card.compact .article-body p {
        font-size: 0.86em;
        line-height: 1.38;
      }

      @keyframes spin {
        from {
          transform: rotate(0deg);
        }
        to {
          transform: rotate(360deg);
        }
      }

      @container (max-width: 360px) {
        .article-button {
          padding: 0.72em;
        }
      }
    `;
  }
}

function normalizeProviders(value) {
  if (!Array.isArray(value) || value.length === 0) {
    return [...DEFAULT_CONFIG.providers];
  }

  const providers = value.filter((provider) => provider in PROVIDERS);
  return providers.length ? [...new Set(providers)] : [...DEFAULT_CONFIG.providers];
}

function normalizeBoolean(value, fallback) {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    return value.toLowerCase() === "true";
  }
  return fallback;
}

function normalizeThemeMode(value, key) {
  return BACKGROUND_OPTIONS.some((option) => option.value === value) ? value : DEFAULT_CONFIG[key];
}

function summaryText(article) {
  return [
    article.summary,
    article.description,
    article.excerpt,
    article.teaser,
    article.subtitle
  ].find((value) => typeof value === "string" && value.trim())?.trim() || "";
}

function timestamp(value) {
  const parsed = Date.parse(value || "");
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatTime(value) {
  const parsed = timestamp(value);
  if (!parsed) {
    return "";
  }
  return new Intl.DateTimeFormat("da-DK", {
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(parsed));
}

function formatRelative(value) {
  const parsed = timestamp(value);
  if (!parsed) {
    return "";
  }

  const minutes = Math.max(0, Math.round((Date.now() - parsed) / 60000));
  if (minutes < 1) {
    return "opdateret nu";
  }
  if (minutes < 60) {
    return `opdateret for ${minutes} min siden`;
  }

  const hours = Math.round(minutes / 60);
  return `opdateret for ${hours} t siden`;
}

function readableError(err) {
  if (typeof err === "string") {
    return err;
  }
  return err?.message || err?.body?.message || "Artiklen kunne ikke hentes.";
}

function providerFor(article) {
  return PROVIDERS[article.provider] || {
    name: article.provider_name || article.provider || "Nyhed",
    shortName: article.provider_name || article.provider || "Nyhed",
    accent: "#697386",
    logo: "fallback"
  };
}

function isBreakingArticle(article) {
  if (article.breaking === true || article.is_breaking === true) {
    return true;
  }

  const text = [
    article.title,
    article.summary,
    article.category,
    article.label,
    article.tag
  ].filter(Boolean).join(" ").toLowerCase();

  return text.includes("breaking") || text.includes("breaking news") || text.includes("lige nu");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

function clampNumber(value, min, max) {
  if (!Number.isFinite(value)) {
    return min;
  }
  return Math.min(Math.max(value, min), max);
}

if (!customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, DanishNewsCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_TAG,
  name: "Danske nyheder",
  description: "Dagens danske nyheder med logoer, breaking-markering og intern artikelvisning.",
  preview: true
});

console.info(
  `%c ${CARD_TAG} %c v${CARD_VERSION} `,
  "color: white; background: #2f6f73; font-weight: 700;",
  "color: #2f6f73; background: transparent; font-weight: 700;"
);
