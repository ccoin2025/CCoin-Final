// Use global variables from HTML
const {
    USER_ID,
    SOLANA_RPC_URL,
    COMMISSION_AMOUNT,
    ADMIN_WALLET,
    INITIAL_TASKS_COMPLETED,
    INITIAL_INVITED_FRIENDS,
    INITIAL_WALLET_CONNECTED,
    INITIAL_COMMISSION_PAID,
    INITIAL_WALLET_ADDRESS
} = window.APP_CONFIG;

let tasksCompleted = {
    task: INITIAL_TASKS_COMPLETED,
    invite: INITIAL_INVITED_FRIENDS,
    wallet: INITIAL_WALLET_CONNECTED,
    pay: INITIAL_COMMISSION_PAID
};

let connectedWallet = INITIAL_WALLET_ADDRESS;
let phantomProvider = null;
let phantomDetected = false;

// Fix: BS58 utility functions
function ensureBS58() {
    if (typeof bs58 === 'undefined') {
        if (typeof window.bs58 !== 'undefined') {
            window.bs58 = window.bs58;
            return true;
        }
        console.error('BS58 library not loaded');
        return false;
    }
    return true;
}

function encodeBase58(data) {
    if (!ensureBS58()) {
        // Fallback to base64 if bs58 not available
        return btoa(String.fromCharCode.apply(null, data));
    }
    try {
        if (typeof bs58 === 'function') {
            return bs58(data);
        } else if (bs58.encode) {
            return bs58.encode(data);
        } else if (bs58.default && bs58.default.encode) {
            return bs58.default.encode(data);
        } else {
            throw new Error('BS58 encode function not available');
        }
    } catch (error) {
        console.error('BS58 encoding error:', error);
        // Fallback to base64
        return btoa(String.fromCharCode.apply(null, data));
    }
}

// **Fixed: Countdown Timer**
function updateCountdown() {
    // Set the target date (30 days from now for example)
    const targetDate = new Date();
    targetDate.setDate(targetDate.getDate() + 30);
    
    const now = new Date().getTime();
    const distance = targetDate.getTime() - now;
    
    if (distance > 0) {
        const days = Math.floor(distance / (1000 * 60 * 60 * 24));
        const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);
        
        document.getElementById('days').textContent = days.toString().padStart(2, '0');
        document.getElementById('hours').textContent = hours.toString().padStart(2, '0');
        document.getElementById('minutes').textContent = minutes.toString().padStart(2, '0');
        document.getElementById('seconds').textContent = seconds.toString().padStart(2, '0');
    } else {
        document.getElementById('days').textContent = '00';
        document.getElementById('hours').textContent = '00';
        document.getElementById('minutes').textContent = '00';
        document.getElementById('seconds').textContent = '00';
    }
}

// Enhanced Phantom detection با reset کامل
async function detectPhantomWallet(forceReset = false) {
    console.log("🔍 Starting Phantom detection...", forceReset ? "(FORCED RESET)" : "");
    
    if (forceReset) {
        phantomProvider = null;
        phantomDetected = false;
    }
    
    // بررسی window.phantom (روش جدید)
    if (window.phantom?.solana?.isPhantom) {
        console.log("✅ Phantom detected via window.phantom.solana");
        phantomDetected = true;
        return window.phantom.solana;
    }
    
    // بررسی window.solana (روش قدیمی)
    if (window.solana?.isPhantom) {
        console.log("✅ Phantom detected via window.solana (legacy)");
        phantomDetected = true;
        return window.solana;
    }
    
    // انتظار برای load شدن
    console.log("⏳ Waiting for Phantom extension to load...");
    for (let i = 0; i < 50; i++) {
        await new Promise(resolve => setTimeout(resolve, 100));
        
        if (window.phantom?.solana?.isPhantom) {
            console.log("✅ Phantom detected after waiting");
            phantomDetected = true;
            return window.phantom.solana;
        }
        if (window.solana?.isPhantom) {
            console.log("✅ Phantom detected (legacy) after waiting");
            phantomDetected = true;
            return window.solana;
        }
    }
    
    console.log("❌ Phantom wallet not found after waiting");
    phantomDetected = false;
    return null;
}

