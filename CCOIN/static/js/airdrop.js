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

// **تابع شمارش معکوس اصلاح شده**
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

// **تابع بروزرسانی UI کیف پول اصلاح شده**
function updateWalletUI() {
    const walletButtonText = document.getElementById('wallet-button-text');
    const walletIcon = document.getElementById('wallet-icon');
    const walletStatusIndicator = document.getElementById('wallet-status-indicator');
    const walletButton = document.querySelector('#connect-wallet .task-button');

    if (tasksCompleted.wallet && connectedWallet) {
        // نمایش آدرس کوتاه شده روی دکمه
        const shortAddress = connectedWallet.substring(0, 6) + '...' + connectedWallet.substring(connectedWallet.length - 4);
        
        if (walletButtonText) {
            walletButtonText.textContent = `Connected: ${shortAddress}`;
        }
        
        // تغییر آیکون به چک سبز
        if (walletIcon) {
            walletIcon.className = 'fas fa-check right-icon';
            walletIcon.style.color = '#28a745';
        }
        
        // اضافه کردن کلاس connected
        if (walletButton) {
            walletButton.classList.add('wallet-connected');
        }
        
        // نمایش status indicator سبز
        if (walletStatusIndicator) {
            walletStatusIndicator.classList.add('connected');
        }
        
        log('✅ Wallet UI updated: ' + shortAddress);
    } else {
        // حالت disconnect
        if (walletButtonText) {
            walletButtonText.textContent = 'Connect Wallet';
        }
        
        if (walletIcon) {
            walletIcon.className = 'fas fa-chevron-right right-icon';
            walletIcon.style.color = '#aaa';
        }
        
        if (walletButton) {
            walletButton.classList.remove('wallet-connected');
        }
        
        if (walletStatusIndicator) {
            walletStatusIndicator.classList.remove('connected');
        }
        
        log('🔄 Wallet UI reset to disconnected state');
    }
}

// **تابع بروزرسانی UI کمیسیون**
function updateCommissionUI() {
    const commissionIcon = document.getElementById('commission-icon');
    const commissionButton = document.querySelector('#pay-commission .task-button');

    if (tasksCompleted.pay) {
        if (commissionIcon) {
            commissionIcon.className = 'fas fa-check right-icon';
            commissionIcon.style.color = '#28a745';
        }
        if (commissionButton) {
            commissionButton.classList.add('commission-paid');
        }
        log('✅ Commission UI updated: paid');
    } else {
        if (commissionIcon) {
            commissionIcon.className = 'fas fa-chevron-right right-icon';
            commissionIcon.style.color = '#aaa';
        }
        if (commissionButton) {
            commissionButton.classList.remove('commission-paid');
        }
        log('💰 Commission UI updated: not paid');
    }
}

// **تابع بروزرسانی UI tasks**
function updateTaskCompleteUI() {
    const taskIcon = document.getElementById('tasks-icon');
    const taskButton = document.querySelector('#task-completion .task-button');

    if (tasksCompleted.task) {
        if (taskIcon) {
            taskIcon.className = 'fas fa-check right-icon';
            taskIcon.style.color = '#28a745';
        }
        if (taskButton) {
            taskButton.classList.add('tasks-completed');
        }
        log('✅ Tasks UI updated: completed');
    } else {
        if (taskIcon) {
            taskIcon.className = 'fas fa-chevron-right right-icon';
            taskIcon.style.color = '#aaa';
        }
        if (taskButton) {
            taskButton.classList.remove('tasks-completed');
        }
        log('📋 Tasks UI updated: not completed');
    }
}

// **تابع بروزرسانی UI دعوت دوستان**
function updateInviteFriendsUI() {
    const friendsIcon = document.getElementById('friends-icon');
    const friendsButton = document.querySelector('#inviting-friends .task-button');

    if (tasksCompleted.invite) {
        if (friendsIcon) {
            friendsIcon.className = 'fas fa-check right-icon';
            friendsIcon.style.color = '#28a745';
        }
        if (friendsButton) {
            friendsButton.classList.add('friends-invited');
        }
        log('✅ Friends UI updated: invited');
    } else {
        if (friendsIcon) {
            friendsIcon.className = 'fas fa-chevron-right right-icon';
            friendsIcon.style.color = '#aaa';
        }
        if (friendsButton) {
            friendsButton.classList.remove('friends-invited');
        }
        log('👥 Friends UI updated: not invited');
    }
}

