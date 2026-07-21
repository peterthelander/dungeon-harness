function showWelcome() {
    const root = document.getElementById('scene-page-root');
    root.className = 'welcome-shell';
    root.replaceChildren();
    const screen = document.createElement('section');
    screen.className = 'welcome welcome--threshold';

    const content = document.createElement('div');
    content.className = 'welcome__content';
    content.innerHTML = '<p class="welcome__eyebrow">Dungeon Harness</p><h1>Step into the story.</h1><p class="welcome__lede">An AI game master brings an adventure to life. Choose a hand-picked quest below, or bring your own.</p>';
    
    content.append(buildModuleGrid('adventure'));

    const actions = document.createElement('div');
    actions.className = 'welcome__actions';
    actions.append(
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
    root.append(screen);
    requestWelcomeArtwork();
    document.getElementById('dashboard').style.display = 'flex';
}