async function getPhantomProvider(forceReset = false) {
    if (forceReset || !phantomProvider || !phantomDetected) {
        phantomProvider = await detectPhantomWallet(forceReset);
    }
    return phantomProvider;
}

// **اصلاح شده: تشخیص محیط Telegram**
function isTelegramEnvironment() {
    return window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData;
}

// **اصلاح شده: باز کردن لینک در مرورگر خارجی**
function openExternalLink(url) {
    console.log("🔗 Opening external link:", url);
    
    if (isTelegramEnvironment()) {
        console.log("📱 Telegram environment detected, using Telegram API");
        try {
            // روش اول: استفاده از Telegram WebApp API
            if (window.Telegram.WebApp.openTelegramLink) {
                window.Telegram.WebApp.openTelegramLink(url);
                return;
            }
            
            // روش دوم: استفاده از openLink
            if (window.Telegram.WebApp.openLink) {
                window.Telegram.WebApp.openLink(url, { try_instant_view: false });
                return;
            }
            
            // روش سوم: fallback به window.open
            console.log("🔄 Falling back to window.open");
            window.open(url, '_blank');
            
        } catch (error) {
            console.error("Error opening Telegram link:", error);
            // آخرین fallback
            window.location.href = url;
        }
    } else {
        console.log("🌐 Standard browser environment");
        // برای دسکتاپ یا مرورگر عادی
        window.open(url, '_blank');
    }
}

// **اصلاح شده: هدایت مستقیم بدون مودال واسطه**
function redirectToPhantomApp(deeplink) {
    console.log("🦄 Redirecting directly to Phantom:", deeplink);
    // هدایت مستقیم بدون هیچ تاخیر یا مودال
    openExternalLink(deeplink);
    // نمایش پیام موفقیت
    showToast("Redirecting to Phantom wallet...", "info");
}

// Wallet connection handler
async function handleWalletConnection() {
    if (!tasksCompleted.wallet) {
        await connectWallet();
    } else {
        toggleWalletDropdown();
    }
}

// **اصلاح شده: اتصال مستقیم کیف پول**
async function connectWallet() {
    console.log("🔗 Starting wallet connection...");
    
    // Force reset Phantom provider
    const provider = await getPhantomProvider(true);
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|OperaMini/i.test(navigator.userAgent);
    
    if (isMobile || isTelegramEnvironment()) {
        console.log("📱 Mobile/Telegram environment - using deeplink");
        
        try {
            const params = new URLSearchParams({
                cluster: "devnet",
                app_url: window.location.origin,
                redirect_link: `${window.location.origin}/airdrop?phantom_action=connect`
            });
            
            const connectUrl = `https://phantom.app/ul/v1/connect?${params.toString()}`;
            
            redirectToPhantomApp(connectUrl);
            
        } catch (error) {
            console.error("Error creating deeplink:", error);
            showToast("Error creating connection link", "error");
        }
        
    } else {
        // برای دسکتاپ
        if (provider) {
            await connectWalletDirect();
        } else {
            showPhantomModal();
        }
    }
}

