const STORAGE_KEY = 'we_theme';

async function applyTheme(themeName) {
    const response = await fetch(`/theme.css?t=${Date.now()}`);
    if (!response.ok) return;
    const css = await response.text();
    let styleEl = document.getElementById('theme-override');
    if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = 'theme-override';
        document.head.appendChild(styleEl);
    }
    styleEl.textContent = css;
}

function updateLogo(themeList, themeName) {
    const theme = themeList.find(t => t.name === themeName);
    if (!theme) return;
    const logoImg = document.querySelector('.header-logo');
    if (logoImg) logoImg.src = theme.explorer_logo;
}

async function switchTheme(themeName, dropdownItems, themeList) {
    const response = await fetch(`/api/explorer/theme/${themeName}`, { method: 'POST' });
    if (!response.ok) return;
    localStorage.setItem(STORAGE_KEY, themeName);
    await applyTheme(themeName);
    updateLogo(themeList, themeName);
    dropdownItems.forEach(li => {
        li.setAttribute('aria-current', li.dataset.name === themeName ? 'true' : 'false');
    });
}

export async function initThemeSwitcher() {
    const btn      = document.getElementById('theme-btn');
    const dropdown = document.getElementById('theme-dropdown');
    if (!btn || !dropdown) return;

    const response = await fetch('/api/explorer/themes');
    if (!response.ok) return;
    const { themes, active } = await response.json();

    const savedTheme = localStorage.getItem(STORAGE_KEY);

    dropdown.innerHTML = '';
    themes.forEach(({ name, display_name }) => {
        const li = document.createElement('li');
        li.textContent = display_name;
        li.dataset.name = name;
        li.setAttribute('aria-current', name === (savedTheme || active) ? 'true' : 'false');
        dropdown.appendChild(li);
    });

    const dropdownItems = Array.from(dropdown.querySelectorAll('li'));

    dropdownItems.forEach(li => {
        li.addEventListener('click', () => {
            switchTheme(li.dataset.name, dropdownItems, themes);
            dropdown.hidden = true;
        });
    });

    btn.addEventListener('click', (event) => {
        event.stopPropagation();
        dropdown.hidden = !dropdown.hidden;
    });

    document.addEventListener('click', () => { dropdown.hidden = true; });

    if (savedTheme && savedTheme !== active) {
        await switchTheme(savedTheme, dropdownItems, themes);
    }
}
