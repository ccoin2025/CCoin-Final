document.addEventListener('DOMContentLoaded', function() {
    const closeBtn = document.getElementById('close-settings');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            const urlParams = new URLSearchParams(window.location.search);
            const telegramId = urlParams.get('telegram_id') || 
                              (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initDataUnsafe && window.Telegram.WebApp.initDataUnsafe.user && window.Telegram.WebApp.initDataUnsafe.user.id);
            
            if (telegramId) {
                window.location.href = `/home?telegram_id=${telegramId}`;
            } else {
                window.location.href = '/';
            }
        });
    }
    
    const linkBtn = document.getElementById('website-link');
    if (linkBtn) {
        linkBtn.addEventListener('click', function() {
            const urlParams = new URLSearchParams(window.location.search);
            const telegramId = urlParams.get('telegram_id') || 
                              (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initDataUnsafe && window.Telegram.WebApp.initDataUnsafe.user && window.Telegram.WebApp.initDataUnsafe.user.id);
            
            if (telegramId) {
                window.location.href = `/home?telegram_id=${telegramId}`;
            } else {
                window.location.href = '/';
            }
        });
    }
    
    if (window.Telegram && window.Telegram.WebApp) {
        closeBtn?.addEventListener('click', function() {
            window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
        });
        
        linkBtn?.addEventListener('click', function() {
            window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
        });
    }
});

document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        document.getElementById('close-settings')?.click();
    }
});