// **اصلاح کامل: اتصال wallet با تأکید بر account اصلی**
async function connectWalletDirect() {
    try {
        console.log("🔗 Starting REAL wallet connection...");
        
        // مرحله 1: کاملاً پاک کردن تمام اتصالات
        if (phantomProvider && phantomProvider.isConnected) {
            console.log("🔌 Force disconnecting all connections...");
            try {
                await phantomProvider.disconnect();
            } catch (e) {
                console.log("Disconnect error (expected):", e);
            }
        }
        
        // مرحله 2: کمی صبر کنیم تا Phantom reset شود
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // مرحله 3: بررسی دوباره Phantom provider
        phantomProvider = await detectPhantomWallet();
        if (!phantomProvider) {
            throw new Error("Phantom wallet not found after reset");
        }
        
        console.log("🦄 Phantom provider reset complete");
        
        // مرحله 4: درخواست اتصال با تنظیمات خاص
        console.log("🔑 Requesting connection to PRIMARY account...");
        
        // استفاده از روش استاندارد Phantom
        const connectOptions = {
            onlyIfTrusted: false  // اجبار به نمایش popup
        };
        
        const response = await phantomProvider.connect(connectOptions);
        
        if (!response || !response.publicKey) {
            throw new Error('No public key received from Phantom');
        }
        
        // مرحله 5: دریافت آدرس اصلی
        const primaryAddress = response.publicKey.toString();
        console.log("🎯 Primary address from connection:", primaryAddress);
        
        // مرحله 6: Double-check با provider
        if (phantomProvider.publicKey) {
            const providerAddress = phantomProvider.publicKey.toString();
            console.log("🏦 Provider address after connection:", providerAddress);
            
            if (primaryAddress !== providerAddress) {
                console.warn("⚠️ Address mismatch detected!");
                console.warn("Connection response:", primaryAddress);
                console.warn("Provider current:", providerAddress);
                
                // نمایش popup برای انتخاب
                const message = `Address mismatch detected!\n\nFrom connection: ${primaryAddress}\nFrom provider: ${providerAddress}\n\nWhich one is your MAIN Phantom address?\n\nClick OK for the first one, Cancel for the second one.`;
                
                const useFirst = confirm(message);
                const finalAddress = useFirst ? primaryAddress : providerAddress;
                
                console.log("👤 User selected address:", finalAddress);
                connectedWallet = finalAddress;
            } else {
                console.log("✅ Addresses match - using:", primaryAddress);
                connectedWallet = primaryAddress;
            }
        } else {
            console.log("✅ Using connection response address:", primaryAddress);
            connectedWallet = primaryAddress;
        }
        
        // مرحله 7: نمایش اطلاعات کامل برای debugging
        console.log("📊 FINAL CONNECTION INFO:");
        console.log("- Selected Address:", connectedWallet);
        console.log("- Response publicKey:", response.publicKey.toString());
        console.log("- Provider publicKey:", phantomProvider.publicKey?.toString());
        console.log("- Provider isConnected:", phantomProvider.isConnected);
        
        // مرحله 8: تأیید از کاربر
        const confirmMessage = `Please confirm this is your MAIN Phantom wallet address:\n\n${connectedWallet}\n\nThis address should match the one you see in your Phantom wallet.`;
        
        if (!confirm(confirmMessage)) {
            throw new Error("User rejected the wallet address");
        }
        
        // مرحله 9: ارسال به سرور
        console.log("📤 Saving confirmed address to server...");
        const saveResponse = await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                telegram_id: USER_ID,
                wallet_address: connectedWallet
            })
        });
        
        if (!saveResponse.ok) {
            const errorData = await saveResponse.json();
            throw new Error(errorData.detail || "Failed to save wallet connection");
        }
        
        const result = await saveResponse.json();
        console.log("✅ Server confirmed:", result);
        
        // مرحله 10: بروزرسانی UI
        tasksCompleted.wallet = true;
        updateWalletUI();
        updateTasksUI();
        
        showToast(`Wallet connected: ${connectedWallet.slice(0,6)}...${connectedWallet.slice(-6)}`, "success");
        
        // نمایش آدرس نهایی
        setTimeout(() => {
            alert(`SUCCESS!\n\nConnected wallet: ${connectedWallet}\n\nThis address is now saved to your account.`);
        }, 1000);
        
    } catch (error) {
        console.error("❌ Wallet connection completely failed:", error);
        
        // Reset everything
        connectedWallet = null;
        tasksCompleted.wallet = false;
        updateWalletUI();
        
        // نمایش خطای دقیق
        const errorMessage = error.message || "Unknown connection error";
        showToast(`Connection failed: ${errorMessage}`, "error");
        
        alert(`Connection Failed!\n\n${errorMessage}\n\nPlease try again or make sure:\n1. Phantom is installed\n2. You have accounts in Phantom\n3. You approve the connection`);
    }
}

