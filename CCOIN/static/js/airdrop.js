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

// **جدید: نمایش modal برای اتصال wallet**
function showPhantomModal() {
    const modal = document.getElementById('phantomModal');
    const connectLink = document.getElementById('phantomConnectLink');
    
    // تنظیم لینک اتصال
    connectLink.href = `/wallet/connect?telegram_id=${USER_ID}`;
    
    modal.classList.add('show');
}

// **جدید: بستن modal**
function closePhantomModal() {
    const modal = document.getElementById('phantomModal');
    modal.classList.remove('show');
}

// **کلیک خارج از modal برای بستن**
document.addEventListener('click', function(event) {
    const modal = document.getElementById('phantomModal');
    if (event.target === modal) {
        closePhantomModal();
    }
});

// **بازطراحی: اتصال wallet با modal**
async function handleWalletConnection() {
    // اگر wallet متصل است، فقط نمایش اطلاعات
    if (tasksCompleted.wallet) {
        showToast(`Already connected: ${connectedWallet.slice(0,6)}...${connectedWallet.slice(-6)}`, "info");
        return;
    }

    // نمایش modal اتصال
    showPhantomModal();
}

// **بازطراحی: connectWallet با modal**
async function connectWallet() {
    // این تابع حالا توسط modal صدا زده می‌شود
    showPhantomModal();
}

// **اصلاح شده: پرداخت کمیسیون (بدون تغییر)**
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

// **اصلاح شده: updateWalletUI**
function updateWalletUI() {
    const button = document.querySelector('#connect-wallet .task-button');
    const leftText = button.querySelector('.left-text');
    const rightIcon = button.querySelector('.right-icon');
    const statusIndicator = button.querySelector('.wallet-status-indicator');

    if (tasksCompleted.wallet && connectedWallet) {
        leftText.textContent = 'Wallet Connected';
        rightIcon.className = 'fas fa-check right-icon';
        button.classList.add('wallet-connected');
        button.classList.add('completed');
        statusIndicator.classList.add('connected');
        document.querySelector('#connect-wallet .task-box').classList.add('completed');

        // نمایش آدرس در متن
        leftText.innerHTML = `Wallet Connected<br><small style="font-size:10px; opacity:0.7;">${connectedWallet.slice(0,6)}...${connectedWallet.slice(-6)}</small>`;
    } else {
        leftText.textContent = 'Connect Wallet';
        rightIcon.className = 'fas fa-chevron-right right-icon';
        button.classList.remove('wallet-connected');
        button.classList.remove('completed');
        statusIndicator.classList.remove('connected');
        document.querySelector('#connect-wallet .task-box').classList.remove('completed');
    }
}

function updateTasksUI() {
    // Update tasks completion
    if (tasksCompleted.task) {
        const taskButton = document.querySelector('#task-completion .task-button');
        const taskLeftText = taskButton.querySelector('.left-text');
        const taskRightIcon = taskButton.querySelector('.right-icon');

        taskLeftText.textContent = 'Tasks Completed';
        taskRightIcon.className = 'fas fa-check right-icon';
        taskButton.classList.add('completed');
        document.querySelector('#task-completion .task-box').classList.add('completed');
    }

    // Update referral completion
    if (tasksCompleted.invite) {
        const inviteButton = document.querySelector('#inviting-friends .task-button');
        const inviteLeftText = inviteButton.querySelector('.left-text');
        const inviteRightIcon = inviteButton.querySelector('.right-icon');

        inviteLeftText.textContent = 'Friends Invited';
        inviteRightIcon.className = 'fas fa-check right-icon';
        inviteButton.classList.add('completed');
        document.querySelector('#inviting-friends .task-box').classList.add('completed');
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

// **handling wallet connection success از URL**
function handleWalletConnectionSuccess() {
    const urlParams = new URLSearchParams(window.location.search);
    const walletConnected = urlParams.get('wallet_connected');
    const walletAddress = urlParams.get('wallet_address');

    if (walletConnected === 'true' && walletAddress) {
        console.log("✅ Wallet connection successful from external page:", walletAddress);

        // تأیید آدرس Solana
        if (walletAddress.length >= 32 && walletAddress.length <= 44 && !walletAddress.startsWith('0x')) {
            connectedWallet = walletAddress;
            tasksCompleted.wallet = true;

            updateWalletUI();
            updateTasksUI();
            showToast('Wallet connected successfully!', 'success');

            // پاک کردن URL
            const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
            window.history.replaceState({}, document.title, cleanUrl);
        } else {
            console.error("Invalid wallet address format:", walletAddress);
            showToast("Invalid wallet address received", "error");
        }
    }
}

// **Handler functions for other tasks**
async function handleTaskCompletion() {
    if (tasksCompleted.task) {
        showToast("Tasks already completed!", "info");
        return;
    }
    // هدایت به صفحه tasks
    window.location.href = "/earn";
}

async function handleInviteCheck() {
    if (tasksCompleted.invite) {
        showToast("Friends already invited!", "info");
        return;
    }
    // هدایت به صفحه friends
    window.location.href = "/friends";
}

// **Check status periodically**
async function checkAllStatus() {
    try {
        // Check wallet status
        const walletResponse = await fetch(`/api/wallet/status?telegram_id=${USER_ID}`);
        if (walletResponse.ok) {
            const walletData = await walletResponse.json();
            if (walletData.connected && walletData.address) {
                connectedWallet = walletData.address;
                tasksCompleted.wallet = true;
            }
        }

        // Check tasks status
        const tasksResponse = await fetch(`/api/tasks/status?telegram_id=${USER_ID}`);
        if (tasksResponse.ok) {
            const tasksData = await tasksResponse.json();
            tasksCompleted.task = tasksData.tasks_completed;
            tasksCompleted.invite = tasksData.friends_invited;
        }

        // Check commission status
        const commissionResponse = await fetch(`/api/commission/status?telegram_id=${USER_ID}`);
        if (commissionResponse.ok) {
            const commissionData = await commissionResponse.json();
            tasksCompleted.pay = commissionData.paid;
        }

        updateWalletUI();
        updateTasksUI();

    } catch (error) {
        console.error("Error checking status:", error);
    }
}

// **اجرای اولیه**
document.addEventListener('DOMContentLoaded', function() {
    console.log("🚀 Airdrop page loaded");
    
    // Set countdown timer
    setInterval(updateCountdown, 1000);
    updateCountdown();

    // Check URL for wallet connection success
    handleWalletConnectionSuccess();

    // Initial UI update
    updateWalletUI();
    updateTasksUI();

    // Check status every 30 seconds
    setInterval(checkAllStatus, 30000);
    
    // Initial status check
    checkAllStatus();
});
