/* ---------- BS58 fallback (moved from inline) ---------- */
if (typeof bs58 === 'undefined') {
    window.bs58 = {
        encode: function (data) {
            try {
                return btoa(String.fromCharCode.apply(null, data));
            } catch (e) {
                // safer fallback for large arrays
                let s = '';
                for (let i = 0; i < data.length; i++) s += String.fromCharCode(data[i]);
                return btoa(s);
            }
        },
        decode: function (str) {
            const binary = atob(str);
            const arr = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) arr[i] = binary.charCodeAt(i);
            return arr;
        }
    };
}

// ensureBS58 (keeps original behavior if cdn loaded)
window.ensureBS58 = function () {
    if (typeof bs58 !== 'undefined') {
        window.bs58 = bs58;
        return true;
    }
    if (typeof window.bs58 !== 'undefined') {
        return true;
    }
    console.warn('BS58 library not available, using fallback');
    return false;
};

/* ---------- Begin content from 00001.js (with main_ prefixes) ---------- */

// تشخیص وجود APP_CONFIG و ایجاد fallback در صورت عدم وجود
if (typeof window.APP_CONFIG === 'undefined') {
    console.error('❌ APP_CONFIG not found! Using fallback values.');
    window.APP_CONFIG = {
        USER_ID: '123456789',
        SOLANA_RPC_URL: 'https://api.devnet.solana.com',
        COMMISSION_AMOUNT: 0.01,
        ADMIN_WALLET: '',
        INITIAL_TASKS_COMPLETED: false,
        INITIAL_INVITED_FRIENDS: false,
        INITIAL_WALLET_CONNECTED: false,
        INITIAL_COMMISSION_PAID: false,
        INITIAL_WALLET_ADDRESS: ''
    };
}

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
let countdownInterval = null;

function log(msg) {
    console.log('[Airdrop] ' + msg);
}

function main_updateCountdown() {
    try {
        const targetDate = new Date('2026-01-24T23:59:59Z').getTime();
        const now = new Date().getTime();
        const distance = targetDate - now;

        if (distance > 0) {
            const days = Math.floor(distance / (1000 * 60 * 60 * 24));
            const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((distance % (1000 * 60)) / 1000);

            const daysElement = document.getElementById('days');
            const hoursElement = document.getElementById('hours');
            const minutesElement = document.getElementById('minutes');
            const secondsElement = document.getElementById('seconds');

            if (daysElement) {
                const newValue = days.toString().padStart(2, '0');
                if (daysElement.textContent !== newValue) {
                    daysElement.classList.add('flip');
                    setTimeout(() => {
                        daysElement.textContent = newValue;
                        daysElement.classList.remove('flip');
                    }, 150);
                } else {
                    daysElement.textContent = newValue;
                }
            }

            if (hoursElement) {
                const newValue = hours.toString().padStart(2, '0');
                if (hoursElement.textContent !== newValue) {
                    hoursElement.classList.add('flip');
                    setTimeout(() => {
                        hoursElement.textContent = newValue;
                        hoursElement.classList.remove('flip');
                    }, 150);
                } else {
                    hoursElement.textContent = newValue;
                }
            }

            if (minutesElement) {
                const newValue = minutes.toString().padStart(2, '0');
                if (minutesElement.textContent !== newValue) {
                    minutesElement.classList.add('flip');
                    setTimeout(() => {
                        minutesElement.textContent = newValue;
                        minutesElement.classList.remove('flip');
                    }, 150);
                } else {
                    minutesElement.textContent = newValue;
                }
            }

            if (secondsElement) {
                const newValue = seconds.toString().padStart(2, '0');
                if (secondsElement.textContent !== newValue) {
                    secondsElement.classList.add('flip');
                    setTimeout(() => {
                        secondsElement.textContent = newValue;
                        secondsElement.classList.remove('flip');
                    }, 150);
                } else {
                    secondsElement.textContent = newValue;
                }
            }

            if (seconds % 30 === 0) {
                console.log(`⏰ Countdown: ${days}d ${hours}h ${minutes}m ${seconds}s`);
            }

        } else {
            const elements = ['days', 'hours', 'minutes', 'seconds'];
            elements.forEach(id => {
                const element = document.getElementById(id);
                if (element) element.textContent = '00';
            });

            console.log('🎉 Countdown finished!');

            const countdownTitle = document.querySelector('.countdown-title');
            if (countdownTitle) {
                countdownTitle.textContent = '🎉 Airdrop is LIVE!';
                countdownTitle.style.color = '#ffd700';
            }

            if (countdownInterval) {
                clearInterval(countdownInterval);
                countdownInterval = null;
            }
        }

    } catch (error) {
        console.error('❌ Countdown error:', error);
    }
}

