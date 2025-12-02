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

function updateCountdown() {
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

function startCountdown() {
    log('⏰ Starting countdown timer...');

    updateCountdown();

    if (countdownInterval) {
        clearInterval(countdownInterval);
    }
    countdownInterval = setInterval(updateCountdown, 1000);

    log('✅ Countdown timer started successfully');
}

function stopCountdown() {
    if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
        log('⏹️ Countdown timer stopped');
    }
}

function updateWalletUI() {
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

function updateClaimButton() {
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

function updateAllTasksUI() {
    updateTaskCompleteUI();
    updateInviteFriendsUI();
    updateWalletUI();
    updateCommissionUI();
    updateClaimButton();
}

function showToast(message, type = 'info') {
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

async function detectPhantom() {
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

async function handleWalletConnection() {
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
        showToast('Failed to open wallet connection: ' + error.message, 'error');
    }
}

async function sendWalletToServer(walletAddress) {
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

async function disconnectWallet() {
    try {
        log('🔌 Disconnecting wallet...');

        if (phantomProvider) {
            await phantomProvider.disconnect();
        }

        await sendWalletToServer(null);

        connectedWallet = '';
        tasksCompleted.wallet = false;

        updateWalletUI();
        updateClaimButton();

        showToast('Wallet disconnected successfully!', 'success');
        log('✅ Wallet disconnected');

    } catch (error) {
        log('❌ Wallet disconnection failed: ' + error.message);
        showToast('Failed to disconnect wallet: ' + error.message, 'error');
    }
}

async function handleCommissionPayment() {
    if (!tasksCompleted.wallet || !connectedWallet) {
        showToast('Please connect your wallet first!', 'error');
        return;
    }

    if (tasksCompleted.pay) {
        showToast('Commission already paid!', 'info');
        return;
    }

    // باز کردن مودال
    openCommissionModal();
}

function openCommissionModal() {
    const modal = document.getElementById('commissionModal');
    if (modal) {
        modal.classList.add('show');
        log('Commission modal opened');
    }
}

function closeCommissionModal() {
    const modal = document.getElementById('commissionModal');
    if (modal) {
        modal.classList.remove('show');
        log('Commission modal closed');
    }
}

async function sendPaymentLinkToChat() {
    try {
        log('📤 Sending commission payment link to Telegram...');
        
        // نمایش loading
        showToast('Sending link to your Telegram...', 'info');
        
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
        
        const response = await fetch('/commission/send_payment_link', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken
            },
            body: JSON.stringify({ 
                telegram_id: USER_ID 
            })
        });

        const result = await response.json();

        if (response.ok && result.success) {
            log('✅ Payment link sent successfully');
            showToast(result.message || 'Link sent! Check your Telegram.', 'success');
            
            // بستن مودال بعد از 2 ثانیه
            setTimeout(() => {
                closeCommissionModal();
            }, 2000);
            
        } else {
            log('❌ Failed to send link: ' + (result.error || result.message));
            showToast(result.error || result.message || 'Failed to send link', 'error');
        }

    } catch (error) {
        log('❌ Error sending payment link: ' + error.message);
        showToast('Network error. Please try again.', 'error');
        console.error('Error:', error);
    }
}

function closeCommissionModal() {
    document.getElementById('commissionModal').classList.remove('show');
}

function getTelegramId() {
    // روش ۱: از APP_CONFIG
    if (typeof USER_ID !== 'undefined' && USER_ID) {
        return USER_ID;
    }

    // روش ۲: از WebApp
    if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initDataUnsafe) {
        const user = window.Telegram.WebApp.initDataUnsafe.user;
        if (user && user.id) {
            return user.id.toString();
        }
    }

    // روش ۳: از URL
    const urlParams = new URLSearchParams(window.location.search);
    const telegramIdFromUrl = urlParams.get('telegram_id');
    if (telegramIdFromUrl) {
        return telegramIdFromUrl;
    }

    log('❌ Could not retrieve Telegram ID');
    return null;
}

async function claimAirdrop() {
    try {
        log('🎉 Claiming airdrop...');

        const allCompleted = tasksCompleted.task && tasksCompleted.invite && tasksCompleted.wallet && tasksCompleted.pay;

        if (!allCompleted) {
            showToast('Please complete all tasks first!', 'error');
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
            showToast('🎉 Airdrop claimed successfully!', 'success');

            if (claimButton) {
                claimButton.textContent = '✅ Claimed!';
                claimButton.style.background = '#28a745';
            }
        } else {
            throw new Error(data.message || 'Claim failed');
        }

    } catch (error) {
        log('❌ Claim error: ' + error.message);
        showToast('Failed to claim airdrop: ' + error.message, 'error');

        const claimButton = document.getElementById('claimBtn');
        if (claimButton) {
            claimButton.disabled = false;
            claimButton.textContent = 'Claim Airdrop';
        }
    }
}

function checkWalletStatus() {
    const urlParams = new URLSearchParams(window.location.search);

    if (urlParams.has('wallet_connected')) {
        const status = urlParams.get('wallet_connected');
        if (status === 'success') {
            showToast('✅ Wallet connected successfully!', 'success');

            setTimeout(() => {
                window.location.reload();
            }, 1500);
        }
    }

    if (urlParams.has('wallet_error')) {
        const error = urlParams.get('wallet_error');
        showToast('❌ Wallet connection failed: ' + error, 'error');
    }

    if (urlParams.has('commission_paid')) {
        const status = urlParams.get('commission_paid');
        if (status === 'success') {
            showToast('✅ Commission paid successfully!', 'success');

            setTimeout(() => {
                window.location.reload();
            }, 1500);
        }
    }

    if (urlParams.has('commission_error')) {
        const error = urlParams.get('commission_error');
        showToast('❌ Commission payment failed: ' + error, 'error');
    }
}

window.addEventListener('DOMContentLoaded', function() {
    log('🚀 Airdrop page loaded');

    startCountdown();

    updateAllTasksUI();

    checkWalletStatus();

    const connectWalletBtn = document.querySelector('#connect-wallet .task-button');
    if (connectWalletBtn) {
        connectWalletBtn.addEventListener('click', handleWalletConnection);
    }

    const payCommissionBtn = document.querySelector('#pay-commission .task-button');
    if (payCommissionBtn) {
        payCommissionBtn.addEventListener('click', handleCommissionPayment);
    }

    const claimBtn = document.getElementById('claimBtn');
    if (claimBtn) {
        claimBtn.addEventListener('click', claimAirdrop);
    }

    log('✅ Event listeners attached');
});

window.addEventListener('beforeunload', function() {
    stopCountdown();
});


async function sendPaymentLinkToChat() {
    try {
        console.log('🔵 sendPaymentLinkToChat called!'); // تست اولیه
        log('📤 Sending payment link to Telegram chat...');
        
        // نمایش loading
        showToast('Sending link to your Telegram...', 'info');
        
        // دریافت CSRF token
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
        console.log('🔑 CSRF Token:', csrfToken ? 'Found' : 'Not found');
        console.log('👤 User ID:', USER_ID);
        
        // ارسال درخواست
        const response = await fetch('/commission/send_payment_link', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken
            },
            body: JSON.stringify({ 
                telegram_id: USER_ID 
            })
        });

        console.log('📡 Response status:', response.status);
        
        const result = await response.json();
        console.log('📦 Response data:', result);

        if (response.ok && result.success) {
            log('✅ Payment link sent successfully');
            showToast(result.message || 'Link sent! Check your Telegram messages.', 'success');
            
            // بستن مودال بعد از 2 ثانیه
            setTimeout(() => {
                closeCommissionModal();
            }, 2000);
            
        } else {
            log('❌ Failed to send link: ' + (result.error || result.message));
            showToast(result.error || result.message || 'Failed to send link. Please try again.', 'error');
        }

    } catch (error) {
        console.error('❌ Error in sendPaymentLinkToChat:', error);
        log('❌ Error sending payment link: ' + error.message);
        showToast('Network error. Please check your connection and try again.', 'error');
    }
}