// تابع جدید برای تغییر account در Phantom
async function switchPhantomAccount() {
    try {
        console.log("🔄 Requesting account switch...");
        
        if (!phantomProvider) {
            throw new Error("Phantom not available");
        }
        
        // disconnect و reconnect برای نمایش popup انتخاب account
        await phantomProvider.disconnect();
        
        // کمی صبر کنیم
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // اتصال مجدد که باید popup account selector را نشان دهد
        const response = await phantomProvider.connect({ onlyIfTrusted: false });
        
        if (response && response.publicKey) {
            const newAddress = response.publicKey.toString();
            console.log("🎯 New account selected:", newAddress);
            
            connectedWallet = newAddress;
            
            // ارسال به سرور
            await fetch('/airdrop/connect_wallet', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    telegram_id: USER_ID,
                    wallet_address: newAddress
                })
            });
            
            updateWalletUI();
            showToast(`Switched to: ${newAddress.slice(0,4)}...${newAddress.slice(-4)}`, "success");
        }
        
    } catch (error) {
        console.error("❌ Account switch failed:", error);
        showToast("Failed to switch account", "error");
    }
}

// **اصلاح شده: پرداخت کمیسیون با روش استاندارد**
async function payCommission() {
    if (!connectedWallet) {
        showToast("Please connect wallet first", "error");
        return;
    }
    
    if (tasksCompleted.pay) {
        showToast("Commission already paid!", "info");
        return;
    }
    
    console.log("💰 Starting commission payment process...");
    
    try {
        // نمایش loading
        const commissionButton = document.getElementById('commission-button');
        const commissionIcon = document.getElementById('commission-icon');
        
        if (commissionButton && commissionIcon) {
            commissionButton.classList.add('loading');
            commissionIcon.className = 'fas fa-spinner right-icon';
        }
        
        // هدایت به صفحه پرداخت خارجی
        const commissionUrl = `/commission/pay?telegram_id=${USER_ID}`;
        
        if (isTelegramEnvironment()) {
            console.log("📱 Telegram environment - opening external payment page");
            window.Telegram.WebApp.openLink(commissionUrl, { try_instant_view: false });
        } else {
            console.log("🌐 Browser environment - opening in new tab");
            window.open(commissionUrl, '_blank');
        }
        
        showToast("Opening payment page...", "info");
        
        // بازگرداندن UI به حالت عادی بعد از 3 ثانیه
        setTimeout(() => {
            if (commissionButton && commissionIcon) {
                commissionButton.classList.remove('loading');
                commissionIcon.className = 'fas fa-chevron-right right-icon';
            }
        }, 3000);
        
    } catch (error) {
        console.error("❌ Commission payment error:", error);
        showToast("Failed to open payment page", "error");
        
        // بازگرداندن UI
        const commissionButton = document.getElementById('commission-button');
        const commissionIcon = document.getElementById('commission-icon');
        if (commissionButton && commissionIcon) {
            commissionButton.classList.remove('loading');
            commissionIcon.className = 'fas fa-chevron-right right-icon';
        }
    }
}

// **باقی توابع**
function toggleWalletDropdown() {
    const dropdown = document.querySelector('.wallet-dropdown-content');
    if (dropdown) {
        dropdown.classList.toggle('show');
    }
}

function updateWalletUI() {
    const button = document.querySelector('#connect-wallet .task-button');
    const leftText = button.querySelector('.left-text');
    const rightIcon = button.querySelector('.right-icon');
    const statusIndicator = button.querySelector('.wallet-status-indicator');
    
    if (tasksCompleted.wallet) {
        leftText.textContent = 'Wallet Connected';
        rightIcon.className = 'fas fa-chevron-down right-icon';
        button.classList.add('wallet-connected');
        statusIndicator.classList.add('connected');
        
        // نمایش آدرس در dropdown
        const addressElement = document.getElementById('wallet-address-dropdown');
        if (addressElement && connectedWallet) {
            addressElement.innerHTML = `
                ${connectedWallet}<br>
                <button onclick="switchPhantomAccount()" style="margin-top:10px; padding:5px 10px; background:#AB9FF2; color:white; border:none; border-radius:5px; cursor:pointer;">
                    Switch Account
                </button>
            `;
        }
        
        // نمایش dropdown content
        document.querySelector('#connect-wallet .task-box').classList.add('completed');
    } else {
        leftText.textContent = 'Connect Wallet';
        rightIcon.className = 'fas fa-chevron-right right-icon';
        button.classList.remove('wallet-connected');
        statusIndicator.classList.remove('connected');
        document.querySelector('#connect-wallet .task-box').classList.remove('completed');
    }
}