function main_startCountdown() {
    log('⏰ Starting countdown timer...');
    
    main_updateCountdown();
    
    if (countdownInterval) {
        clearInterval(countdownInterval);
    }
    countdownInterval = setInterval(main_updateCountdown, 1000);
    
    log('✅ Countdown timer started successfully');
}

function main_stopCountdown() {
    if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
        log('⏹️ Countdown timer stopped');
    }
}

function main_updateWalletUI() {
    const walletButtonText = document.getElementById('wallet-button-text');
    const walletIcon = document.getElementById('wallet-icon');
    const walletStatusIndicator = document.getElementById('wallet-status-indicator');
    const walletButton = document.querySelector('#connect-wallet .task-button');

    if (tasksCompleted.wallet && connectedWallet) {
        const shortAddress = connectedWallet.substring(0, 6) + '...' + connectedWallet.substring(connectedWallet.length - 4);
        
        if (walletButtonText) {
            walletButtonText.textContent = `Connected: ${shortAddress}`;
            walletButtonText.style.color = '#ffffff';
        }

        if (walletIcon) {
            walletIcon.className = 'fas fa-check right-icon';
            walletIcon.style.color = '#28a745';
        }

        if (walletButton) {
            walletButton.classList.add('wallet-connected');
        }

        if (walletStatusIndicator) {
            walletStatusIndicator.classList.add('connected');
        }

        log('✅ Wallet UI updated: ' + shortAddress);

    } else {
        if (walletButtonText) {
            walletButtonText.textContent = 'Connect Wallet';
            walletButtonText.style.color = '#ffffff';
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

function main_updateCommissionUI() {
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

function main_updateTaskCompleteUI() {
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

function main_updateInviteFriendsUI() {
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

function main_updateClaimButton() {
    const claimButton = document.getElementById('claimBtn');
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

function main_updateAllTasksUI() {
    main_updateTaskCompleteUI();
    main_updateInviteFriendsUI();
    main_updateWalletUI();
    main_updateCommissionUI();
    main_updateClaimButton();
}

function main_showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 100);

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => document.body.removeChild(toast), 300);
    }, 3000);
}

async function main_detectPhantom() {
    try {
        if (window.solana && window.solana.isPhantom) {
            phantomProvider = window.solana;
            phantomDetected = true;
            log('✅ Phantom Wallet detected');
            return true;
        } else {
            log('❌ Phantom Wallet not detected');
            return false;
        }
    } catch (error) {
        log('❌ Error detecting Phantom: ' + error.message);
        return false;
    }
}

async function main_handleWalletConnection() {
    try {
        log('🔗 Initiating wallet connection...');

        const walletUrl = `/wallet/browser/connect?telegram_id=${USER_ID}`;
        log('Opening wallet connection page: ' + walletUrl);

        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.openLink(walletUrl);
        } else {
            window.open(walletUrl, '_blank');
        }

    } catch (error) {
        log('❌ Wallet connection error: ' + error.message);
        main_showToast('Failed to open wallet connection: ' + error.message, 'error');
    }
}

async function main_sendWalletToServer(walletAddress) {
    try {
        log(`📤 Sending wallet to server: ${walletAddress || 'disconnect'}`);

        const response = await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                wallet_address: walletAddress
            })
        });

        if (!response.ok) {
            throw new Error('Server error: ' + response.statusText);
        }

        const data = await response.json();
        log('✅ Server response: ' + JSON.stringify(data));

        return data;

    } catch (error) {
        log('❌ Error sending wallet to server: ' + error.message);
        throw error;
    }
}

