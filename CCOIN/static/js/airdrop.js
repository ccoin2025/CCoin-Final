
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

function log(msg) {
    console.log('[Airdrop] ' + msg);
}

// **بهبود یافته: تابع چک کردن وضعیت از سرور**
async function checkAllStatusFromServer() {
    try {
        console.log('🔍 Checking all status from server...');
        
        // چک کردن وضعیت wallet و commission در یک بار
        const walletResponse = await fetch('/airdrop/commission_status');
        if (walletResponse.ok) {
            const walletData = await walletResponse.json();
            
            // Update wallet status
            if (walletData.wallet_connected && walletData.wallet_address) {
                connectedWallet = walletData.wallet_address;
                tasksCompleted.wallet = true;
                log('✅ Wallet status updated from server: ' + connectedWallet.substring(0, 8) + '...');
            } else {
                tasksCompleted.wallet = false;
                connectedWallet = null;
                log('❌ Wallet not connected');
            }
            
            // Update commission status
            tasksCompleted.pay = walletData.commission_paid;
            log('💰 Commission status: ' + (walletData.commission_paid ? 'Paid' : 'Not paid'));
        } else {
            log('⚠️ Failed to get wallet/commission status');
        }

        // چک کردن وضعیت referrals
        try {
            const referralResponse = await fetch('/airdrop/referral_status');
            if (referralResponse.ok) {
                const referralData = await referralResponse.json();
                tasksCompleted.invite = referralData.has_referrals;
                log('👥 Referral status: ' + (referralData.has_referrals ? `${referralData.referral_count} friends invited` : 'No friends invited'));
            } else {
                log('❌ Failed to get referral status');
            }
        } catch (error) {
            log('⚠️ Referral endpoint error: ' + error.message);
        }

        // چک کردن وضعیت tasks
        try {
            const tasksResponse = await fetch('/airdrop/tasks_status');
            if (tasksResponse.ok) {
                const tasksData = await tasksResponse.json();
                tasksCompleted.task = tasksData.tasks_completed;
                log('📋 Tasks status: ' + (tasksData.tasks_completed ? `${tasksData.completed_count}/${tasksData.total_tasks} completed` : 'No tasks completed'));
            } else {
                log('⚠️ Tasks endpoint not available, using initial value: ' + tasksCompleted.task);
            }
        } catch (error) {
            log('⚠️ Tasks endpoint error: ' + error.message);
        }

        // بروزرسانی UI
        updateAllTasksUI();

        // لاگ وضعیت نهایی
        log('📊 Final status: Wallet=' + tasksCompleted.wallet + ', Tasks=' + tasksCompleted.task + ', Invite=' + tasksCompleted.invite + ', Commission=' + tasksCompleted.pay);

    } catch (error) {
        console.error('Error checking status from server:', error);
        log('⚠️ Failed to check status from server: ' + error.message);
    }
}

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
        return btoa(String.fromCharCode.apply(null, data));
    }
}

// تابع شمارش معکوس اصلاح شده
function updateCountdown() {
    // تاریخ هدف: 1 ژانویه 2025 (یا هر تاریخ دلخواه)
    const targetDate = new Date('2025-01-01T00:00:00Z').getTime();
    const now = new Date().getTime();
    const distance = targetDate - now;

    if (distance > 0) {
        const days = Math.floor(distance / (1000 * 60 * 60 * 24));
        const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);

        // بروزرسانی المان‌های HTML
        const daysElement = document.getElementById('days');
        const hoursElement = document.getElementById('hours');
        const minutesElement = document.getElementById('minutes');
        const secondsElement = document.getElementById('seconds');

        if (daysElement) daysElement.textContent = days.toString().padStart(2, '0');
        if (hoursElement) hoursElement.textContent = hours.toString().padStart(2, '0');
        if (minutesElement) minutesElement.textContent = minutes.toString().padStart(2, '0');
        if (secondsElement) secondsElement.textContent = seconds.toString().padStart(2, '0');
        
        console.log(`⏰ Countdown: ${days}d ${hours}h ${minutes}m ${seconds}s`);
    } else {
        // تمام شد
        const elements = ['days', 'hours', 'minutes', 'seconds'];
        elements.forEach(id => {
            const element = document.getElementById(id);
            if (element) element.textContent = '00';
        });
        console.log('🎉 Countdown finished!');
    }
}