// **تابع بروزرسانی دکمه claim**
function updateClaimButton() {
    const claimButton = document.getElementById('claim-button');
    if (!claimButton) return;

    const allCompleted = tasksCompleted.task && tasksCompleted.invite && tasksCompleted.wallet && tasksCompleted.pay;
    
    if (allCompleted) {
        claimButton.disabled = false;
        claimButton.textContent = 'Claim Airdrop';
        claimButton.style.background = 'linear-gradient(45deg, #ffd700, #ffed4e)';
        claimButton.style.color = '#000';
    } else {
        claimButton.disabled = true;
        claimButton.textContent = 'Complete all tasks to claim';
        claimButton.style.background = 'rgba(255, 255, 255, 0.1)';
        claimButton.style.color = 'rgba(255, 255, 255, 0.5)';
    }
}

// **تابع بروزرسانی همه UI ها**
function updateAllTasksUI() {
    updateTaskCompleteUI();
    updateInviteFriendsUI();
    updateWalletUI();
    updateCommissionUI();
    updateClaimButton();
}

// **تابع چک وضعیت از سرور**
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
        }

        // چک کردن وضعیت referrals
        try {
            const referralResponse = await fetch('/airdrop/referral_status');
            if (referralResponse.ok) {
                const referralData = await referralResponse.json();
                tasksCompleted.invite = referralData.has_referrals;
                log('👥 Referral status: ' + (referralData.has_referrals ? `${referralData.referral_count} friends invited` : 'No friends invited'));
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
            }
        } catch (error) {
            log('⚠️ Tasks endpoint error: ' + error.message);
        }

        // بروزرسانی UI
        updateAllTasksUI();

        log('📊 Final status: Wallet=' + tasksCompleted.wallet + ', Tasks=' + tasksCompleted.task + ', Invite=' + tasksCompleted.invite + ', Commission=' + tasksCompleted.pay);

    } catch (error) {
        console.error('Error checking status from server:', error);
        log('⚠️ Failed to check status from server: ' + error.message);
    }
}

// **تشخیص محیط Telegram**
function isTelegramEnvironment() {
    return window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData;
}

// **اتصال wallet**
async function handleWalletConnection() {
    log('🔗 Wallet connection requested');

    // اگر wallet متصل است، toggle dropdown
    if (tasksCompleted.wallet && connectedWallet) {
        toggleWalletDropdown();
        return;
    }

    // اگر wallet متصل نیست، شروع فرآیند اتصال
    try {
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

// **Toggle wallet dropdown**
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

// **تغییر wallet**
function changeWallet() {
    log('🔄 Changing wallet...');
    closeWalletDropdown();
    tasksCompleted.wallet = false;
    connectedWallet = null;
    updateWalletUI();
    handleWalletConnection();
}

// **قطع اتصال wallet**
async function disconnectWallet() {
    try {
        log('🔌 Disconnecting wallet...');
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

// **بستن dropdown**
function closeWalletDropdown() {
    const dropdown = document.getElementById('wallet-dropdown-content');
    if (dropdown) {
        dropdown.classList.remove('show');
    }
}

// **پرداخت کمیسیون**
async function handleCommissionPayment() {
    log('💰 Commission payment requested');
    try {
        const statusResponse = await fetch('/airdrop/commission_status');
        if (statusResponse.ok) {
            const statusData = await statusResponse.json();

            if (statusData.commission_paid) {
                showToast("Commission already paid!", "info");
                tasksCompleted.pay = true;
                updateCommissionUI();
                return;
            }

            if (!statusData.wallet_connected || !statusData.wallet_address) {
                showToast("Please connect your wallet first", "error");
                log('❌ Wallet not connected - cannot proceed with commission payment');
                return;
            }

            connectedWallet = statusData.wallet_address;
            tasksCompleted.wallet = true;
            updateWalletUI();
        }

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

// **Handlers برای دکمه‌های اصلی**
function handleTaskCompletion() {
    window.location.href = `/earn?telegram_id=${USER_ID}`;
}

function handleInviteCheck() {
    window.location.href = `/friends?telegram_id=${USER_ID}`;
}

// **Toast notifications**
function showToast(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 100);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => document.body.removeChild(toast), 300);
    }, duration);
}

// **شروع برنامه**
document.addEventListener('DOMContentLoaded', function() {
    log('🚀 Airdrop page loaded');
    
    // شروع شمارش معکوس
    updateCountdown();
    setInterval(updateCountdown, 1000);
    log('⏰ Countdown timer started');
    
    // چک کردن وضعیت از سرور
    checkAllStatusFromServer();
    
    // بروزرسانی UI اولیه
    updateAllTasksUI();
    
    // بستن dropdown با کلیک خارج از آن
    document.addEventListener('click', function(event) {
        const dropdown = document.querySelector('.wallet-dropdown');
        if (dropdown && !dropdown.contains(event.target)) {
            closeWalletDropdown();
        }
    });
    
    log('✅ Airdrop initialization complete');
});
