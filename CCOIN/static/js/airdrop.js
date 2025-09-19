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

// **جدید: تابع چک کردن وضعیت از سرور**
async function checkAllStatusFromServer() {
    try {
        // چک کردن وضعیت wallet
        const walletResponse = await fetch('/airdrop/check_wallet_status');
        if (walletResponse.ok) {
            const walletData = await walletResponse.json();
            if (walletData.connected && walletData.wallet_address) {
                connectedWallet = walletData.wallet_address;
                tasksCompleted.wallet = true;
                log('✅ Wallet status updated from server');
            }
        }

        // چک کردن وضعیت commission
        const commissionResponse = await fetch('/airdrop/commission_status');
        if (commissionResponse.ok) {
            const commissionData = await commissionResponse.json();
            tasksCompleted.pay = commissionData.commission_paid;
            log('✅ Commission status updated from server');
        }

        // چک کردن وضعیت referrals
        const referralResponse = await fetch('/airdrop/referral_status');
        if (referralResponse.ok) {
            const referralData = await referralResponse.json();
            tasksCompleted.invite = referralData.has_referrals;
            log('✅ Referral status updated from server');
        }

        // بروزرسانی UI
        updateAllTasksUI();
        
    } catch (error) {
        console.error('Error checking status from server:', error);
        log('⚠️ Failed to check status from server: ' + error.message);
    }
}

// **Fix: BS58 utility functions**
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

// **Fixed: Countdown Timer**
function updateCountdown() {
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
    }
}

function log(msg) {
    console.log('[Airdrop] ' + msg);
}

// **اصلاح شده: تشخیص محیط Telegram**
function isTelegramEnvironment() {
    return window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData;
}

// **جدید: نمایش modal برای اتصال wallet**
function showPhantomModal() {
    const modal = document.getElementById('phantomModal');
    if (modal) {
        modal.classList.add('show');
    }
}

function closePhantomModal() {
    const modal = document.getElementById('phantomModal');
    if (modal) {
        modal.classList.remove('show');
    }
}

// **بازطراحی: handleWalletConnection**
async function handleWalletConnection() {
    log('🔗 Wallet connection requested');
    
    // اگر wallet متصل است، toggle dropdown
    if (tasksCompleted.wallet && connectedWallet) {
        toggleWalletDropdown();
        return;
    }

    // اگر wallet متصل نیست، شروع فرآیند اتصال
    try {
        // هدایت به صفحه اتصال wallet
        const connectUrl = `/wallet/browser/connect?telegram_id=${USER_ID}`;
        
        if (isTelegramEnvironment()) {
            log('📱 Opening wallet connection in external browser');
            window.Telegram.WebApp.openLink(connectUrl, { try_instant_view: false });
        } else {
            log('🌐 Opening wallet connection in new window');
            window.open(connectUrl, '_blank');
        }
        
        showToast("Opening wallet connection...", "info");
        
    } catch (error) {
        log('❌ Error opening wallet connection: ' + error.message);
        showToast("Failed to open wallet connection", "error");
    }
}

// **جدید: Toggle wallet dropdown**
function toggleWalletDropdown() {
    const dropdown = document.getElementById('wallet-dropdown-content');
    const addressElement = document.getElementById('dropdown-wallet-address');
    
    if (dropdown) {
        if (dropdown.classList.contains('show')) {
            dropdown.classList.remove('show');
        } else {
            // نمایش آدرس wallet
            if (addressElement && connectedWallet) {
                addressElement.textContent = connectedWallet;
            }
            dropdown.classList.add('show');
        }
    }
}

// **جدید: تغییر wallet**
function changeWallet() {
    log('🔄 Changing wallet...');
    closeWalletDropdown();
    
    // ریست کردن وضعیت wallet
    tasksCompleted.wallet = false;
    connectedWallet = null;
    
    // بروزرسانی UI
    updateWalletUI();
    
    // شروع فرآیند اتصال جدید
    handleWalletConnection();
}