async function main_disconnectWallet() {
    try {
        log('🔌 Disconnecting wallet...');

        if (phantomProvider) {
            try { await phantomProvider.disconnect(); } catch(e) { /* ignore */ }
        }

        await main_sendWalletToServer(null);

        connectedWallet = '';
        tasksCompleted.wallet = false;

        main_updateWalletUI();
        main_updateClaimButton();

        main_showToast('Wallet disconnected successfully!', 'success');
        log('✅ Wallet disconnected');

    } catch (error) {
        log('❌ Wallet disconnection failed: ' + error.message);
        main_showToast('Failed to disconnect wallet: ' + error.message, 'error');
    }
}

async function main_handleCommissionPayment() {
    try {
        log('💰 Starting commission payment process...');

        if (!tasksCompleted.wallet || !connectedWallet) {
            main_showToast('Please connect your wallet first!', 'error');
            return;
        }

        if (tasksCompleted.pay) {
            main_showToast('Commission already paid!', 'info');
            return;
        }

        // ذخیره زمان شروع پرداخت
        localStorage.setItem('ccoin_payment_initiated', Date.now().toString());

        // ساخت URL کامل برای صفحه کمیسیون
        const commissionUrl = `${window.location.origin}/commission/browser/pay?telegram_id=${USER_ID}`;
        
        log('🔗 Opening commission page in external browser: ' + commissionUrl);

        // استفاده از Telegram WebApp API برای باز کردن در مرورگر خارجی
        if (window.Telegram && window.Telegram.WebApp) {
            // this wrapper tries to open externally via Telegram
            if (window.Telegram.WebApp.openTelegramLink) {
                try {
                    window.Telegram.WebApp.openTelegramLink(`https://t.me/iv?url=${encodeURIComponent(commissionUrl)}&rhash=${Math.random()}`);
                } catch(e) {
                    window.Telegram.WebApp.openLink(commissionUrl);
                }
            } else if (window.Telegram.WebApp.openLink) {
                window.Telegram.WebApp.openLink(commissionUrl);
            } else {
                window.open(commissionUrl, '_blank');
            }
        } else {
            // fallback
            window.open(commissionUrl, '_blank');
        }

        main_showToast('Opening payment page...', 'info');

    } catch (error) {
        log('❌ Commission payment error: ' + error.message);
        main_showToast('Failed to open payment page: ' + error.message, 'error');
    }
}

async function main_claimAirdrop() {
    try {
        log('🎉 Claiming airdrop...');

        const allCompleted = tasksCompleted.task && tasksCompleted.invite && tasksCompleted.wallet && tasksCompleted.pay;

        if (!allCompleted) {
            main_showToast('Please complete all tasks first!', 'error');
            return;
        }

        const claimButton = document.getElementById('claimBtn');
        if (claimButton) {
            claimButton.disabled = true;
            claimButton.textContent = 'Processing...';
        }

        const response = await fetch('/airdrop/claim', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error('Server error: ' + response.statusText);
        }

        const data = await response.json();
        log('✅ Claim response: ' + JSON.stringify(data));

        if (data.success) {
            main_showToast('🎉 Airdrop claimed successfully!', 'success');
            
            if (claimButton) {
                claimButton.textContent = '✅ Claimed!';
                claimButton.style.background = '#28a745';
            }
        } else {
            throw new Error(data.message || 'Claim failed');
        }

    } catch (error) {
        log('❌ Claim error: ' + error.message);
        main_showToast('Failed to claim airdrop: ' + error.message, 'error');

        const claimButton = document.getElementById('claimBtn');
        if (claimButton) {
            claimButton.disabled = false;
            claimButton.textContent = 'Claim Airdrop';
        }
    }
}

