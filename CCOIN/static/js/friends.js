console.log("Friends.js loaded");

document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM loaded, setting up buttons");
    
    const inviteButton = document.getElementById('inviteButton');
    const copyButton = document.getElementById('copyButton');
    
    if (inviteButton) {
        inviteButton.addEventListener('click', function() {
            console.log("Invite button clicked");
            console.log("Using referral link:", window.REFERRAL_LINK);
            
            if (!window.REFERRAL_LINK || window.REFERRAL_LINK.endsWith("?start=")) {
                alert('Error: Invalid referral link!');
                console.error("Invalid referral link:", window.REFERRAL_LINK);
                return;
            }
            
            if (window.Telegram && window.Telegram.WebApp) {
                try {
                    window.Telegram.WebApp.openLink(window.REFERRAL_LINK);
                } catch (e) {
                    console.error("Telegram WebApp error:", e);
                    window.open(window.REFERRAL_LINK, '_blank');
                }
            } else {
                window.open(window.REFERRAL_LINK, '_blank');
            }
        });
    }
    
    if (copyButton) {
        copyButton.addEventListener('click', function() {
            console.log("Copy button clicked");
            console.log("Copying referral link:", window.REFERRAL_LINK);
            
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
    }
});
