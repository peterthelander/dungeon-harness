let actionInProgress = false;
let nextSceneBlockId = 1;
let uploadRequestedFromChat = false;

/**
 * @typedef {Object} ScenePageData
 * @property {string=} title
 * @property {string=} heroImageUrl
 * @property {string} narrative
 * @property {Array<Object>=} blocks
 */

const scenePageData = {
    title: undefined,
    heroImageUrl: undefined,
    narrative: '',
    blocks: []
};

const PRESET_MODULES = [
    { label: 'The Sky Blind Spire', author: 'Michael Prescott', url: 'https://trilemma.com/blog/adventures/24%20Sky-Blind%20Spire.pdf' },
    { label: 'Tomb of the Serpent Kings', author: 'Skerples', url: 'https://friendorfoe.com/d/Tomb%20of%20the%20Serpent_Kings%20v4.pdf' },
    { label: 'Moby Dick', author: 'Herman Melville', url: 'https://uberty.org/wp-content/uploads/2015/12/herman-melville-moby-dick.pdf' },
    { label: 'Dracula', author: 'Bram Stoker', url: 'https://www.bramstoker.org/pdf/novels/05dracula.pdf' }
];

function normalizeActionLabel(label) {
    return label.trim().toLowerCase();
}

function findPresetModule(label) {
    const normalizedLabel = normalizeActionLabel(label);
    return PRESET_MODULES.find((module) => normalizeActionLabel(module.label) === normalizedLabel);
}

function buildModuleLobbyText() {
    const moduleChoices = PRESET_MODULES
        .map((module) => `**${module.label}** by ${module.author}`)
        .join('\n');
    return `Welcome to Dungeon Harness. Choose an adventure module, or bring your own PDF.\n\n${moduleChoices}\n**Upload a PDF**`;
}

function resetScenePage() {
    scenePageData.title = undefined;
    scenePageData.heroImageUrl = undefined;
    scenePageData.narrative = '';
    scenePageData.blocks = [];
}

function syncNarrativeFromBlocks() {
    scenePageData.narrative = scenePageData.blocks
        .filter((block) => block.type === 'message')
        .map((block) => block.markdown || '')
        .join('\n\n');
}

function deactivateInlineActions() {
    document.querySelectorAll('.inline-action').forEach((button) => {
        button.classList.add('inline-action--inactive');
        button.disabled = true;
        button.setAttribute('aria-disabled', 'true');
    });
}


function isActionableBoldLabel(label) {
    if (!label || label.length > 100) return false;
    if (/^[A-Za-z][A-Za-z ]+:$/.test(label)) return false;
    if (/^[A-Za-z][A-Za-z ]+:\s*[-+]?\d+$/.test(label)) return false;
    return true;
}

function activateBoldActions(messageElement) {
    messageElement.querySelectorAll('strong').forEach((strong) => {
        if (strong.closest('a, button')) return;
        const label = strong.textContent.trim();
        if (!isActionableBoldLabel(label)) return;

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'inline-action';
        button.textContent = label;
        button.setAttribute('aria-label', `Choose ${label}`);
        button.addEventListener('click', () => {
            if (!actionInProgress) handleInlineAction(label);
        });
        strong.replaceWith(button);
    });
}

function handleInlineAction(label) {
    if (handleDeterministicAction(label)) return;
    sendAction(label);
}

function handleDeterministicAction(label) {
    const normalizedLabel = normalizeActionLabel(label);
    if (normalizedLabel === 'upload a pdf') {
        triggerUploadFromChat();
        return true;
    }
    if (normalizedLabel === 'restart this module') {
        restartCurrentModule();
        return true;
    }

    const presetModule = findPresetModule(label);
    if (presetModule) {
        loadPresetModuleFromChat(presetModule);
        return true;
    }

    return false;
}

