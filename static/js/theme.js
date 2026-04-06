document.addEventListener('DOMContentLoaded', function () {
    const htmlElement = document.documentElement;
    const btnToggle = document.getElementById('btnToggleTheme');
    const iconTheme = document.getElementById('iconTheme');
    const themeText = document.getElementById('themeText');
    const navbar = document.getElementById('mainNavbar');

    function updateUI(tema) {
        if (!btnToggle) return;
        if (tema === 'dark') {
            iconTheme.classList.replace('bi-moon-fill', 'bi-sun-fill');
            themeText.innerText = 'Claro';
            navbar.classList.replace('bg-primary', 'bg-dark');
            btnToggle.classList.replace('btn-outline-light', 'btn-outline-info');
        } else {
            iconTheme.classList.replace('bi-sun-fill', 'bi-moon-fill');
            themeText.innerText = 'Escuro';
            navbar.classList.replace('bg-dark', 'bg-primary');
            btnToggle.classList.replace('btn-outline-info', 'btn-outline-light');
        }
    }

    updateUI(htmlElement.getAttribute('data-bs-theme'));

    btnToggle.addEventListener('click', function () {
        const currentTheme = htmlElement.getAttribute('data-bs-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        htmlElement.setAttribute('data-bs-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateUI(newTheme);
    });
});