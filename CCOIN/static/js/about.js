document.addEventListener('DOMContentLoaded', function() {
    // دکمه ضربدر - بازگشت به صفحه هوم
    const closeBtn = document.getElementById('close-settings');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            // دریافت telegram_id از URL parameter یا session
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
    
    // دکمه لینک - فعلاً به صفحه هوم می‌رود
    const linkBtn = document.getElementById('website-link');
    if (linkBtn) {
        linkBtn.addEventListener('click', function() {
            // دریافت telegram_id از URL parameter یا session
            const urlParams = new URLSearchParams(window.location.search);
            const telegramId = urlParams.get('telegram_id') || 
                              (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initDataUnsafe && window.Telegram.WebApp.initDataUnsafe.user && window.Telegram.WebApp.initDataUnsafe.user.id);
            
            if (telegramId) {
                window.location.href = `/home?telegram_id=${telegramId}`;
            } else {
                window.location.href = '/';
            }
            
            // TODO: در آینده این لینک را به سایت اصلی CCoin تغییر دهید
            // window.open('https://ccoin-website.com', '_blank');
        });
    }
    
    // اضافه کردن haptic feedback برای تلگرام
    if (window.Telegram && window.Telegram.WebApp) {
        closeBtn?.addEventListener('click', function() {
            window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
        });
        
        linkBtn?.addEventListener('click', function() {
            window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
        });
    }
});

// اضافه کردن keyboard navigation
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        document.getElementById('close-settings')?.click();
    }
});
