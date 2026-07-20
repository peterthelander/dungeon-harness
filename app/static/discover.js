let discoveryRequest;

function buildDiscoveryView() {
    const discovery = document.createElement('div');
    discovery.className = 'adventure-catalog discovery';
    discovery.innerHTML = `
        <button class="catalog-back" type="button">← Back</button>
        <p class="welcome__eyebrow">Live web discovery</p>
        <h1>Find an adventure</h1>
        <p class="catalog-intro">Fresh, freely published adventure PDFs from around the web. These results have not been play-tested by Dungeon Harness.</p>
        <div class="discovery__status" role="status"><span></span>Searching for open adventures…</div>
        <div class="discovery__attribution" hidden></div>
        <div class="adventure-grid discovery__grid" hidden></div>
        <button class="discovery__retry" type="button" hidden>Search again</button>
    `;
    discovery.querySelector('.catalog-back').addEventListener('click', () => showWelcome());
    discovery.querySelector('.discovery__retry').addEventListener('click', () => loadDiscoveryResults(discovery, true));
    loadDiscoveryResults(discovery);
    return discovery;
}

async function loadDiscoveryResults(discovery, refresh = false) {
    const status = discovery.querySelector('.discovery__status');
    const grid = discovery.querySelector('.discovery__grid');
    const retry = discovery.querySelector('.discovery__retry');
    status.hidden = false;
    status.innerHTML = '<span></span>Searching for open adventures…';
    grid.hidden = true;
    retry.hidden = true;
    if (refresh) discoveryRequest = null;
    discoveryRequest ||= fetch('/discover-adventures').then(async (response) => ({
        ok: response.ok,
        data: await response.json(),
    })).catch(() => ({ ok: false, data: {} }));
    const { ok, data } = await discoveryRequest;
    if (!discovery.isConnected) return;
    if (!ok || !Array.isArray(data.adventures) || !data.adventures.length) {
        status.textContent = data.error || 'Adventure discovery is temporarily unavailable.';
        retry.hidden = false;
        return;
    }
    grid.replaceChildren(...data.adventures.slice(0, 10).map(buildDiscoveryCard));
    const attribution = discovery.querySelector('.discovery__attribution');
    if (typeof data.google_search_html === 'string' && data.google_search_html) {
        attribution.innerHTML = data.google_search_html;
        attribution.hidden = false;
    }
    status.hidden = true;
    grid.hidden = false;
}

function buildDiscoveryCard(adventure, index) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'adventure-card discovery-card';
    const number = String(index + 1).padStart(2, '0');
    button.innerHTML = `
        <span class="adventure-card__number">${number}</span>
        <span class="adventure-card__body">
            <strong></strong><span class="adventure-card__author"></span>
            <span class="adventure-card__description"></span><span class="adventure-card__details"></span>
        </span><span class="adventure-card__arrow">→</span>
    `;
    button.querySelector('strong').textContent = adventure.title;
    button.querySelector('.adventure-card__author').textContent = adventure.source;
    button.querySelector('.adventure-card__description').textContent = adventure.description;
    button.querySelector('.adventure-card__details').textContent = adventure.details;
    button.addEventListener('click', async () => {
        if (actionInProgress) return;
        actionInProgress = true;
        button.classList.add('adventure-card--loading');
        button.querySelector('.adventure-card__arrow').textContent = 'Preparing…';
        mountGameScene();
        try { await loadUrl(adventure.url); } finally { actionInProgress = false; }
    });
    return button;
}
