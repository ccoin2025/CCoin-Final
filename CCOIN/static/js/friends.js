console.log("Friends.js loaded");

// تعریف متغیرهای global از data attributes
let REFERRAL_CODE = null;
let REFERRAL_LINK = null;

// تابع validation برای بررسی صحت لینک رفرال
function isValidReferralLink(link) {
    console.log("Validating referral link:", link);
    
    if (!link || link === "") {
        console.log("Link is empty");
        return false;
    }
    
    if (link === "https://t.me/CTG_COIN_BOT?start=") {
        console.log("Link has empty start parameter");
        return false;
    }
    
    if (!link.includes("?start=")) {
        console.log("Link doesn't contain start parameter");
        return false;
    }
    
    const referralCode = link.split("?start=")[1];
    if (!referralCode || referralCode === "") {
        console.log("Referral code is empty");
        return false;
    }
    
    console.log("Link validation passed, referral code:", referralCode);
    return true;
}

// تابع دعوت دوست
function inviteFriend() {
    console.log("Invite button clicked!");
    console.log("Using referral link:", REFERRAL_LINK);
    console.log("Using referral code:", REFERRAL_CODE);
    
    if (!isValidReferralLink(REFERRAL_LINK)) {
        alert('خطا: کد رفرال نامعتبر است!\nکد: ' + (REFERRAL_CODE || 'موجود نیست'));
        console.error("Invalid referral link detected");
        return;
    }

    // تلاش برای باز کردن لینک
    try {
        if (window.Telegram && window.Telegram.WebApp) {
            console.log("Opening with Telegram WebApp");
            window.Telegram.WebApp.openLink(REFERRAL_LINK);
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
    console.log("Copy button clicked!");
    
    if (!isValidReferralLink(REFERRAL_LINK)) {
        alert('خطا: کد رفرال نامعتبر است!\nکد: ' + (REFERRAL_CODE || 'موجود نیست'));
        console.error("Invalid referral link detected");
        return;
    }

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
    console.log("DOM loaded, initializing friends page");
    
    // دریافت متغیرها از data attributes
    REFERRAL_CODE = document.body.getAttribute('data-referral-code');
    REFERRAL_LINK = document.body.getAttribute('data-referral-link');
    
    console.log("Loaded REFERRAL_CODE:", REFERRAL_CODE);
    console.log("Loaded REFERRAL_LINK:", REFERRAL_LINK);
    
    // پیدا کردن دکمه‌ها
    const inviteButton = document.getElementById('inviteButton');
    const copyButton = document.getElementById('copyButton');

    if (inviteButton) {
        console.log("Invite button found, attaching event listener");
        inviteButton.addEventListener('click', inviteFriend);
    } else {
        console.error("Invite button NOT found!");
    }

    if (copyButton) {
        console.log("Copy button found, attaching event listener");
        copyButton.addEventListener('click', copyLink);
    } else {
        console.error("Copy button NOT found!");
    }
    
    // بررسی اولیه صحت داده‌ها
    if (!isValidReferralLink(REFERRAL_LINK)) {
        console.warn("Invalid referral link detected on page load");
        console.warn("This may cause issues with invite/copy functionality");
    }
});

// تابع‌های global برای استفاده در صورت نیاز
window.inviteFriend = inviteFriend;
window.copyLink = copyLink;
