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

// تابع برای تولید encryption key
function generateEncryptionKey() {
    // تولید یک کلید ساده برای encryption (اختیاری)
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    return btoa(String.fromCharCode.apply(null, array)).replace(/[^a-zA-Z0-9]/g, '').substring(0, 32);
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
            // **کلیدی: اضافه کردن cluster برای Solana**
            const params = new URLSearchParams({
                cluster: "devnet",  // یا "mainnet-beta" برای mainnet
                app_url: window.location.origin,
                redirect_link: `${window.location.origin}/airdrop?phantom_action=connect&user_id=${USER_ID}`,
                dapp_encryption_public_key: generateEncryptionKey() // برای امنیت
            });
            
            const connectUrl = `https://phantom.app/ul/v1/connect?${params.toString()}`;
            
            console.log("🦄 Phantom connect URL with cluster:", connectUrl);
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

// **اصلاح کامل: اتصال wallet برای desktop**
async function connectWalletDirect() {
    try {
        console.log("🔗 Starting DESKTOP wallet connection...");
        
        // اطمینان از Solana network
        if (phantomProvider && phantomProvider.isConnected) {
            console.log("🔌 Force disconnecting previous connection...");
            try {
                await phantomProvider.disconnect();
            } catch (e) {
                console.log("Disconnect error (expected):", e);
            }
        }
        
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // تنظیم شبکه Solana
        console.log("🦄 Requesting Solana connection...");
        
        const connectOptions = {
            onlyIfTrusted: false,
            // اختیاری: تعیین شبکه برای desktop
            cluster: 'devnet' // یا 'mainnet-beta'
        };
        
        const response = await phantomProvider.connect(connectOptions);
        
        if (!response || !response.publicKey) {
            throw new Error('No public key received from Phantom');
        }
        
        const walletAddress = response.publicKey.toString();
        console.log("🎯 Connected to Solana address:", walletAddress);
        
        // تأیید آدرس Solana
        if (walletAddress.length < 32 || walletAddress.length > 44 || walletAddress.startsWith('0x')) {
            throw new Error(`Invalid Solana address: ${walletAddress}. This looks like an Ethereum address.`);
        }
        
        // تأیید از کاربر
        const confirmMessage = `Connected to Solana wallet:\n\n${walletAddress}\n\nIs this your correct Phantom Solana address?`;
        
        if (!confirm(confirmMessage)) {
            await phantomProvider.disconnect();
            throw new Error("User rejected the wallet address");
        }
        
        // ذخیره آدرس
        connectedWallet = walletAddress;
        
        // ارسال به سرور
        await saveWalletToServer(walletAddress);
        
        // بروزرسانی UI
        tasksCompleted.wallet = true;
        updateWalletUI();
        updateTasksUI();
        
        showToast(`Wallet connected: ${walletAddress.slice(0,6)}...${walletAddress.slice(-6)}`, "success");
        
    } catch (error) {
        console.error("❌ Desktop wallet connection failed:", error);
        
        // Reset
        connectedWallet = null;
        tasksCompleted.wallet = false;
        updateWalletUI();
        
        showToast(`Connection failed: ${error.message}`, "error");
        
        if (error.message.includes('Ethereum')) {
            alert(`Network Error!\n\n${error.message}\n\nPlease make sure you're connected to Solana network in Phantom, not Ethereum.`);
        }
    }
}

// تابع ذخیره wallet در سرور
async function saveWalletToServer(walletAddress) {
    try {
        console.log("📤 Saving wallet to server:", walletAddress);
        
        const response = await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                telegram_id: USER_ID,
                wallet_address: walletAddress
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || "Failed to save wallet");
        }
        
        const result = await response.json();
        console.log("✅ Server save successful:", result);
        return result;
        
    } catch (error) {
        console.error("❌ Server save failed:", error);
        showToast("Failed to save wallet address", "error");
        throw error;
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
            
            // تأیید آدرس Solana
            if (newAddress.length < 32 || newAddress.length > 44 || newAddress.startsWith('0x')) {
                throw new Error(`Invalid Solana address: ${newAddress}`);
            }
            
            connectedWallet = newAddress;
            
            // ارسال به سرور
            await saveWalletToServer(newAddress);
            
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

// **بهبود handling callback response**
function handlePhantomResponse() {
    const urlParams = new URLSearchParams(window.location.search);
    const phantomAction = urlParams.get('phantom_action');
    
    if (phantomAction === 'connect') {
        console.log("📱 Processing Phantom callback...");
        
        // چک کردن error code
        const errorCode = urlParams.get('errorCode');
        const errorMessage = urlParams.get('errorMessage');
        
        if (errorCode) {
            console.error("Phantom connection error:", errorCode, errorMessage);
            showToast(`Connection failed: ${errorMessage || errorCode}`, "error");
            return;
        }
        
        // دریافت public key از callback
        let publicKey = urlParams.get('phantom_encryption_public_key') || 
                       urlParams.get('public_key') || 
                       urlParams.get('phantom_publicKey');
        
        console.log("🔑 Received publicKey from callback:", publicKey);
        
        if (publicKey) {
            try {
                // تأیید که آدرس Solana است (base58 format)
                if (publicKey.length >= 32 && publicKey.length <= 44 && !publicKey.startsWith('0x')) {
                    console.log('✅ Valid Solana address detected:', publicKey);
                    
                    // ذخیره آدرس
                    connectedWallet = publicKey;
                    tasksCompleted.wallet = true;
                    
                    // ارسال به سرور
                    saveWalletToServer(publicKey);
                    
                    // بروزرسانی UI
                    updateWalletUI();
                    updateTasksUI();
                    showToast('Wallet connected successfully!', 'success');
                    
                    // نمایش تأیید
                    setTimeout(() => {
                        alert(`Connected to Solana wallet:\n${publicKey}\n\nPlease verify this matches your Phantom wallet.`);
                    }, 1000);
                    
                } else {
                    throw new Error(`Invalid Solana address format: ${publicKey}`);
                }
                
            } catch (error) {
                console.error("Invalid public key:", error);
                showToast("Invalid wallet address received", "error");
            }
            
            // پاک کردن URL
            const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
            window.history.replaceState({}, document.title, cleanUrl);
            
        } else {
            console.error("No public key received from Phantom");
            showToast("No wallet address received. Please try again.", "error");
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
