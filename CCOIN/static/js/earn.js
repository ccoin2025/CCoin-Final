console.log("earn.js script started");

function handleAction(button, platform) {
    console.log("handleAction called with platform: " + platform);
    platform = platform.toLowerCase();
    
    const urls = {
        'telegram': "https://t.me/CCOIN_OFFICIAL",
        'instagram': "https://instagram.com/ccoin_official",
        'x': "https://x.com/CCOIN_OFFICIAL",
        'youtube': "https://youtube.com/@CCOIN_OFFICIAL"
    };
    
    const url = urls[platform];
    
    if (!url) {
        console.error("No URL for platform: " + platform);
        alert("No URL defined for this platform!");
        return;
    }
    
    console.log("Attempting to open: " + url);
    const newWindow = window.open(url, "_blank");
    
    if (!newWindow || newWindow.closed || typeof newWindow.closed === 'undefined') {
        console.warn("Pop-up blocked by browser.");
        alert("Pop-up blocked! Please allow pop-ups and try again.");
        return;
    }
    
    const statusElement = button.querySelector(".status");
    statusElement.textContent = "Verifying...";
    button.disabled = true;
    button.style.cursor = "not-allowed";
    
    setTimeout(async () => {
        try {
            console.log("Verifying task for platform: " + platform);
            
            const verifyRes = await fetch("/earn/verify-task", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Telegram-Init-Data": window.Telegram.WebApp.initData || ""
                },
                body: JSON.stringify({platform: platform})
            });
            
            const verifyData = await verifyRes.json();
            console.log("Verify response: ", verifyData);
            
            if (verifyData.success) {
                // درخواست کسب پاداش
                const claimRes = await fetch("/earn/claim-reward", {
                    method: "POST", 
                    headers: {
                        "Content-Type": "application/json",
                        "X-Telegram-Init-Data": window.Telegram.WebApp.initData || ""
                    },
                    body: JSON.stringify({platform: platform})
                });
                
                const claimData = await claimRes.json();
                
                if (claimData.success) {
                    statusElement.textContent = "Task Completed!";
                    statusElement.classList.add("done");
                    button.classList.add("completed");
                    
                    // نمایش پیام موفقیت
                    if (claimData.tokens_added) {
                        alert(`Congratulations! You earned ${claimData.tokens_added} tokens!`);
                    }
                } else {
                    statusElement.textContent = claimData.error || "Claim failed!";
                    statusElement.style.color = "red";
                    button.disabled = false;
                    button.style.cursor = "pointer";
                }
            } else {
                statusElement.textContent = verifyData.error || "Follow verification failed!";
                statusElement.style.color = "red";
                button.disabled = false;
                button.style.cursor = "pointer";
            }
        } catch (err) {
            console.error("Error verifying task:", err);
            statusElement.textContent = "Network Error!";
            statusElement.style.color = "red";
            button.disabled = false;
            button.style.cursor = "pointer";
        }
    }, 3000);
}
