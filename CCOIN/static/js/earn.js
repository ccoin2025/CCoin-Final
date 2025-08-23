console.log("earn.js script started");

function handleAction(button, platform) {
    console.log("handleAction called with platform: " + platform);
    platform = platform.toLowerCase();
    console.log("Converted platform to: " + platform);

    const urls = {
        'telegram': "https://t.me/CCOIN_OFFICIAL",
        'instagram': "https://instagram.com/ccoin_official",
        'x': "https://x.com/CCOIN_OFFICIAL",
        'youtube': "https://youtube.com/@CCOIN_OFFICIAL"
    };

    const oauthUrls = {
        'instagram': "https://api.instagram.com/oauth/authorize?client_id=YOUR_INSTAGRAM_CLIENT_ID&redirect_uri=https://your-domain.com/insta-callback&response_type=code",
        'x': "https://x.com/oauth/authorize?oauth_token=YOUR_X_OAUTH_TOKEN",
        'youtube': "https://accounts.google.com/o/oauth2/auth?client_id=YOUR_YOUTUBE_CLIENT_ID&redirect_uri=https://your-domain.com/youtube-callback&scope=https://www.googleapis.com/auth/youtube.readonly&response_type=code"
    };

    const url = oauthUrls[platform] || urls[platform];
    console.log("URL for platform: " + url);
    if (!url) {
        console.error("No URL for platform: " + platform);
        alert("No URL defined for this platform!");
        return;
    }

    console.log("Attempting to open: " + url);
    const newWindow = window.open(url, "_blank");
    if (!newWindow || newWindow.closed || typeof newWindow.closed === 'undefined') {
        console.warn("Pop-up blocked by browser. Please allow pop-ups for this site.");
        alert("Pop-up blocked! Please allow pop-ups and try again.");
        return;
    }

    console.log("Window opened successfully");
    const statusElement = button.querySelector(".status");
    statusElement.textContent = "Verifying...";
    button.disabled = true;
    button.style.cursor = "not-allowed";

    setTimeout(async () => {
        try {
            console.log("Verifying task for platform: " + platform);
            const verifyRes = await fetch("/verify-task", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Telegram-Init-Data": window.Telegram.WebApp.initData
                },
                body: JSON.stringify({ platform: platform })
            });

            const verifyData = await verifyRes.json();
            console.log("Verify response: ", verifyData);

            if (verifyData.success) {
                statusElement.textContent = "Task Completed!";
                statusElement.classList.add("done");
                button.classList.add("completed");

                await fetch("/claim-reward", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Telegram-Init-Data": window.Telegram.WebApp.initData
                    },
                    body: JSON.stringify({ platform: platform })
                });
            } else {
                statusElement.textContent = verifyData.error || "Failed!";
                statusElement.style.color = "red";
                button.disabled = false;
                button.style.cursor = "pointer";
            }
        } catch (err) {
            console.error("Error verifying task:", err);
            statusElement.textContent = "Error!";
            statusElement.style.color = "red";
            button.disabled = false;
            button.style.cursor = "pointer";
        }
    }, 2000);
}