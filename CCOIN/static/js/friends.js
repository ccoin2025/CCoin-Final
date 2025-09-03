console.log("Friends.js loaded");

// تعریف متغیرهای global از data attributes
let REFERRAL_CODE = null;
let REFERRAL_LINK = null;

// تابع validation اصلاح شده برای بررسی صحت لینک رفرال
function isValidReferralLink(link) {
    console.log("Validating referral link:", link);
    
    // بررسی اولیه - آیا لینک وجود دارد؟
    if (!link || link === "" || link === null || link === undefined) {
        console.log("Link is empty or null");
        return false;
    }
    
    // تبدیل به string برای اطمینان
    const linkStr = String(link).trim();
    
    // بررسی اینکه آیا لینک شامل telegram است
    if (!linkStr.includes("t.me/")) {
        console.log("Link doesn't contain t.me");
        return false;
    }
    
    // بررسی اینکه آیا لینک شامل start parameter است
    if (!linkStr.includes("?start=")) {
        console.log("Link doesn't contain start parameter");
        return false;
    }
    
    // استخراج کد رفرال از لینک
    const parts = linkStr.split("?start=");
    if (parts.length !== 2) {
        console.log("Link format is incorrect");
        return false;
    }
    
    const referralCode = parts[1];
    
    // بررسی اینکه کد رفرال خالی نباشد
    if (!referralCode || referralCode === "" || referralCode.trim() === "") {
        console.log("Referral code in link is empty");
        return false;
    }
    
    // بررسی اینکه کد رفرال حداقل 3 کاراختر باشد
    if (referralCode.length < 3) {
        console.log("Referral code is too short:", referralCode);
        return false;
    }
    
    console.log("Link validation passed, referral code:", referralCode);
    return true;
}

// تابع دعوت دوست
function inviteFriend() {
    console.log("=== INVITE FUNCTION CALLED ===");
    console.log("Current REFERRAL_LINK:", REFERRAL_LINK);
    console.log("Current REFERRAL_CODE:", REFERRAL_CODE);
    
    // بررسی validation
    if (!isValidReferralLink(REFERRAL_LINK)) {
        console.error("Validation failed for referral link");
        alert('خطا: لینک رفرال نامعتبر است!\nلینک: ' + (REFERRAL_LINK || 'موجود نیست'));
        return;
    }

    console.log("Referral link is valid, proceeding to open");

    // تلاش برای باز کردن لینک
    try {
        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.openLink) {
            console.log("Opening with Telegram WebApp.openLink");
            window.Telegram.WebApp.openLink(REFERRAL_LINK);
        } else if (window.Telegram && window.Telegram.WebApp) {
            console.log("Telegram WebApp available but openLink not found, using window.open");
            window.open(REFERRAL_LINK, '_blank');
        } else {
            console.log("Telegram WebApp not available, using window.open");
            window.open(REFERRAL_LINK, '_blank');
        }
    } catch (error) {
        console.error("Error opening referral link:", error);
        alert('خطا در باز کردن لینک رفرال');
    }
}

// تابع کپی لینک
function copyLink() {
    console.log("=== COPY FUNCTION CALLED ===");
    console.log("Current REFERRAL_LINK:", REFERRAL_LINK);
    
    // بررسی validation
    if (!isValidReferralLink(REFERRAL_LINK)) {
        console.error("Validation failed for referral link in copy function");
        alert('خطا: لینک رفرال نامعتبر است!\nلینک: ' + (REFERRAL_LINK || 'موجود نیست'));
        return;
    }

    console.log("Referral link is valid, proceeding to copy");

    // تلاش برای کپی کردن
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(REFERRAL_LINK).then(() => {
            alert('لینک با موفقیت کپی شد!');
            console.log("Link copied successfully using modern API");
        }).catch((error) => {
            console.error("Modern clipboard API failed:", error);
            fallbackCopyMethod();
        });
    } else {
        console.log("Modern clipboard API not available, using fallback");
        fallbackCopyMethod();
    }
}

// روش جایگزین برای کپی کردن
function fallbackCopyMethod() {
    try {
        const textArea = document.createElement('textarea');
        textArea.value = REFERRAL_LINK;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        textArea.style.top = '0';
        textArea.style.left = '0';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);
        
        if (successful) {
            alert('لینک با موفقیت کپی شد!');
            console.log("Link copied successfully using fallback method");
        } else {
            throw new Error("execCommand failed");
        }
    } catch (error) {
        console.error("Fallback copy method failed:", error);
        alert('خطا در کپی کردن لینک');
    }
}

// تابع اصلی که وقتی DOM آماده شد اجرا می‌شود
document.addEventListener('DOMContentLoaded', function() {
    console.log("=== DOM LOADED ===");
    
    // دریافت متغیرها از data attributes
    REFERRAL_CODE = document.body.getAttribute('data-referral-code');
    REFERRAL_LINK = document.body.getAttribute('data-referral-link');
    
    console.log("=== INITIAL DATA ===");
    console.log("REFERRAL_CODE from body:", REFERRAL_CODE);
    console.log("REFERRAL_LINK from body:", REFERRAL_LINK);
    console.log("REFERRAL_CODE type:", typeof REFERRAL_CODE);
    console.log("REFERRAL_LINK type:", typeof REFERRAL_LINK);
    
    // پیدا کردن دکمه‌ها
    const inviteButton = document.getElementById('inviteButton');
    const copyButton = document.getElementById('copyButton');

    if (inviteButton) {
        console.log("Invite button found, attaching event listener");
        inviteButton.addEventListener('click', inviteFriend);
        
        // اضافه کردن onclick برای backup
        inviteButton.onclick = inviteFriend;
    } else {
        console.error("Invite button NOT found!");
    }

    if (copyButton) {
        console.log("Copy button found, attaching event listener");
        copyButton.addEventListener('click', copyLink);
        
        // اضافه کردن onclick برای backup
        copyButton.onclick = copyLink;
    } else {
        console.error("Copy button NOT found!");
    }
    
    // بررسی اولیه صحت داده‌ها
    console.log("=== INITIAL VALIDATION ===");
    const isValid = isValidReferralLink(REFERRAL_LINK);
    console.log("Initial validation result:", isValid);
    
    if (!isValid) {
        console.warn("⚠️ Invalid referral link detected on page load");
        console.warn("This will cause issues with invite/copy functionality");
        console.warn("REFERRAL_LINK value:", REFERRAL_LINK);
    } else {
        console.log("✅ Referral link is valid on page load");
    }
});

// تابع‌های global برای استفاده در صورت نیاز
window.inviteFriend = inviteFriend;
window.copyLink = copyLink;
window.isValidReferralLink = isValidReferralLink;

// اضافه کردن debug function
window.debugReferral = function() {
    console.log("=== DEBUG REFERRAL INFO ===");
    console.log("REFERRAL_CODE:", REFERRAL_CODE);
    console.log("REFERRAL_LINK:", REFERRAL_LINK);
    console.log("Validation result:", isValidReferralLink(REFERRAL_LINK));
    console.log("Body data-referral-code:", document.body.getAttribute('data-referral-code'));
    console.log("Body data-referral-link:", document.body.getAttribute('data-referral-link'));
};