/**
 * باز کردن مودال کمیسیون
 */
function openCommissionModal() {
    console.log('🔵 [DEBUG] openCommissionModal called');
    const modal = document.getElementById('commissionModal');
    if (modal) {
        modal.classList.add('show');
        console.log('✅ Modal opened successfully');
        log('Commission modal opened');
    } else {
        console.error('❌ commissionModal element not found in DOM!');
        alert('Error: Modal not found. Please refresh the page.');
    }
}

/**
 * بستن مودال کمیسیون
 */
function closeCommissionModal() {
    console.log('🔵 [DEBUG] closeCommissionModal called');
    const modal = document.getElementById('commissionModal');
    if (modal) {
        modal.classList.remove('show');
        console.log('✅ Modal closed successfully');
        log('Commission modal closed');
    }
}

/**
 * Handle commission payment button click
 */
async function handleCommissionPayment() {
    console.log('🔵 [DEBUG] handleCommissionPayment called');
    console.log('🔵 [DEBUG] Wallet connected:', tasksCompleted.wallet);
    console.log('🔵 [DEBUG] Connected wallet address:', connectedWallet);
    console.log('🔵 [DEBUG] Commission paid:', tasksCompleted.pay);
    
    if (!tasksCompleted.wallet || !connectedWallet) {
        console.log('❌ Wallet not connected');
        showToast('Please connect your wallet first!', 'error');
        return;
    }

    if (tasksCompleted.pay) {
        console.log('ℹ️ Commission already paid');
        showToast('Commission already paid!', 'info');
        return;
    }

    console.log('✅ Opening commission modal...');
    openCommissionModal();
}

/**
 * تابع تست برای دیباگ
 */
window.testCommissionModal = function() {
    console.log('🧪 Testing commission modal...');
    console.log('Modal element:', document.getElementById('commissionModal'));
    console.log('Send button:', document.getElementById('sendPaymentLinkBtn'));
    console.log('Close button:', document.getElementById('closeCommissionModalBtn'));
    console.log('APP_CONFIG:', window.APP_CONFIG);
    openCommissionModal();
};

console.log('✅ Commission modal functions loaded');