// **جدید: قطع اتصال wallet**
async function disconnectWallet() {
    try {
        log('🔌 Disconnecting wallet...');
        
        const response = await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                wallet: ""  // خالی کردن wallet
            })
        });

        if (response.ok) {
            tasksCompleted.wallet = false;
            connectedWallet = null;
            
            updateWalletUI();
            closeWalletDropdown();
            
            showToast("Wallet disconnected successfully", "success");
            log('✅ Wallet disconnected successfully');
        } else {
            throw new Error('Failed to disconnect wallet');
        }
        
    } catch (error) {
        log('❌ Error disconnecting wallet: ' + error.message);
        showToast("Failed to disconnect wallet", "error");
    }
}

// **جدید: بستن dropdown**
function closeWalletDropdown() {
    const dropdown = document.getElementById('wallet-dropdown-content');
    if (dropdown) {
        dropdown.classList.remove('show');
    }
}

// **اصلاح شده: پرداخت کمیسیون**
async function payCommission() {
    if (!connectedWallet) {
        showToast("Please connect wallet first", "error");
        return;
    }

    if (tasksCompleted.pay) {
        showToast("Commission already paid!", "info");
        return;
    }

    log('💰 Starting commission payment process...');

    try {
        const commissionButton = document.getElementById('commission-button');
        const commissionIcon = document.getElementById('commission-icon');

        if (commissionButton && commissionIcon) {
            commissionButton.classList.add('loading');
            commissionIcon.className = 'fas fa-spinner right-icon';
        }

        const commissionUrl = `/commission/pay?telegram_id=${USER_ID}`;

        if (isTelegramEnvironment()) {
            log('📱 Telegram environment - opening external payment page');
            window.Telegram.WebApp.openLink(commissionUrl, { try_instant_view: false });
        } else {
            log('🌐 Browser environment - opening in new tab');
            window.open(commissionUrl, '_blank');
        }

        showToast("Opening payment page...", "info");

        setTimeout(() => {
            if (commissionButton && commissionIcon) {
                commissionButton.classList.remove('loading');
                commissionIcon.className = 'fas fa-chevron-right right-icon';
            }
        }, 3000);

    } catch (error) {
        log('❌ Commission payment error: ' + error.message);
        showToast("Failed to open payment page", "error");
    }
}

// **اصلاح شده: updateWalletUI**
function updateWalletUI() {
    const button = document.querySelector('#connect-wallet .task-button');
    const leftText = button.querySelector('.left-text');
    const rightIcon = button.querySelector('.right-icon');
    const statusIndicator = button.querySelector('.wallet-status-indicator');
    const taskBox = document.querySelector('#connect-wallet .task-box');

    if (tasksCompleted.wallet && connectedWallet) {
        leftText.textContent = 'Wallet Connected';
        rightIcon.className = 'fas fa-check right-icon';
        button.classList.add('wallet-connected');
        button.classList.add('completed');
        statusIndicator.classList.add('connected');
        taskBox.classList.add('completed');

        log('✅ Wallet UI updated to connected state');
    } else {
        leftText.textContent = 'Connect Wallet';
        rightIcon.className = 'fas fa-chevron-right right-icon';
        button.classList.remove('wallet-connected');
        button.classList.remove('completed');
        statusIndicator.classList.remove('connected');
        taskBox.classList.remove('completed');

        log('🔌 Wallet UI updated to disconnected state');
    }
}

