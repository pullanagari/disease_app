// script.js
// Simple tab switching functionality
document.querySelectorAll('.nav-tabs li').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.nav-tabs li').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
    });
});