function updateTasksUI() {
    // Update tasks completion
    if (tasksCompleted.task) {
        const taskButton = document.querySelector('#complete-tasks .task-button');
        const taskLeftText = taskButton.querySelector('.left-text');
        const taskRightIcon = taskButton.querySelector('.right-icon');
        
        taskLeftText.textContent = 'Tasks Completed';
        taskRightIcon.className = 'fas fa-check right-icon';
        taskButton.classList.add('completed');
        document.querySelector('#complete-tasks .task-box').classList.add('completed');
    }
    
    // Update referral completion
    if (tasksCompleted.invite) {
        const inviteButton = document.querySelector('#invite-friends .task-button');
        const inviteLeftText = inviteButton.querySelector('.left-text');
        const inviteRightIcon = inviteButton.querySelector('.right-icon');
        
        inviteLeftText.textContent = 'Friends Invited';
        inviteRightIcon.className = 'fas fa-check right-icon';
        inviteButton.classList.add('completed');
        document.querySelector('#invite-friends .task-box').classList.add('completed');
    }
    
    // Update commission payment
    if (tasksCompleted.pay) {
        const payButton = document.querySelector('#pay-commission .task-button');
        const payLeftText = payButton.querySelector('.left-text');
        const payRightIcon = payButton.querySelector('.right-icon');
        
        payLeftText.textContent = 'Commission Paid';
        payRightIcon.className = 'fas fa-check right-icon';
        payButton.classList.add('completed');
        document.querySelector('#pay-commission .task-box').classList.add('completed');
    }
    
    updateProgress();
}

function updateProgress() {
    const completedTasks = Object.values(tasksCompleted).filter(Boolean).length;
    const totalTasks = Object.keys(tasksCompleted).length;
    const percentage = (completedTasks / totalTasks) * 100;
    
    const progressBar = document.querySelector('.progress');
    const progressText = document.querySelector('.progress-text');
    
    if (progressBar) {
        progressBar.style.width = percentage + '%';
    }
    
    if (progressText) {
        progressText.textContent = `${completedTasks}/${totalTasks} Tasks Completed`;
    }
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}

function showPhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

function hidePhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Handle URL parameters for Phantom responses
function handlePhantomResponse() {
    const urlParams = new URLSearchParams(window.location.search);
    const phantomAction = urlParams.get('phantom_action');
    
    if (phantomAction === 'connect') {
        const publicKey = urlParams.get('phantom_publicKey');
        
        if (publicKey) {
            console.log('✅ Phantom connection successful:', publicKey);
            connectedWallet = publicKey;
            tasksCompleted.wallet = true;
            updateWalletUI();
            updateTasksUI();
            showToast('Wallet connected successfully!', 'success');
            
            // Clean URL
            const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
            window.history.replaceState({}, document.title, cleanUrl);
        }
    }
}

// Initialize everything when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Airdrop page initialized');
    
    // Handle Phantom response if present
    handlePhantomResponse();
    
    // Update initial UI state
    updateTasksUI();
    updateWalletUI();
    
    // Start countdown
    updateCountdown();
    setInterval(updateCountdown, 1000);
    
    // Initialize Phantom detection
    getPhantomProvider();
});

// Export functions for global use
window.connectWallet = connectWallet;
window.payCommission = payCommission;
window.handleWalletConnection = handleWalletConnection;
window.hidePhantomModal = hidePhantomModal;
window.switchPhantomAccount = switchPhantomAccount;
