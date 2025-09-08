document.addEventListener("DOMContentLoaded", function() {
    // Countdown timer
    const endTime = new Date("2025-10-01T23:59:59Z").getTime();
    
    const countdown = setInterval(() => {
        const now = new Date().getTime();
        const distance = endTime - now;
        
        if (distance < 0) {
            clearInterval(countdown);
            document.getElementById("days").innerText = "00";
            document.getElementById("hours").innerText = "00";
            document.getElementById("minutes").innerText = "00";
            document.getElementById("seconds").innerText = "00";
            return;
        }
        
        document.getElementById("days").innerText = Math.floor(distance / (1000 * 60 * 60 * 24)).toString().padStart(2, '0');
        document.getElementById("hours").innerText = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)).toString().padStart(2, '0');
        document.getElementById("minutes").innerText = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60)).toString().padStart(2, '0');
        document.getElementById("seconds").innerText = Math.floor((distance % (1000 * 60)) / 1000).toString().padStart(2, '0');
    }, 1000);
    
    console.log("Enhanced airdrop.js loaded successfully");
});

document.addEventListener('DOMContentLoaded', function() {
    const USER_ID = new URLSearchParams(window.location.search).get('telegram_id') || 
                   window.Telegram?.WebApp?.initDataUnsafe?.user?.id || 
                   'guest';

    // بررسی وضعیت اتصال wallet در بارگذاری صفحه
    checkWalletStatus();

    // تنظیمات Telegram WebApp
    if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
    }
});

async function checkWalletStatus() {
    try {
        const USER_ID = new URLSearchParams(window.location.search).get('telegram_id') || 
                       window.Telegram?.WebApp?.initDataUnsafe?.user?.id || 
                       'guest';

        const response = await fetch(`/api/wallet/status?telegram_id=${USER_ID}`);
        const data = await response.json();
        
        const walletButton = document.getElementById('walletButton');
        const walletIcon = document.getElementById('walletIcon');
        const walletDropdown = document.getElementById('walletDropdown');
        const connectedAddress = document.getElementById('connectedAddress');
        
        if (data.connected && data.address) {
            // تغییر ایکون به تیک
            walletIcon.textContent = '✓';
            walletButton.classList.add('completed');
            
            // نمایش آدرس در dropdown
            const shortAddress = `${data.address.slice(0, 8)}...${data.address.slice(-8)}`;
            connectedAddress.innerHTML = `
                <strong>Connected Wallet:</strong><br>
                ${shortAddress}
                <div style="font-size: 10px; color: rgba(255,255,255,0.6); margin-top: 5px;">
                    Full: ${data.address}
                </div>
            `;
        } else {
            // حالت عدم اتصال
            walletIcon.textContent = '>';
            walletButton.classList.remove('completed');
            walletDropdown.style.display = 'none';
        }
        
    } catch (error) {
        console.error('Error checking wallet status:', error);
    }
}

function handleWalletAction() {
    const USER_ID = new URLSearchParams(window.location.search).get('telegram_id') || 
                   window.Telegram?.WebApp?.initDataUnsafe?.user?.id || 
                   'guest';
    
    const walletDropdown = document.getElementById('walletDropdown');
    const walletIcon = document.getElementById('walletIcon');
    
    // اگر wallet متصل است، dropdown را toggle کن
    if (walletIcon.textContent === '✓') {
        if (walletDropdown.style.display === 'none' || !walletDropdown.style.display) {
            walletDropdown.style.display = 'block';
        } else {
            walletDropdown.style.display = 'none';
        }
    } else {
        // اگر wallet متصل نیست، صفحه اتصال را باز کن
        if (window.Telegram?.WebApp) {
            window.Telegram.WebApp.openLink(`${window.location.origin}/wallet-browser-connect?telegram_id=${USER_ID}`);
        } else {
            window.open(`/wallet-browser-connect?telegram_id=${USER_ID}`, '_blank');
        }
    }
}

async function disconnectWallet() {
    try {
        const USER_ID = new URLSearchParams(window.location.search).get('telegram_id') || 
                       window.Telegram?.WebApp?.initDataUnsafe?.user?.id || 
                       'guest';

        const response = await fetch('/api/wallet/disconnect', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                telegram_id: USER_ID
            })
        });

        const data = await response.json();
        
        if (data.success) {
            // بروزرسانی UI
            const walletIcon = document.getElementById('walletIcon');
            const walletButton = document.getElementById('walletButton');
            const walletDropdown = document.getElementById('walletDropdown');
            
            walletIcon.textContent = '>';
            walletButton.classList.remove('completed');
            walletDropdown.style.display = 'none';
            
            // نمایش پیام موفقیت (اختیاری)
            showNotification('Wallet disconnected successfully!', 'success');
        } else {
            showNotification('Failed to disconnect wallet', 'error');
        }
        
    } catch (error) {
        console.error('Error disconnecting wallet:', error);
        showNotification('Error disconnecting wallet', 'error');
    }
}

function showNotification(message, type) {
    // ایجاد notification ساده
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: ${type === 'success' ? '#28a745' : '#dc3545'};
        color: white;
        padding: 10px 20px;
        border-radius: 5px;
        z-index: 1000;
        font-size: 14px;
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        document.body.removeChild(notification);
    }, 3000);
}
