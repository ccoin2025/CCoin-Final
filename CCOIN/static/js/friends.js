console.log("Friends.js loaded");

document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM loaded, setting up invite button");
    
    const inviteButton = document.getElementById('inviteButton');
    const copyButton = document.getElementById('copyButton');
    
    if (inviteButton) {
        console.log("Invite button found, attaching event listener");
        
        inviteButton.addEventListener('click', function() {
            console.log("Invite button clicked!");
            console.log("Using referral link:", window.REFERRAL_LINK);
            
            if (!window.REFERRAL_LINK || window.REFERRAL_LINK.endsWith("?start=")) {
                alert('Error: Invalid referral link!');
                return;
            }
            
            // تلاش اول: Telegram WebApp
            if (window.Telegram && window.Telegram.WebApp) {
                try {
                    console.log("Opening with Telegram WebApp");
                    window.Telegram.WebApp.openLink(window.REFERRAL_LINK);
                } catch (e) {
                    console.log("Telegram WebApp failed, using window.open");
                    window.open(window.REFERRAL_LINK, '_blank');
                }
            } else {
                console.log("Telegram WebApp not available, using window.open");
                window.open(window.REFERRAL_LINK, '_blank');
            }
        });
    } else {
        console.error("Invite button NOT found!");
    }
    
    if (copyButton) {
        console.log("Copy button found, attaching event listener");
        
        copyButton.addEventListener('click', function() {
            console.log("Copy button clicked!");
            
            if (!window.REFERRAL_LINK || window.REFERRAL_LINK.endsWith("?start=")) {
                alert('Error: Invalid referral link!');
                return;
            }
            
            if (navigator.clipboard) {
                navigator.clipboard.writeText(window.REFERRAL_LINK).then(() => {
                    alert('Link copied!');
                }).catch(() => {
                    alert('Copy failed!');
                });
            } else {
                const textArea = document.createElement('textarea');
                textArea.value = window.REFERRAL_LINK;
                document.body.appendChild(textArea);
                textArea.select();
                try {
                    document.execCommand('copy');
                    alert('Link copied!');
                } catch (err) {
                    alert('Copy failed!');
                }
                document.body.removeChild(textArea);
            }
        });
    } else {
        console.error("Copy button NOT found!");
    }
});

// تابع backup برای صورتی که event listener کار نکرد
function directInvite() {
    console.log("Direct invite called");
    if (window.REFERRAL_LINK && !window.REFERRAL_LINK.endsWith("?start=")) {
        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.openLink(window.REFERRAL_LINK);
        } else {
            window.open(window.REFERRAL_LINK, '_blank');
        }
    }
}