// شروع شمارش معکوس
document.addEventListener('DOMContentLoaded', function() {
    // اجرای فوری
    updateCountdown();
    
    // بروزرسانی هر ثانیه
    setInterval(updateCountdown, 1000);
    
    log('⏰ Countdown timer started');
});

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
            if (window.Telegram.WebApp.openTelegramLink) {
                window.Telegram.WebApp.openTelegramLink(url);
                return;
            }
            if (window.Telegram.WebApp.openLink) {
                window.Telegram.WebApp.openLink(url, { try_instant_view: false });
                return;
            }
            console.log("🔄 Falling back to window.open");
            window.open(url, '_blank');
        } catch (error) {
            console.error("Error opening Telegram link:", error);
            window.location.href = url;
        }
    } else {
        console.log("🌐 Standard browser environment");
        window.open(url, '_blank');
    }
}

// **UNCHANGED: کد اتصال wallet اصلی شما را حفظ می‌کنم**
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

// **جدید: Toggle wallet dropdown بدون نمایش آدرس**
function toggleWalletDropdown() {
    const dropdown = document.getElementById('wallet-dropdown-content');
    if (dropdown) {
        if (dropdown.classList.contains('show')) {
            dropdown.classList.remove('show');
            log('📱 Wallet dropdown closed');
        } else {
            dropdown.classList.add('show');
            log('📱 Wallet dropdown opened');
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
                wallet: "" // خالی کردن wallet
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

// **UNCHANGED: کد اتصال wallet اصلی شما را حفظ می‌کنم**
async function connectWallet() {
    handleWalletConnection();
}

// **اصلاح شده: پرداخت کمیسیون با چک دقیق wallet**
async function payCommission() {
    log('💰 Commission payment requested');
    
    try {
        // ابتدا چک کنیم که آیا کمیسیون قبلاً پرداخت شده
        const statusResponse = await fetch('/airdrop/commission_status');
        if (statusResponse.ok) {
            const statusData = await statusResponse.json();
            
            if (statusData.commission_paid) {
                showToast("Commission already paid!", "info");
                tasksCompleted.pay = true;
                updateCommissionUI();
                return;
            }
            
            // چک کردن اتصال wallet
            if (!statusData.wallet_connected || !statusData.wallet_address) {
                showToast("Please connect your wallet first", "error");
                log('❌ Wallet not connected - cannot proceed with commission payment');
                return;
            }
            
            // بروزرسانی وضعیت wallet
            connectedWallet = statusData.wallet_address;
            tasksCompleted.wallet = true;
            updateWalletUI();
        }

        // ساخت URL پرداخت کمیسیون
        const paymentUrl = `/commission/browser/pay?telegram_id=${USER_ID}`;
        
        if (isTelegramEnvironment()) {
            log('📱 Opening commission payment in external browser');
            showToast("Opening payment page...", "info");
            window.Telegram.WebApp.openLink(paymentUrl, { try_instant_view: false });
        } else {
            log('🌐 Opening commission payment in new window');
            window.open(paymentUrl, '_blank');
        }
        
    } catch (error) {
        log('❌ Error initiating commission payment: ' + error.message);
        showToast("Failed to initiate payment", "error");
    }
}

// **بازطراحی کامل: بروزرسانی UI همه tasks**
function updateAllTasksUI() {
    updateTaskCompleteUI();
    updateInviteFriendsUI();
    updateWalletUI();
    updateCommissionUI();
    updateClaimButton();
}

// **اصلاح شده: بروزرسانی UI task completion**
function updateTaskCompleteUI() {
    const taskButton = document.querySelector('#task-completion .task-button');
    const taskIcon = document.getElementById('tasks-icon');
    
    if (tasksCompleted.task) {
        taskButton?.classList.add('tasks-completed');
        if (taskIcon) {
            taskIcon.className = 'fas fa-check right-icon';
            taskIcon.style.color = '#00c853';
        }
        log('✅ Tasks UI updated: completed');
    } else {
        taskButton?.classList.remove('tasks-completed');
        if (taskIcon) {
            taskIcon.className = 'fas fa-chevron-right right-icon';
            taskIcon.style.color = '#aaa';
        }
        log('📋 Tasks UI updated: not completed');
    }
}

// **اصلاح شده: بروزرسانی UI دعوت دوستان**
function updateInviteFriendsUI() {
    const inviteButton = document.querySelector('#inviting-friends .task-button');
    const friendsIcon = document.getElementById('friends-icon');
    
    if (tasksCompleted.invite) {
        inviteButton?.classList.add('friends-invited');
        if (friendsIcon) {
            friendsIcon.className = 'fas fa-check right-icon';
            friendsIcon.style.color = '#00c853';
        }
        log('✅ Friends UI updated: invited');
    } else {
        inviteButton?.classList.remove('friends-invited');
        if (friendsIcon) {
            friendsIcon.className = 'fas fa-chevron-right right-icon';
            friendsIcon.style.color = '#aaa';
        }
        log('👥 Friends UI updated: not invited');
    }
}

// تابع بروزرسانی UI کیف پول
function updateWalletUI() {
    const walletButton = document.querySelector('.wallet-connect-button .task-button');
    const walletText = walletButton.querySelector('.task-text');
    const walletIcon = walletButton.querySelector('.right-icon');
    
    if (tasksCompleted.wallet && connectedWallet) {
        // نمایش آدرس کوتاه شده روی دکمه
        const shortAddress = connectedWallet.substring(0, 6) + '...' + connectedWallet.substring(connectedWallet.length - 4);
        walletText.textContent = `Connected: ${shortAddress}`;
        
        // تغییر آیکون به چک
        walletIcon.className = 'fas fa-check right-icon';
        
        // اضافه کردن کلاس connected
        walletButton.classList.add('wallet-connected');
        
        // نمایش status indicator
        const statusIndicator = document.querySelector('.wallet-status-indicator');
        if (statusIndicator) {
            statusIndicator.classList.add('connected');
        }
        
        log('✅ Wallet UI updated: ' + shortAddress);
    } else {
        // حالت disconnect
        walletText.textContent = 'Connect Wallet';
        walletIcon.className = 'fas fa-wallet right-icon';
        walletButton.classList.remove('wallet-connected');
        
        const statusIndicator = document.querySelector('.wallet-status-indicator');
        if (statusIndicator) {
            statusIndicator.classList.remove('connected');
        }
        
        log('🔄 Wallet UI reset to disconnected state');
    }
}

// **اصلاح شده: بروزرسانی UI کمیسیون**
function updateCommissionUI() {
    const commissionButton = document.querySelector('#pay-commission .task-button');
    const commissionIcon = document.getElementById('commission-icon');
    const commissionText = document.querySelector('#pay-commission .left-text');
    
    if (tasksCompleted.pay) {
        commissionButton?.classList.add('commission-paid');
        if (commissionIcon) {
            commissionIcon.className = 'fas fa-check right-icon';
            commissionIcon.style.color = '#00c853';
        }
        if (commissionText) {
            commissionText.textContent = 'Commission Paid';
        }
        log('✅ Commission UI updated: paid');
    } else {
        commissionButton?.classList.remove('commission-paid');
        if (commissionIcon) {
            commissionIcon.className = 'fas fa-chevron-right right-icon';
            commissionIcon.style.color = '#aaa';
        }
        if (commissionText) {
            commissionText.textContent = 'Pay for Commission';
        }
        log('💰 Commission UI updated: not paid');
    }
}

// **اصلاح شده: بروزرسانی دکمه Claim**
function updateClaimButton() {
    const claimBtn = document.getElementById('claim-btn');
    const allCompleted = tasksCompleted.task && tasksCompleted.invite && tasksCompleted.wallet && tasksCompleted.pay;
    
    if (claimBtn) {
        if (allCompleted) {
            claimBtn.disabled = false;
            claimBtn.textContent = 'Claim Airdrop';
            claimBtn.style.background = 'linear-gradient(45deg, #ffd700, #ffed4e)';
            log('🎉 Claim button enabled');
        } else {
            claimBtn.disabled = true;
            claimBtn.textContent = 'Complete All Tasks';
            claimBtn.style.background = 'rgba(255,255,255,0.1)';
            log('⏳ Claim button disabled - tasks incomplete');
        }
    }
}

// **اضافه شده: Toast notifications**
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 24px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    
    switch(type) {
        case 'success':
            toast.style.backgroundColor = '#4caf50';
            break;
        case 'error':
            toast.style.backgroundColor = '#f44336';
            break;
        case 'info':
        default:
            toast.style.backgroundColor = '#2196f3';
            break;
    }
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// **اضافه شده: CSS برای animations**
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
`;
document.head.appendChild(style);

// **اصلاح شده: Event listeners**
document.addEventListener('DOMContentLoaded', function() {
    // تنظیم countdown
    setInterval(updateCountdown, 1000);
    updateCountdown();
    
    // چک کردن وضعیت از سرور
    checkAllStatusFromServer();
    
    // تنظیم interval برای چک کردن وضعیت هر 30 ثانیه
    setInterval(checkAllStatusFromServer, 30000);
    
    // Event listener برای بستن dropdown وقتی کاربر جای دیگری کلیک کند
    document.addEventListener('click', function(event) {
        const dropdown = document.getElementById('wallet-dropdown-content');
        const walletButton = document.querySelector('#connect-wallet .task-button');
        
        if (dropdown && walletButton && 
            !dropdown.contains(event.target) && 
            !walletButton.contains(event.target)) {
            closeWalletDropdown();
        }
    });
    
    log('✅ Airdrop page initialized');
});

// **اضافه شده: Global functions برای استفاده در HTML**
window.handleWalletConnection = handleWalletConnection;
window.changeWallet = changeWallet;
window.disconnectWallet = disconnectWallet;
window.payCommission = payCommission;
window.showToast = showToast;
