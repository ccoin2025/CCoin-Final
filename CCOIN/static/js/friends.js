console.log("Friends.js loaded - Simple version");

let REFERRAL_CODE = null;
let REFERRAL_LINK = null;

function inviteFriend() {
    console.log("=== INVITE BUTTON CLICKED ===");
    console.log("REFERRAL_LINK:", REFERRAL_LINK);
    
    if (!REFERRAL_LINK) {
        console.error("REFERRAL_LINK is null/undefined");
        alert("Referral link does not exist!");
        return;
    }

    console.log("Opening referral link:", REFERRAL_LINK);

    try {
        if (window.Telegram && window.Telegram.WebApp && typeof window.Telegram.WebApp.openLink === 'function') {
            console.log("Using Telegram WebApp.openLink");
            window.Telegram.WebApp.openLink(REFERRAL_LINK);
        } else {
            console.log("Using window.open");
            window.open(REFERRAL_LINK, '_blank');
        }
    } catch (error) {
        console.error("Error opening link:", error);
        try {
            window.open(REFERRAL_LINK, '_blank');
        } catch (fallbackError) {
            console.error("Fallback also failed:", fallbackError);
            alert("Error opening the link");
        }
    }
}

function copyLink() {
    console.log("=== COPY BUTTON CLICKED ===");
    console.log("REFERRAL_LINK:", REFERRAL_LINK);
    
    if (!REFERRAL_LINK) {
        console.error("REFERRAL_LINK is null/undefined");
        alert("Referral link not found!");
        return;
    }

    console.log("Copying referral link:", REFERRAL_LINK);

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(REFERRAL_LINK).then(() => {
            console.log("Link copied successfully");
            alert("Link copied!");
        }).catch((error) => {
            console.error("Clipboard API failed:", error);
            fallbackCopy();
        });
    } else {
        console.log("Clipboard API not available, using fallback");
        fallbackCopy();
    }
}

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
            alert("Link copied!");
        } else {
            console.error("Fallback copy failed");
            alert("Copy error");
        }
    } catch (error) {
        console.error("Fallback copy error:", error);
        alert("Copy error");
    }
}

document.addEventListener('DOMContentLoaded', function() {
    console.log("=== DOM READY ===");
    
    REFERRAL_CODE = document.body.getAttribute('data-referral-code');
    REFERRAL_LINK = document.body.getAttribute('data-referral-link');
    
    console.log("Retrieved REFERRAL_CODE:", REFERRAL_CODE);
    console.log("Retrieved REFERRAL_LINK:", REFERRAL_LINK);
    
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

window.inviteFriend = inviteFriend;
window.copyLink = copyLink;
