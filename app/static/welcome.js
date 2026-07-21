const WELCOME_MODULE_DETAILS = {
    'The Sky Blind Spire': { kind: 'adventure', description: 'Climb an impossible tower where gravity and architecture have both gone astray.', details: 'Short · Exploration · Surreal fantasy' },
    'Tomb of the Serpent Kings': { kind: 'adventure', description: 'Delve into a forgotten tomb built to teach brave newcomers how dungeons think.', details: 'Medium · Traps & discovery · Dark fantasy' },
    'The Keep on the Borderlands': { kind: 'adventure', description: 'A classic starting adventure set in a fortress on the edge of the wilderness, near the chaotic Caves of Chaos.', details: 'Classic · Megadungeon · Epic fantasy' },
    'Palace of the Silver Princess': { kind: 'adventure', description: 'A princess\'s palace is locked in time by a mysterious ruby, waiting to be freed.', details: 'Classic · Rescue · High fantasy' },
    'The Lost City': { kind: 'adventure', description: 'Lost in the desert, discover a buried step pyramid where strange factions dwell.', details: 'Classic · Desert sandbox · Weird fantasy' },
    'The Crypt of Terror': { kind: 'adventure', description: 'A journey into an ancient crypt filled with undead and forgotten evils.', details: 'Classic · Dungeon crawl · Dark fantasy' }
};

function mountGameScene() {
    const root = document.getElementById('scene-page-root');
    root.className = '';
    ScenePage.init(root, { onSubmit: () => sendAction() });
}

function resumeCurrentAdventure() {
    mountGameScene();
    ScenePage.render(scenePageData, { stickToTop: true });
    ScenePage.focusInput();
}

function openNewAdventureFlow() {
    closeAppMenu();
    showWelcome();
}

function welcomeAction(label, description, className, onClick) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.innerHTML = `<span>${label}</span><small>${description}</small>`;
    button.addEventListener('click', onClick);
    return button;
}

function showWelcome(view = 'threshold') {
    const root = document.getElementById('scene-page-root');
    root.className = 'welcome-shell';
    root.replaceChildren();
    const screen = document.createElement('section');
    screen.className = `welcome welcome--${view}`;

    if (view === 'catalog') {
        screen.append(buildAdventureCatalog());
    } else {
        const content = document.createElement('div');
        content.className = 'welcome__content';
        content.innerHTML = '<p class="welcome__eyebrow">Dungeon Harness</p><h1>Step into the story.</h1><p class="welcome__lede">An AI game master brings an adventure to life. Explore dangerous places, meet their inhabitants, and decide what your character does next.</p>';
        const actions = document.createElement('div');
        actions.className = 'welcome__actions';
        actions.append(
            welcomeAction('Play a starter adventure', 'Choose a hand-picked quest and begin immediately.', 'welcome-action welcome-action--primary', () => showWelcome('catalog')),
            welcomeAction('Bring your own adventure', 'Upload a tabletop adventure PDF and enter its world.', 'welcome-action', triggerUploadFromChat)
        );
        content.append(actions);
        if (scenePageData.blocks.length) {
            const resume = document.createElement('button');
            resume.type = 'button';
            resume.className = 'welcome__resume';
            resume.textContent = '← Return to current adventure';
            resume.addEventListener('click', resumeCurrentAdventure);
            content.append(resume);
        }
        content.insertAdjacentHTML('beforeend', '<p class="welcome__note">No group or preparation required.</p>');
        screen.append(content);
    }
    root.append(screen);
    if (view === 'threshold') requestWelcomeArtwork();
    document.getElementById('dashboard').style.display = 'flex';
}

function buildAdventureCatalog() {
    const catalog = document.createElement('div');
    catalog.className = 'adventure-catalog';
    catalog.innerHTML = '<button class="catalog-back" type="button">← Back</button><p class="welcome__eyebrow">Choose your first world</p><h1>Starter adventures</h1><p class="catalog-intro">Begin with a tabletop adventure selected for exploration and discovery.</p>';
    catalog.querySelector('.catalog-back').addEventListener('click', () => showWelcome());
    catalog.append(buildModuleGrid('adventure'));

    const upload = document.createElement('button');
    upload.type = 'button';
    upload.className = 'catalog-upload';
    upload.textContent = 'Or bring your own adventure PDF →';
    upload.addEventListener('click', triggerUploadFromChat);
    catalog.append(upload);
    return catalog;
}

function buildModuleGrid(kind) {
    const grid = document.createElement('div');
    grid.className = 'adventure-grid';
    PRESET_MODULES.filter((module) => WELCOME_MODULE_DETAILS[module.label].kind === kind).forEach((module, index) => {
        const detail = WELCOME_MODULE_DETAILS[module.label];
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'adventure-card';
        button.innerHTML = `<span class="adventure-card__number">0${index + 1}</span><span class="adventure-card__body"><strong>${module.label}</strong><span class="adventure-card__author">by ${module.author}</span><span class="adventure-card__description">${detail.description}</span><span class="adventure-card__details">${detail.details}</span></span><span class="adventure-card__arrow">→</span>`;
        button.addEventListener('click', async () => {
            if (actionInProgress) return;
            actionInProgress = true;
            document.querySelectorAll('.adventure-card, .catalog-upload, .catalog-back').forEach((element) => { element.disabled = true; });
            button.classList.add('adventure-card--loading');
            button.querySelector('.adventure-card__arrow').textContent = 'Preparing…';
            mountGameScene();
            try { await loadUrl(module.url); } finally { actionInProgress = false; }
        });
        grid.append(button);
    });
    return grid;
}

async function initializeWelcome() {
    mountGameScene();
    ScenePage.render(scenePageData, { stickToTop: true });
    try {
        const response = await fetch('/session');
        if (response.ok) {
            const data = await response.json();
            if (data.initialized) {
                resetScenePage();
                scenePageData.heroImageUrl = data.hero_image_url || undefined;
                scenePageData.blocks = data.blocks || [];
                syncNarrativeFromBlocks();
                document.getElementById('upload-overlay').style.display = 'none';
                document.getElementById('dashboard').style.display = 'flex';
                ScenePage.render(scenePageData, { stickToTop: true });
                ScenePage.focusInput();
                return;
            }
        }
    } catch (err) {
        console.error('Failed to fetch session state:', err);
    }
    document.getElementById('upload-overlay').style.display = 'none';
    showWelcome();
}

document.getElementById('pdf-upload').addEventListener('change', () => {
    if (uploadRequestedFromChat) mountGameScene();
}, { capture: true });