function main_checkWalletStatus() {
    const urlParams = new URLSearchParams(window.location.search);
    
    if (urlParams.has('wallet_connected')) {
        const status = urlParams.get('wallet_connected');
        if (status === 'success') {
            main_showToast('✅ Wallet connected successfully!', 'success');
            
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        }
    }
    
    if (urlParams.has('wallet_error')) {
        const error = urlParams.get('wallet_error');
        main_showToast('❌ Wallet connection failed: ' + error, 'error');
    }

    if (urlParams.has('commission_paid')) {
        const status = urlParams.get('commission_paid');
        if (status === 'success') {
            main_showToast('✅ Commission paid successfully!', 'success');
            
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        }
    }

    if (urlParams.has('commission_error')) {
        const error = urlParams.get('commission_error');
        main_showToast('❌ Commission payment failed: ' + error, 'error');
    }
}

window.addEventListener('DOMContentLoaded', function() {
    log('🚀 Airdrop page loaded (main script)');
    
    main_startCountdown();
    
    main_updateAllTasksUI();
    
    main_checkWalletStatus();
    
    const connectWalletBtn = document.querySelector('#connect-wallet .task-button');
    if (connectWalletBtn) {
        connectWalletBtn.addEventListener('click', main_handleWalletConnection);
    }

    const payCommissionBtn = document.querySelector('#pay-commission .task-button');
    if (payCommissionBtn) {
        payCommissionBtn.addEventListener('click', main_handleCommissionPayment);
    }

    const claimBtn = document.getElementById('claimBtn');
    if (claimBtn) {
        claimBtn.addEventListener('click', main_claimAirdrop);
    }

    log('✅ Event listeners attached');
});

window.addEventListener('beforeunload', function() {
    main_stopCountdown();
});

/* ---------- End content from 00001.js ---------- */

/* ---------- Begin inline script originally inside 00001.html ----------
   (kept as-is so onclick attributes and Jinja2 templating keep working)
   These functions remain global and are expected by the HTML markup.
   ------------------------------------------------------------------ */

 // Global variables
let currentWalletAddress = '{{ user_wallet_address if user_wallet_address else "" }}';
let userStatuses = {
    tasks_completed: {{ tasks_completed|lower }},
    friends_invited: {{ invited|lower }},
    wallet_connected: {{ wallet_connected|lower }},
    commission_paid: {{ commission_paid|lower }}
};

// Telegram WebApp Initialization
const tg = window.Telegram ? window.Telegram.WebApp : null;
const telegramId = tg ? tg.initDataUnsafe.user?.id : null;

// Get CSRF token from meta tag
function getCsrfToken() {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    return metaTag ? metaTag.getAttribute('content') : '';
}

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    console.log('Page loaded, initializing...');

    initializeCountdown();
    updateTaskStatuses();

    document.addEventListener('click', function(event) {
        const dropdown = document.getElementById('wallet-dropdown-content');
        const walletButton = document.querySelector('.wallet-connect-button');

        if (!walletButton.contains(event.target)) {
            dropdown.classList.remove('show');
        }
    });
});

function initializeCountdown() {
    const countDownDate = new Date("2026-02-17T23:59:59").getTime();

    const timer = setInterval(function() {
        const now = new Date().getTime();
        const distance = countDownDate - now;

        if (distance < 0) {
            clearInterval(timer);
            document.getElementById("days").innerHTML = "00";
            document.getElementById("hours").innerHTML = "00";
            document.getElementById("minutes").innerHTML = "00";
            document.getElementById("seconds").innerHTML = "00";
            return;
        }

        const days = Math.floor(distance / (1000 * 60 * 60 * 24));
        const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);

        document.getElementById("days").innerHTML = String(days).padStart(2, '0');
        document.getElementById("hours").innerHTML = String(hours).padStart(2, '0');
        document.getElementById("minutes").innerHTML = String(minutes).padStart(2, '0');
        document.getElementById("seconds").innerHTML = String(seconds).padStart(2, '0');
    }, 1000);
}