const ScenePage = (() => {
    let rootElement;
    let contentElement;
    let inputField;
    let sendButton;

    function init(root, { onSubmit }) {
        rootElement = root;
        rootElement.classList.add('scene-page-scroll');
        rootElement.innerHTML = '';

        const page = document.createElement('section');
        page.className = 'scene-page';

        contentElement = document.createElement('div');
        contentElement.className = 'scene-page__main';

        const inputFooter = document.createElement('form');
        inputFooter.id = 'input-footer';
        inputFooter.className = 'scene-page__input';
        inputFooter.addEventListener('submit', (event) => {
            event.preventDefault();
            onSubmit();
        });

        inputField = document.createElement('input');
        inputField.type = 'text';
        inputField.id = 'action-input';
        inputField.setAttribute('aria-label', 'Custom action');
        inputField.placeholder = 'Other...';
        inputField.autocomplete = 'off';

        sendButton = document.createElement('button');
        sendButton.id = 'send-action-btn';
        sendButton.type = 'submit';
        sendButton.setAttribute('aria-label', 'Send action');
        sendButton.title = 'Send action';
        sendButton.textContent = '↑';

        inputFooter.append(inputField, sendButton);
        page.append(contentElement, inputFooter);
        rootElement.append(page);
    }

    function render(data, options = {}) {
        if (!contentElement) return;
        const shouldStickToTop = options.stickToTop === true;
        contentElement.replaceChildren(renderScene(data));
        if (shouldStickToTop && rootElement) {
            rootElement.scrollTop = 0;
        }
    }

    function renderScene(data) {
        const fragment = document.createDocumentFragment();

        if (data.title) {
            const title = document.createElement('h1');
            title.className = 'scene-page__title';
            title.textContent = data.title;
            fragment.append(title);
        }

        const layout = document.createElement('div');
        layout.className = data.heroImageUrl
            ? 'scene-page__layout scene-page__layout--with-hero'
            : 'scene-page__layout';

        const content = document.createElement('div');
        content.className = 'scene-page__content';
        const blocks = Array.isArray(data.blocks) && data.blocks.length
            ? data.blocks
            : [{ type: 'message', role: 'dm', markdown: data.narrative || '' }];
        blocks.forEach((block) => content.append(renderBlock(block)));
        layout.append(content);

        if (data.heroImageUrl) {
            layout.append(renderHeroImage(data.heroImageUrl));
        }
        fragment.append(layout);
        return fragment;
    }

    function renderHeroImage(url) {
        const figure = document.createElement('figure');
        figure.className = 'scene-page__hero';
        const image = document.createElement('img');
        image.src = url;
        image.alt = 'Scene visualization';
        figure.append(image);
        return figure;
    }

    function renderBlock(block) {
        if (block.type === 'system') {
            return renderSystemBlock(block);
        }
        if (block.type === 'message') {
            return renderMessageBlock(block);
        }
        return renderUnknownBlock(block);
    }

    function renderMessageBlock(block) {
        const article = document.createElement('article');
        article.classList.add('message', block.role === 'player' ? 'player' : 'dm');
        article.dataset.sceneBlockId = block.id;
        article.innerHTML = DOMPurify.sanitize(marked.parse(block.markdown || ''));
        if (block.role === 'dm' && !block.markdown) {
            article.hidden = true;
        }
        if (block.role === 'dm') {
            activateBoldActions(article);
        }
        return article;
    }

    function renderSystemBlock(block) {
        const aside = document.createElement('aside');
        aside.className = 'message system';
        aside.dataset.sceneBlockId = block.id;
        aside.innerHTML = DOMPurify.sanitize(marked.parse(block.markdown || ''));
        return aside;
    }

    function renderUnknownBlock(block) {
        const div = document.createElement('div');
        div.className = 'scene-page__block';
        div.dataset.sceneBlockId = block.id;
        div.textContent = block.text || '';
        return div;
    }

    function setBusy(isBusy, statusText) {
        if (!inputField || !sendButton) return;
        inputField.disabled = isBusy;
        sendButton.disabled = isBusy;
        sendButton.textContent = isBusy ? '…' : '↑';
        sendButton.setAttribute('aria-label', statusText || (isBusy ? 'DM thinking' : 'Send action'));
        sendButton.title = statusText || 'Send action';
        if (isBusy) {
            sendButton.setAttribute('aria-busy', 'true');
        } else {
            sendButton.removeAttribute('aria-busy');
        }
    }

    function getInputValue() {
        return inputField ? inputField.value : '';
    }

    function clearInput() {
        if (inputField) inputField.value = '';
    }

    function focusInput() {
        if (inputField) inputField.focus();
    }

    function blurInput() {
        if (inputField) inputField.blur();
    }

    return { init, render, setBusy, getInputValue, clearInput, focusInput, blurInput };
})();

function addSceneBlock(type, values) {
    const block = { id: String(nextSceneBlockId++), type, ...values };
    scenePageData.blocks.push(block);
    syncNarrativeFromBlocks();
    ScenePage.render(scenePageData);
    return block;
}

function updateSceneBlock(block, values) {
    Object.assign(block, values);
    syncNarrativeFromBlocks();
    ScenePage.render(scenePageData);
}

function appendMessage(text, role) {
    return addSceneBlock('message', {
        role,
        markdown: text
    });
}

function appendSystemMessage(text) {
    return addSceneBlock('system', { markdown: text });
}

function setHeroImage(imageData) {
    scenePageData.heroImageUrl = imageData || undefined;
    ScenePage.render(scenePageData);
}

