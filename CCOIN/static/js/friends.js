function checkOnlineStatus() {
    const userItems = document.querySelectorAll('.user-item');
    userItems.forEach(item => {
        const statusBadge = item.querySelector('.status-badge');
        if (statusBadge) {
            const isOnline = Math.random() > 0.5;
            statusBadge.textContent = isOnline ? 'Online' : 'Offline';
            statusBadge.className = `status-badge ${isOnline ? 'online' : 'offline'}`;
        }
    });
}

function refreshData() {
    console.log("Refreshing friends data...");
    location.reload();
}

function addButtonAnimations() {
    const buttons = document.querySelectorAll('.invite-btn, .share-btn, .copy-btn');
    buttons.forEach(button => {
        button.addEventListener('click', function() {
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = 'scale(1)';
            }, 100);
        });
    });
}

document.addEventListener('DOMContentLoaded', function() {
    addButtonAnimations();
    setInterval(checkOnlineStatus, 30000);
});

if (window.Telegram && window.Telegram.WebApp) {
    window.Telegram.WebApp.ready();
    
    window.Telegram.WebApp.BackButton.show();
    window.Telegram.WebApp.BackButton.onClick(() => {
        window.history.back();
    });
}
