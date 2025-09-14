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

// Enhanced Phantom detection
async function detectPhantomWallet() {
    console.log("🔍 Starting Phantom detection...");
    
    if (window.phantom?.solana?.isPhantom) {
        console.log("✅ Phantom detected via window.phantom.solana");
        phantomDetected = true;
        return window.phantom.solana;
    }
    
    if (window.solana?.isPhantom) {
        console.log("✅ Phantom detected via window.solana (legacy)");
        phantomDetected = true;
        return window.solana;
    }
    
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
    
    console.log("❌ Phantom wallet not found");
    phantomDetected = false;
    return null;
}

async function getPhantomProvider() {
    if (phantomProvider && phantomDetected) {
        return phantomProvider;
    }
    phantomProvider = await detectPhantomWallet();
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
    
    const provider = await getPhantomProvider();
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
            
            // **تغییر اصلی: هدایت مستقیم بدون مودال**
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

async function connectWalletDirect() {
    try {
        const response = await phantomProvider.connect();
        connectedWallet = response.publicKey.toString();
        
        const saveResponse = await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                wallet: connectedWallet
            })
        });
        
        if (saveResponse.ok) {
            tasksCompleted.wallet = true;
            updateWalletUI();
            updateTasksUI();
            showToast("Wallet connected successfully!", "success");
        } else {
            throw new Error("Failed to save wallet connection");
        }
        
    } catch (error) {
        console.error("Connection failed:", error);
        showToast("Wallet connection failed", "error");
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

// **باقی توابع بدون تغییر**
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
            addressElement.textContent = connectedWallet;
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
        const tasksIcon = document.getElementById('tasks-icon');
        if (tasksIcon) {
            tasksIcon.className = 'fas fa-check right-icon';
            document.getElementById('task-completion').classList.add('completed');
        }
    }
    
    // Update friends invitation
    if (tasksCompleted.invite) {
        const friendsIcon = document.getElementById('friends-icon');
        if (friendsIcon) {
            friendsIcon.className = 'fas fa-check right-icon';
            document.getElementById('inviting-friends').classList.add('completed');
        }
    }
    
    // Update commission payment
    if (tasksCompleted.pay) {
        const commissionIcon = document.getElementById('commission-icon');
        const commissionText = document.getElementById('commission-button-text');
        if (commissionIcon && commissionText) {
            commissionIcon.className = 'fas fa-check right-icon';
            commissionText.textContent = 'Commission Paid';
            document.getElementById('pay-commission').classList.add('completed');
        }
    }
    
    updateWalletUI();
}

async function handleTaskCompletion() {
    try {
        const response = await fetch('/earn/task_status', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            tasksCompleted.task = data.tasks_completed;
            updateTasksUI();
            
            if (data.tasks_completed) {
                showToast("Tasks completed!", "success");
            } else {
                showToast("Complete tasks first", "error");
                window.location.href = '/earn';
            }
        }
    } catch (error) {
        console.error("Error checking tasks:", error);
        showToast("Error checking tasks", "error");
    }
}

async function handleInviteCheck() {
    try {
        const response = await fetch('/airdrop/referral_status', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            tasksCompleted.invite = data.has_referrals;
            updateTasksUI();
            
            if (data.has_referrals) {
                showToast(`You have ${data.referral_count} referrals!`, "success");
            } else {
                showToast("Invite friends first", "error");
                window.location.href = '/friends';
            }
        }
    } catch (error) {
        console.error("Error checking referrals:", error);
        showToast("Error checking referrals", "error");
    }
}

async function changeWallet() {
    console.log("🔄 Changing wallet...");
    await disconnectWallet();
    setTimeout(() => {
        connectWallet();
    }, 500);
}

async function disconnectWallet() {
    try {
        // Disconnect from Phantom
        if (phantomProvider && phantomProvider.disconnect) {
            await phantomProvider.disconnect();
        }
        
        // Clear local state
        connectedWallet = null;
        tasksCompleted.wallet = false;
        
        // Update server
        const response = await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                wallet: ""
            })
        });
        
        if (response.ok) {
            updateWalletUI();
            updateTasksUI();
            toggleWalletDropdown();
            showToast("Wallet disconnected", "info");
        }
        
    } catch (error) {
        console.error("Disconnect error:", error);
        showToast("Error disconnecting wallet", "error");
    }
}

function showPhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.classList.add('show');
    }
}

function hidePhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.classList.remove('show');
    }
}

function showToast(message, type = 'info') {
    // Remove existing toasts
    const existingToasts = document.querySelectorAll('.toast');
    existingToasts.forEach(toast => toast.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    // Show toast
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    
    // Hide toast after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

// **بررسی وضعیت پرداخت commission در startup**
async function checkCommissionStatus() {
    try {
        const response = await fetch('/airdrop/commission_status', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            tasksCompleted.pay = data.commission_paid;
            connectedWallet = data.wallet_address || connectedWallet;
            tasksCompleted.wallet = data.wallet_connected;
            updateTasksUI();
        }
    } catch (error) {
        console.error("Error checking commission status:", error);
    }
}

// **بررسی query parameters برای callback از Phantom**
function checkPhantomCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    const phantomAction = urlParams.get('phantom_action');
    const publicKey = urlParams.get('public_key');
    
    if (phantomAction === 'connect' && publicKey) {
        console.log("✅ Phantom wallet connected via callback:", publicKey);
        connectedWallet = publicKey;
        tasksCompleted.wallet = true;
        
        // Save to server
        fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                wallet: publicKey
            })
        }).then(response => {
            if (response.ok) {
                updateWalletUI();
                updateTasksUI();
                showToast("Wallet connected successfully!", "success");
                
                // Clean URL
                window.history.replaceState({}, document.title, window.location.pathname);
            }
        });
    }
    
    // بررسی پرداخت commission
    const startapp = urlParams.get('startapp');
    if (startapp === 'commission_paid' || startapp === 'commission_check') {
        console.log("🔄 Checking commission payment status...");
        setTimeout(checkCommissionStatus, 1000);
    }
}

// **اجرای اولیه**
document.addEventListener('DOMContentLoaded', function() {
    console.log("🚀 Airdrop page loaded");
    
    // Initialize countdown
    updateCountdown();
    setInterval(updateCountdown, 1000);
    
    // Check initial state
    checkPhantomCallback();
    checkCommissionStatus();
    updateTasksUI();
    
    // Initialize phantom provider
    getPhantomProvider();
    
    // Close dropdown when clicking outside
    document.addEventListener('click', function(event) {
        const dropdown = document.querySelector('.wallet-dropdown');
        if (dropdown && !dropdown.contains(event.target)) {
            const dropdownContent = document.querySelector('.wallet-dropdown-content');
            if (dropdownContent) {
                dropdownContent.classList.remove('show');
            }
        }
    });
});

// **Export functions برای HTML**
window.handleTaskCompletion = handleTaskCompletion;
window.handleInviteCheck = handleInviteCheck;
window.toggleWalletDropdown = toggleWalletDropdown;
window.payCommission = payCommission;
window.connectWallet = connectWallet;
window.changeWallet = changeWallet;
window.disconnectWallet = disconnectWallet;
window.showPhantomModal = showPhantomModal;
window.hidePhantomModal = hidePhantomModal;