function updateTaskStatuses() {
    if (userStatuses.tasks_completed) {
        markTaskAsCompleted('task-completion', 'tasks-icon', 'Tasks Completed');
    }

    if (userStatuses.friends_invited) {
        markTaskAsCompleted('inviting-friends', 'friends-icon', 'Friends Invited');
    }

    if (userStatuses.wallet_connected && currentWalletAddress) {
        markWalletAsConnected();
    }

    if (userStatuses.commission_paid) {
        markTaskAsCompleted('pay-commission', 'commission-icon', 'Commission Paid');
    }

    checkAllTasksCompletion();
}

function markTaskAsCompleted(taskId, iconId, text) {
    const taskBox = document.getElementById(taskId);
    const button = taskBox.querySelector('.task-button');
    const icon = document.getElementById(iconId);
    const leftText = button.querySelector('.left-text');

    taskBox.classList.add('completed');
    button.classList.add('tasks-completed');
    icon.className = 'fas fa-check right-icon';
    leftText.textContent = text;
}

function markWalletAsConnected() {
    const taskBox = document.getElementById('connect-wallet');
    const button = taskBox.querySelector('.task-button');
    const icon = document.getElementById('wallet-icon');
    const buttonText = document.getElementById('wallet-button-text');
    const statusIndicator = document.getElementById('wallet-status-indicator');

    taskBox.classList.add('completed');
    button.classList.add('wallet-connected');
    icon.className = 'fas fa-check right-icon';
    statusIndicator.classList.add('connected');

    const shortAddress = currentWalletAddress.slice(0, 6) + '...' + currentWalletAddress.slice(-4);
    buttonText.textContent = `Connected: ${shortAddress}`;
}

function handleTaskCompletion() {
    window.location.href = '/earn';
}

function handleInviteCheck() {
    window.location.href = '/friends';
}

function handleWalletConnection() {
    if (userStatuses.wallet_connected && currentWalletAddress) {
        const dropdown = document.getElementById('wallet-dropdown-content');
        dropdown.classList.toggle('show');
    } else {
        showPhantomModal();
    }
}

function showPhantomModal() {
    const modal = document.getElementById('phantomModal');
    modal.classList.add('show');
}

function closePhantomModal() {
    const modal = document.getElementById('phantomModal');
    modal.classList.remove('show');
}

function openPhantomWallet() {
    closePhantomModal();

    if (!telegramId) {
        showToast('Error: User information not found', 'error');
        return;
    }

    showToast('Redirecting to wallet...', 'info');

    const walletUrl = `/wallet/browser/connect?telegram_id=${telegramId}`;

    try {
        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.openLink(walletUrl);
        } else {
            window.open(walletUrl, '_blank');
        }
    } catch (error) {
        console.error('Error opening wallet:', error);
        window.location.href = walletUrl;
    }
}

function changeWallet() {
    const dropdown = document.getElementById('wallet-dropdown-content');
    dropdown.classList.remove('show');
    showPhantomModal();
}

async function disconnectWallet() {
    const dropdown = document.getElementById('wallet-dropdown-content');
    dropdown.classList.remove('show');

    try {
        const response = await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': getCsrfToken()
            },
            body: JSON.stringify({
                wallet: ""
            })
        });

        if (response.ok) {
            currentWalletAddress = '';
            userStatuses.wallet_connected = false;

            const taskBox = document.getElementById('connect-wallet');
            const button = taskBox.querySelector('.task-button');
            const icon = document.getElementById('wallet-icon');
            const buttonText = document.getElementById('wallet-button-text');
            const statusIndicator = document.getElementById('wallet-status-indicator');

            taskBox.classList.remove('completed');
            button.classList.remove('wallet-connected');
            icon.className = 'fas fa-chevron-right right-icon';
            statusIndicator.classList.remove('connected');
            buttonText.textContent = 'Connect Wallet';

            showToast('Wallet disconnected', 'success');
            checkAllTasksCompletion();
        } else {
            throw new Error('Failed to disconnect wallet');
        }
    } catch (error) {
        console.error('Error disconnecting wallet:', error);
        showToast('Error disconnecting wallet', 'error');
    }
}