async function initializeScenePage() {
    const root = document.getElementById('scene-page-root');
    ScenePage.init(root, { onSubmit: () => sendAction() });
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

                const overlay = document.getElementById('upload-overlay');
                overlay.style.display = 'none';
                document.getElementById('dashboard').style.display = 'flex';
                ScenePage.render(scenePageData, { stickToTop: true });
                ScenePage.focusInput();
                return;
            }
        }
    } catch (err) {
        console.error('Failed to fetch session state:', err);
    }

    resetScenePage();
    appendMessage(buildModuleLobbyText(), 'dm');
    const overlay = document.getElementById('upload-overlay');
    if (overlay) overlay.style.display = 'none';
    document.getElementById('dashboard').style.display = 'flex';
    ScenePage.render(scenePageData, { stickToTop: true });
    ScenePage.focusInput();
}



// Start Initialization Request to the Backend
async function initializeEngine(options = {}) {
    const fileInput = document.getElementById('pdf-upload');
    const file = fileInput.files[0];
    const btn = document.getElementById('init-engine-btn');
    const loadText = document.getElementById('loading-text');

    if (!file) {
        if (!options.fromChat) {
            alert('Please select a PDF module first.');
        }
        return false;
    }

    setInitializationBusy(true, 'Preparing...');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const ok = response.ok;
        await handleInitializationResponse(response);
        return ok;
    } catch (err) {
        console.error(err);
        alert('Could not connect to the engine.');
        resetInitUI();
        return false;
    }
}

async function loadUrl(url) {
    setInitializationBusy(true, 'Downloading & Preparing...');

    try {
        const response = await fetch('/load_url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        });

        const ok = response.ok;
        await handleInitializationResponse(response);
        return ok;
    } catch (err) {
        console.error(err);
        alert('Could not connect to the engine.');
        resetInitUI();
    }
}

async function loadPresetModuleFromChat(presetModule) {
    if (actionInProgress) return;

    actionInProgress = true;
    appendMessage(presetModule.label, 'player');
    appendSystemMessage(`Preparing ${presetModule.label}. This can take a minute while the module is loaded.`);
    deactivateInlineActions();
    ScenePage.setBusy(true, 'Preparing your adventure');

    try {
        await loadUrl(presetModule.url);
    } finally {
        actionInProgress = false;
        ScenePage.setBusy(false, 'Send action');
        ScenePage.focusInput();
    }
}

async function handleInitializationResponse(response) {
    const data = await response.json();

    if (response.ok) {
        resetScenePage();
        scenePageData.heroImageUrl = data.image_data || undefined;

        if (data.dm_text) {
            appendMessage(data.dm_text, 'dm');
        } else {
            ScenePage.render(scenePageData);
        }

        const overlay = document.getElementById('upload-overlay');
        if (overlay) overlay.style.display = 'none';
        document.getElementById('dashboard').style.display = 'flex';
        ScenePage.render(scenePageData, { stickToTop: true });
        ScenePage.focusInput();
    } else {
        alert('Initialization error: ' + data.error);
        resetInitUI();
    }
}

function setInitializationBusy(isBusy, label) {
    const btn = document.getElementById('init-engine-btn');
    const loadText = document.getElementById('loading-text');
    if (btn) {
        btn.disabled = isBusy;
        btn.innerText = isBusy ? label : 'Begin Quest';
    }
    if (loadText) {
        loadText.style.display = isBusy ? 'block' : 'none';
    }
}

function resetInitUI() {
    setInitializationBusy(false);
}

function triggerUploadFromChat() {
    const fileInput = document.getElementById('pdf-upload');
    if (!fileInput) {
        appendSystemMessage('Upload is unavailable right now.');
        return;
    }
    uploadRequestedFromChat = true;
    fileInput.value = '';
    fileInput.click();
}

async function handlePdfUploadSelection() {
    if (!uploadRequestedFromChat) return;
    uploadRequestedFromChat = false;

    const fileInput = document.getElementById('pdf-upload');
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) return;
    if (actionInProgress) return;

    actionInProgress = true;
    appendMessage('Upload a PDF', 'player');
    appendSystemMessage('Preparing your uploaded PDF. This can take a minute while the module is uploaded and read.');
    deactivateInlineActions();
    ScenePage.setBusy(true, 'Preparing your adventure');

    try {
        await initializeEngine({ fromChat: true });
    } finally {
        actionInProgress = false;
        ScenePage.setBusy(false, 'Send action');
        ScenePage.focusInput();
    }
}

