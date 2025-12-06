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
        const targetDate = new Date('2026-03-06T23:59:59Z').getTime();
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
        log('❌ Error sending wallet: ' + error.message);
        throw error;
    }
}

async function disconnectWallet() {
    try {
        log('🔌 Disconnecting...');
        if (phantomProvider) await phantomProvider.disconnect();
        await sendWalletToServer(null);
        connectedWallet = '';
        tasksCompleted.wallet = false;
        updateWalletUI();
        updateClaimButton();
        showToast('Wallet disconnected', 'success');
    } catch (error) {
        showToast('Failed to disconnect', 'error');
    }
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


// تابع برای باز کردن مودال کمیسیون
function openCommissionModal() {
    console.log('🔵 Opening commission modal');
    const modal = document.getElementById('commission-modal');
    if (modal) {
        modal.classList.add('show');
        console.log('✅ Modal opened');
    } else {
        console.error('❌ Modal element not found!');
    }
}

// تابع برای بستن مودال کمیسیون
function closeCommissionModal() {
    console.log('🔵 Closing commission modal');
    const modal = document.getElementById('commission-modal');
    if (modal) {
        modal.classList.remove('show');
        console.log('✅ Modal closed');
    }
}

async function handleCommissionClick() {
    console.log('🔵 Commission clicked');
    
    if (!tasksCompleted.wallet || !connectedWallet) {
        showToast('Connect wallet first!', 'error');
        return;
    }
    if (tasksCompleted.pay) {
        showToast('Already paid!', 'info');
        return;
    }
    showToast('Sending link...', 'info');
    try {
        const res = await fetch('/commission/send_payment_link', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({telegram_id: USER_ID})
        });
        const data = await res.json();
        console.log('Response:', data);
        
        if (data.success) {
            showToast('✅ Check Telegram!', 'success');
        } else {
            showToast('❌ ' + data.message, 'error');
        }
    } catch (e) {
        console.error('Error:', e);
        showToast('Error: ' + e.message, 'error');
    }
}
console.log('✅ airdrop.js loaded');

// تابع تست ساده برای دکمه کمیسیون
function testCommissionButton() {
    console.log('🟢 Button clicked!');
    alert('Button works! Telegram ID: ' + USER_ID);
    
    // تست اتصال کیف پول
    if (!tasksCompleted.wallet || !connectedWallet) {
        alert('❌ Please connect your wallet first!');
        console.log('❌ Wallet not connected');
        return;
    }
    
    // تست پرداخت قبلی
    if (tasksCompleted.pay) {
        alert('✅ Commission already paid!');
        console.log('✅ Already paid');
        return;
    }
    
    // ارسال درخواست
    console.log('🔵 Sending request to server...');
    
    fetch('/commission/send_payment_link', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            telegram_id: USER_ID
        })
    })
    .then(response => {
        console.log('🔵 Response status:', response.status);
        return response.json();
    })
    .then(data => {
        console.log('🔵 Response data:', data);
        
        if (data.success) {
            alert('✅ Success! Check your Telegram chat.');
            showToast('✅ Payment link sent! Check your Telegram chat.', 'success');
        } else {
            alert('❌ Failed: ' + data.message);
            showToast('❌ ' + data.message, 'error');
        }
    })
    .catch(error => {
        console.error('🔴 Error:', error);
        alert('❌ Error: ' + error.message);
        showToast('Error: ' + error.message, 'error');
    });
}