// **اصلاح شده: updateTasksUI**
function updateTasksUI() {
    // Update tasks completion
    const taskButton = document.querySelector('#task-completion .task-button');
    const taskLeftText = taskButton.querySelector('.left-text');
    const taskRightIcon = taskButton.querySelector('.right-icon');
    const taskBox = document.querySelector('#task-completion .task-box');

    if (tasksCompleted.task) {
        taskLeftText.textContent = 'Tasks Completed';
        taskRightIcon.className = 'fas fa-check right-icon';
        taskButton.classList.add('tasks-completed');
        taskButton.classList.add('completed');
        taskBox.classList.add('completed');
    } else {
        taskLeftText.textContent = 'Tasks Completion';
        taskRightIcon.className = 'fas fa-chevron-right right-icon';
        taskButton.classList.remove('tasks-completed');
        taskButton.classList.remove('completed');
        taskBox.classList.remove('completed');
    }

    // Update referral completion
    const inviteButton = document.querySelector('#inviting-friends .task-button');
    const inviteLeftText = inviteButton.querySelector('.left-text');
    const inviteRightIcon = inviteButton.querySelector('.right-icon');
    const inviteBox = document.querySelector('#inviting-friends .task-box');

    if (tasksCompleted.invite) {
        inviteLeftText.textContent = 'Friends Invited';
        inviteRightIcon.className = 'fas fa-check right-icon';
        inviteButton.classList.add('friends-invited');
        inviteButton.classList.add('completed');
        inviteBox.classList.add('completed');
    } else {
        inviteLeftText.textContent = 'Inviting Friends';
        inviteRightIcon.className = 'fas fa-chevron-right right-icon';
        inviteButton.classList.remove('friends-invited');
        inviteButton.classList.remove('completed');
        inviteBox.classList.remove('completed');
    }

    // Update commission payment
    const payButton = document.querySelector('#pay-commission .task-button');
    const payLeftText = payButton.querySelector('.left-text');
    const payRightIcon = payButton.querySelector('.right-icon');
    const payBox = document.querySelector('#pay-commission .task-box');

    if (tasksCompleted.pay) {
        payLeftText.textContent = 'Commission Paid';
        payRightIcon.className = 'fas fa-check right-icon';
        payButton.classList.add('commission-paid');
        payButton.classList.add('completed');
        payBox.classList.add('completed');
    } else {
        payLeftText.textContent = 'Pay Commission';
        payRightIcon.className = 'fas fa-chevron-right right-icon';
        payButton.classList.remove('commission-paid');
        payButton.classList.remove('completed');
        payBox.classList.remove('completed');
    }

    updateProgress();
}

// **جدید: تابع کلی برای بروزرسانی همه UI**
function updateAllTasksUI() {
    updateWalletUI();
    updateTasksUI();
    log('🔄 All UI elements updated');
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
            if (document.body.contains(toast)) {
                document.body.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

// **جدید: checking wallet connection success از URL**
function handleWalletConnectionSuccess() {
    const urlParams = new URLSearchParams(window.location.search);
    const walletConnected = urlParams.get('wallet_connected');
    const walletAddress = urlParams.get('wallet_address');

    if (walletConnected === 'true' && walletAddress) {
        log('✅ Wallet connection successful from URL: ' + walletAddress);

        if (walletAddress.length >= 32 && walletAddress.length <= 44 && !walletAddress.startsWith('0x')) {
            connectedWallet = walletAddress;
            tasksCompleted.wallet = true;

            updateAllTasksUI();
            showToast('Wallet connected successfully!', 'success');

            // پاک کردن URL
            const cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
            window.history.replaceState({}, document.title, cleanUrl);
        }
    }
}

// **Handler functions**
async function handleTaskCompletion() {
    if (tasksCompleted.task) {
        showToast("Tasks already completed!", "info");
        return;
    }
    window.location.href = "/earn";
}

async function handleInviteCheck() {
    if (tasksCompleted.invite) {
        showToast("Friends already invited!", "info");
        return;
    }
    window.location.href = "/friends";
}

// **Event listeners**
document.addEventListener('click', function(event) {
    const walletDropdown = document.getElementById('wallet-dropdown-content');
    const walletButton = document.querySelector('#connect-wallet .task-button');
    
    if (walletDropdown && walletDropdown.classList.contains('show')) {
        if (!walletButton.contains(event.target) && !walletDropdown.contains(event.target)) {
            closeWalletDropdown();
        }
    }
});

// **Initialization**
document.addEventListener('DOMContentLoaded', function() {
    log('🚀 Airdrop page initialized');
    
    // چک کردن URL برای wallet connection success
    handleWalletConnectionSuccess();
    
    // چک کردن وضعیت از سرور
    checkAllStatusFromServer();
    
    // بروزرسانی UI اولیه
    updateAllTasksUI();
    
    // شروع countdown
    updateCountdown();
    setInterval(updateCountdown, 1000);
    
    // چک کردن وضعیت هر 30 ثانیه
    setInterval(checkAllStatusFromServer, 30000);
    
    log('✅ All initialization completed');
});