function setupPdfUploadInput() {
    const fileInput = document.getElementById('pdf-upload');
    if (fileInput) {
        fileInput.addEventListener('change', handlePdfUploadSelection);
    }
}

async function restartCurrentModule() {
    if (actionInProgress) return;

    actionInProgress = true;
    appendMessage('Restart this module', 'player');
    deactivateInlineActions();
    ScenePage.setBusy(true, 'Restarting adventure');

    try {
        const response = await fetch('/restart', { method: 'POST' });
        if (response.ok) {
            await handleInitializationResponse(response);
            return;
        }

        const data = await response.json();
        appendSystemMessage(data.error || 'Restart is unavailable right now.');
    } catch (err) {
        console.error(err);
        appendSystemMessage('Could not restart the adventure.');
    } finally {
        actionInProgress = false;
        ScenePage.setBusy(false, 'Send action');
        ScenePage.focusInput();
    }
}

function handleKeyPress(e) {
    if (e.key === 'Enter') {
        sendAction();
    }
}

async function sendAction(suggestedText = null) {
    const text = (suggestedText || ScenePage.getInputValue()).trim();

    if (!text || actionInProgress) return;
    if (handleDeterministicAction(text)) {
        ScenePage.clearInput();
        return;
    }
    actionInProgress = true;

    appendMessage(text, 'player');
    ScenePage.clearInput();
    ScenePage.setBusy(true, 'DM thinking');
    deactivateInlineActions();
    const dmMessages = new Map();
    const dmText = new Map();
    let freshSceneStarted = false;

    function startFreshScene() {
        if (freshSceneStarted) return;
        const currentHeroImageUrl = scenePageData.heroImageUrl;
        freshSceneStarted = true;
        resetScenePage();
        scenePageData.heroImageUrl = currentHeroImageUrl;
        ScenePage.render(scenePageData, { stickToTop: true });
        dmMessages.clear();
        dmText.clear();
    }

    function getDmMessage(messageId) {
        if (!dmMessages.has(messageId)) {
            const message = addSceneBlock('message', {
                role: 'dm',
                markdown: ''
            });
            dmMessages.set(messageId, message);
            dmText.set(messageId, '');
        }
        return dmMessages.get(messageId);
    }

    let msgBlock = getDmMessage(0);

    try {
        const response = await fetch('/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });

        if (!response.ok) {
            const data = await response.json();
            updateSceneBlock(msgBlock, { markdown: 'ERROR: ' + data.error });
        } else {
            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (!line.trim()) continue;
                    const data = JSON.parse(line);

                    if (data.type === 'text_chunk') {
                        startFreshScene();
                        const messageId = data.message_id ?? 0;
                        msgBlock = getDmMessage(messageId);
                        const fullText = (dmText.get(messageId) || '') + data.text;
                        dmText.set(messageId, fullText);
                        updateSceneBlock(msgBlock, { markdown: fullText });
                    } else if (data.type === 'tool_call') {
                        startFreshScene();
                        appendSystemMessage(data.message);
                    } else if (data.type === 'status') {
                        ScenePage.setBusy(true, data.message);
                    } else if (data.type === 'image') {
                        startFreshScene();
                        setHeroImage(data.image_data);
                    } else if (data.type === 'error') {
                        startFreshScene();
                        msgBlock = getDmMessage(0);
                        updateSceneBlock(msgBlock, {
                            markdown: `${msgBlock.markdown || ''}\n\nERROR: ${data.error}`
                        });
                    } else if (data.type === 'done') {
                        break;
                    }
                }
            }
        }
    } catch (err) {
        console.error(err);
        startFreshScene();
        msgBlock = getDmMessage(0);
        updateSceneBlock(msgBlock, { markdown: 'CRITICAL: Failed to communicate with engine backend.' });
    } finally {
        ScenePage.setBusy(false, 'Send action');
        actionInProgress = false;
        ScenePage.focusInput();
    }
}

function toggleAppMenu(event) {
    if (event) event.stopPropagation();
    const dropdown = document.getElementById('app-menu-dropdown');
    if (!dropdown) return;
    const isVisible = dropdown.style.display === 'block';
    dropdown.style.display = isVisible ? 'none' : 'block';
}

function closeAppMenu() {
    const dropdown = document.getElementById('app-menu-dropdown');
    if (dropdown) dropdown.style.display = 'none';
}

function submitPromptMenuItem(text) {
    closeAppMenu();
    sendAction(text);
}

document.addEventListener('click', (event) => {
    const container = document.querySelector('.app-header__menu-container');
    if (container && !container.contains(event.target)) {
        closeAppMenu();
    }
});

document.addEventListener('DOMContentLoaded', () => {
    setupPdfUploadInput();
    initializeScenePage();
});
