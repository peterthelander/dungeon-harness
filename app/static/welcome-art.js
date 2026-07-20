let welcomeArtworkRequest;

async function requestWelcomeArtwork() {
    const threshold = document.querySelector('.welcome--threshold');
    if (!threshold) return;

    threshold.classList.add('welcome--art-loading');
    welcomeArtworkRequest ||= fetch('/welcome-image')
        .then((response) => response.ok ? response.json() : null)
        .catch((error) => {
            console.warn('Welcome artwork could not be generated:', error);
            return null;
        });

    const data = await welcomeArtworkRequest;
    if (!threshold.isConnected) return;
    threshold.classList.remove('welcome--art-loading');
    if (!data?.image_data) return;
    threshold.style.setProperty('--generated-welcome-art', `url("${data.image_data}")`);
    threshold.classList.add('welcome--art-ready');
}