async function handleCommissionPayment() {
    console.log('Commission button clicked', userStatuses);

    if (userStatuses.commission_paid) {
        showToast('✅ Commission already paid!', 'success');
        return;
    }

    if (!userStatuses.wallet_connected) {
        showToast('⚠️ Please connect your wallet first', 'error');
        return;
    }

    // ✅ دریافت telegram_id به صورت string
    const telegram_id = String(telegramId || '{{ request.session.get("telegram_id") }}');

    if (!telegram_id || telegram_id === 'undefined') {
        showToast('Error: Telegram ID not found', 'error');
        return;
    }

    try {
        showToast('📤 Sending payment link to your Telegram...', 'info');

        const response = await fetch('/airdrop/request_commission_link', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({telegram_id: telegram_id})
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast('✅ Check your Telegram messages!', 'success');

            // نمایش popup در Telegram
            if (tg && tg.showPopup) {
                tg.showPopup({
                    title: '✅ Link Sent!',
                    message: 'Payment link has been sent to your Telegram chat. Please check your messages and click the button to pay.',
                    buttons: [{type: 'close'}]
                });
            }
        } else {
            showToast('❌ ' + (data.message || 'Failed to send link'), 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('❌ Error: ' + error.message, 'error');
    }
}

function openCommissionPayment() {
    closeCommissionModal();

    const telegram_id = telegramId || '{{ request.session.get("telegram_id") }}';

    if (!telegram_id) {
        showToast('Error: Telegram ID not found', 'error');
        return;
    }

    const commissionUrl = `${window.location.origin}/commission/browser/pay?telegram_id=${telegram_id}`;

    console.log('🔗 Opening commission payment in external browser:', commissionUrl);

    if (tg && typeof tg.openLink === 'function') {
         tg.openLink(commissionUrl, {try_instant_view: false});
        showToast('Opening payment page in external browser...', 'info');
    } else {
        const newWindow = window.open(commissionUrl, '_blank', 'noopener,noreferrer');
        if (!newWindow) {
            showToast('Please allow pop-ups for this site', 'error');
        }
    }
}

function checkAllTasksCompletion() {
    const allCompleted = userStatuses.tasks_completed &&
                           userStatuses.friends_invited &&
                           userStatuses.wallet_connected &&
                           userStatuses.commission_paid;

    const claimBtn = document.getElementById('claimBtn');

    if (allCompleted) {
        claimBtn.innerHTML = '🎉 Congratulations! You have completed all tasks and are eligible to receive tokens!';
        claimBtn.disabled = false;
        claimBtn.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
        claimBtn.style.color = 'white';
        claimBtn.style.cursor = 'pointer';
        claimBtn.onclick = claimAirdrop;
    } else {
        claimBtn.innerHTML = 'Complete All Tasks to Claim';
        claimBtn.disabled = true;
        claimBtn.style.background = '#e0e7ff';
        claimBtn.style.color = '#9ca3af';
        claimBtn.style.cursor = 'not-allowed';
    }
}

function claimAirdrop() {
    showToast('🎉 Congratulations! Your airdrop claim has been registered!', 'success');
}

function showToast(message, type = 'info') {
    const existingToasts = document.querySelectorAll('.toast');
    existingToasts.forEach(toast => toast.remove());

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
            toast.remove();
        }, 300);
    }, 3000);
}

async function checkCommissionStatus() {
    if (!userStatuses.commission_paid && userStatuses.wallet_connected) {
        try {
            const response = await fetch(`/commission/check_status?telegram_id=${telegramId}`, {
                headers: {
                    'X-CSRF-Token': getCsrfToken()
                }
            });
            const data = await response.json();

            if (data.commission_paid && !userStatuses.commission_paid) {
                userStatuses.commission_paid = true;
                markTaskAsCompleted('pay-commission', 'commission-icon', 'Commission Paid');
                checkAllTasksCompletion();
                showToast('✅ Commission payment confirmed!', 'success');
            }
        } catch (error) {
            console.error('Error checking commission status:', error);
        }
    }
}

setInterval(checkCommissionStatus, 10000);

/* ---------- End inline script ---------- */
