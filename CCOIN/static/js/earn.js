console.log("earn.js script started");

function handleAction(button, platform) {
    console.log("handleAction called with platform: " + platform);
    platform = platform.toLowerCase();

    // جلوگیری از کلیک مجدد روی تسک‌های complete شده
    if (button.classList.contains('completed')) {
        console.log("Task already completed");
        return;
    }

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
    const originalText = statusElement.textContent;
    
    statusElement.textContent = "Verifying...";
    button.disabled = true;
    button.style.cursor = "not-allowed";
    button.style.opacity = "0.6";

    // تایمر 4 ثانیه برای شبیه‌سازی بررسی
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

            // اگر تسک قبلاً complete شده
            if (verifyData.already_completed) {
                statusElement.textContent = "Task Completed!";
                statusElement.classList.add("done");
                button.classList.add("completed");
                button.disabled = true;
                button.style.opacity = "1";
                return;
            }

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
                    button.style.opacity = "1";

                    // نمایش پیام موفقیت
                    if (claimData.tokens_added) {
                        window.Telegram.WebApp.showAlert(`🎉 Congratulations! You earned ${claimData.tokens_added} tokens!`);
                        
                        // به‌روزرسانی توکن در صفحه (اگر المنتی برای نمایش توکن وجود داشته باشد)
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
                    
                    // نمایش پیام خطا
                    window.Telegram.WebApp.showAlert(claimData.error || "Failed to claim reward. Please try again.");
                }
            } else {
                // ✅ اگر verification ناموفق بود
                const attemptCount = verifyData.attempt_count || 0;
                
                // 📱 برای Telegram - پیام واقعی نمایش بده
                if (platform === 'telegram') {
                    statusElement.textContent = "Please join our channel first!";
                    statusElement.style.color = "#ff4444";
                    window.Telegram.WebApp.showAlert("❌ Please join our Telegram channel first, then try again.");
                    
                    button.disabled = false;
                    button.style.cursor = "pointer";
                    button.style.opacity = "1";
                } 
                // 🎭 برای Instagram, X, YouTube - سیستم 3 بار کلیک
                else {
                    if (attemptCount < 3) {
                        statusElement.textContent = `Checking... (${attemptCount}/3)`;
                        statusElement.style.color = "#ffa500";
                        
                        // پیام‌های مختلف برای هر attempt
                        if (attemptCount === 1) {
                            window.Telegram.WebApp.showAlert("⏳ We're verifying your follow status. Please make sure you've followed us and try again.");
                        } else if (attemptCount === 2) {
                            window.Telegram.WebApp.showAlert("🔍 Still checking... Please ensure you've followed our page and try one more time.");
                        }
                    } else {
                        // در دفعه سوم اگر باز هم verify نشد (نباید اتفاق بیفته چون mock API داریم)
                        statusElement.textContent = "Verification failed!";
                        statusElement.style.color = "#ff4444";
                        
                        const platformName = platform === 'instagram' ? 'Instagram page' :
                                           platform === 'x' ? 'X (Twitter) account' :
                                           'YouTube channel';
                        
                        window.Telegram.WebApp.showAlert(`❌ Please make sure you have followed our ${platformName}, then try again.`);
                    }
                    
                    button.disabled = false;
                    button.style.cursor = "pointer";
                    button.style.opacity = "1";
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
    }, 4000); // 4 ثانیه تاخیر برای شبیه‌سازی بررسی واقعی
}

// Auto-refresh task status on page load (optional)
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
            
            // اگر نیاز به refresh صفحه باشد
            if (data.success && data.platforms) {
                // می‌توانید اینجا UI را به‌روزرسانی کنید
                console.log("All tasks checked successfully");
            }
        }
    } catch (err) {
        console.error("Error checking tasks on load:", err);
    }
});
