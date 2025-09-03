console.log("Friends.js loaded - Simple version");

// متغیرهای global
let REFERRAL_CODE = null;
let REFERRAL_LINK = null;

// تابع دعوت دوست - بدون validation
function inviteFriend() {
    console.log("=== INVITE BUTTON CLICKED ===");
    console.log("REFERRAL_LINK:", REFERRAL_LINK);
    
    // فقط چک می‌کنیم که لینک خالی نباشد
    if (!REFERRAL_LINK) {
        console.error("REFERRAL_LINK is null/undefined");
        alert('لینک رفرال موجود نیست!');
        return;
    }

    console.log("Opening referral link:", REFERRAL_LINK);

    try {
        // تلاش اول: Telegram WebApp
        if (window.Telegram && window.Telegram.WebApp && typeof window.Telegram.WebApp.openLink === 'function') {
            console.log("Using Telegram WebApp.openLink");
            window.Telegram.WebApp.openLink(REFERRAL_LINK);
        } else {
            console.log("Using window.open");
            window.open(REFERRAL_LINK, '_blank');
        }
    } catch (error) {
        console.error("Error opening link:", error);
        // fallback
        try {
            window.open(REFERRAL_LINK, '_blank');
        } catch (fallbackError) {
            console.error("Fallback also failed:", fallbackError);
            alert('خطا در باز کردن لینک');
        }
    }
}

// تابع کپی لینک - بدون validation
function copyLink() {
    console.log("=== COPY BUTTON CLICKED ===");
    console.log("REFERRAL_LINK:", REFERRAL_LINK);
    
    // فقط چک می‌کنیم که لینک خالی نباشد
    if (!REFERRAL_LINK) {
        console.error("REFERRAL_LINK is null/undefined");
        alert('لینک رفرال موجود نیست!');
        return;
    }

    console.log("Copying referral link:", REFERRAL_LINK);

    // تلاش برای کپی
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(REFERRAL_LINK).then(() => {
            console.log("Link copied successfully");
            alert('لینک کپی شد!');
        }).catch((error) => {
            console.error("Clipboard API failed:", error);
            fallbackCopy();
        });
    } else {
        console.log("Clipboard API not available, using fallback");
        fallbackCopy();
    }
}

// تابع fallback برای کپی
function fallbackCopy() {
    try {
        const textArea = document.createElement('textarea');
        textArea.value = REFERRAL_LINK;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.select();
        
        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);
        
        if (successful) {
            console.log("Fallback copy successful");
            alert('لینک کپی شد!');
        } else {
            console.error("Fallback copy failed");
            alert('خطا در کپی کردن');
        }
    } catch (error) {
        console.error("Fallback copy error:", error);
        alert('خطا در کپی کردن');
    }
}

// وقتی DOM آماده شد
document.addEventListener('DOMContentLoaded', function() {
    console.log("=== DOM READY ===");
    
    // دریافت داده‌ها از body
    REFERRAL_CODE = document.body.getAttribute('data-referral-code');
    REFERRAL_LINK = document.body.getAttribute('data-referral-link');
    
    console.log("Retrieved REFERRAL_CODE:", REFERRAL_CODE);
    console.log("Retrieved REFERRAL_LINK:", REFERRAL_LINK);
    
    // پیدا کردن دکمه‌ها
    const inviteButton = document.getElementById('inviteButton');
    const copyButton = document.getElementById('copyButton');

    if (inviteButton) {
        console.log("Invite button found");
        inviteButton.onclick = inviteFriend;
    } else {
        console.error("Invite button NOT found!");
    }

    if (copyButton) {
        console.log("Copy button found");
        copyButton.onclick = copyLink;
    } else {
        console.error("Copy button NOT found!");
    }
    
    console.log("Setup completed");
});

// تابع‌های global
window.inviteFriend = inviteFriend;
window.copyLink = copyLink;
