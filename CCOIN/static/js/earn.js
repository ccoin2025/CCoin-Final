console.log("earn.js script started");

function handleAction(button, platform) {
    console.log("handleAction called with platform: " + platform);
    platform = platform.toLowerCase();

    if (button.classList.contains('completed')) {
        console.log("Task already completed");
        return;
    }

    const urls = {
        'telegram': "https://t.me/CCOIN_OFFICIAL",
        'instagram': "https://instagram.com/ccoin_official",
        'x': "https://x.com/OFFICIAL_CCOIN",
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
    const originalText = statusElement.textContent; 
    
    statusElement.textContent = "Verifying...";
    button.disabled = true;
    button.style.cursor = "not-allowed";
    button.style.opacity = "0.6";

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

            if (verifyData.already_completed) {
                statusElement.textContent = "Task Completed!";
                statusElement.classList.add("done");
                button.classList.add("completed");
                button.disabled = true;
                button.style.opacity = "1";
                return;
            }

            if (verifyData.success) {
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
                    button.style.opacity = "1";

                    if (claimData.tokens_added) {
                        window.Telegram.WebApp.showAlert(`🎉 Congratulations! You earned ${claimData.tokens_added} tokens!`);
                        
                        const tokenElement = document.querySelector('.user-tokens');
                        if (tokenElement && claimData.total_tokens) {
                            tokenElement.textContent = claimData.total_tokens;
                        }
                    }
                } else {
                    statusElement.textContent = claimData.error || "Claim failed!";
                    statusElement.style.color = "#ff4444";
                    button.disabled = false;
                    button.style.cursor = "pointer";
                    button.style.opacity = "1";
                    
                    window.Telegram.WebApp.showAlert(claimData.error || "Failed to claim reward. Please try again.");
                }
            } else {
                const attemptCount = verifyData.attempt_count || 0;
                
                if (platform === 'telegram') {
                    statusElement.textContent = "Please join our channel first!";
                    statusElement.style.color = "#ff4444";
                    window.Telegram.WebApp.showAlert("❌ Please join our Telegram channel first, then try again.");
                    
                    button.disabled = false;
                    button.style.cursor = "pointer";
                    button.style.opacity = "1";
                } 
                else {
                    if (attemptCount < 3) {
                        statusElement.textContent = "Checking...";
                        statusElement.style.color = "#ffa500";
                        
                        if (attemptCount === 1) {
                            window.Telegram.WebApp.showAlert("⏳ We're verifying your follow status. Please make sure you've followed us and try again.");
                        } else if (attemptCount === 2) {
                            window.Telegram.WebApp.showAlert("🔍 Still checking... Please ensure you've followed our page and try one more time.");
                        }
                        
                        setTimeout(() => {
                            statusElement.textContent = originalText; 
                            statusElement.style.color = ""; 
                            button.disabled = false;
                            button.style.cursor = "pointer";
                            button.style.opacity = "1";
                            
                            console.log(`Button reset to original state after attempt ${attemptCount}`);
                        }, 5000); 
                        
                    } else {
                       
                        statusElement.textContent = "Verification failed!";
                        statusElement.style.color = "#ff4444";
                        
                        const platformName = platform === 'instagram' ? 'Instagram page' :
                                           platform === 'x' ? 'X (Twitter) account' :
                                           'YouTube channel';
                        
                        window.Telegram.WebApp.showAlert(`❌ Please make sure you have followed our ${platformName}, then try again.`);
                        
                        button.disabled = false;
                        button.style.cursor = "pointer";
                        button.style.opacity = "1";
                    }
                }
            }
        } catch (err) {
            console.error("Error verifying task:", err);
            statusElement.textContent = "Network Error!";
            statusElement.style.color = "#ff4444";
            button.disabled = false;
            button.style.cursor = "pointer";
            button.style.opacity = "1";
            
            window.Telegram.WebApp.showAlert("⚠️ Network error occurred. Please check your connection and try again.");
        }
    }, 4000);
}


document.addEventListener('DOMContentLoaded', async () => {
    console.log("Page loaded, checking task statuses...");
    
    try {
        const response = await fetch("/earn/check-all-tasks", {
            method: "GET",
            headers: {
                "Content-Type": "application/json"
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log("Task status check result:", data);
            
            if (data.success && data.platforms) {
                console.log("All tasks checked successfully");
            }
        }
    } catch (err) {
        console.error("Error checking tasks on load:", err);
    }
});
