// ============================================
// CCoin Airdrop JavaScript
// ============================================

// Check for APP_CONFIG and create fallback if not exists
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

// Extract global variables from APP_CONFIG
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

// State management
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

// ============================================
// Utility Functions
// ============================================

function log(msg) {
    console.log('[Airdrop] ' + msg);
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(function() {
        toast.classList.add('show');
    }, 100);

    setTimeout(function() {
        toast.classList.remove('show');
        setTimeout(function() {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}

// ============================================
// Countdown Timer
// ============================================

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

            const daysEl = document.getElementById('days');
            const hoursEl = document.getElementById('hours');
            const minutesEl = document.getElementById('minutes');
            const secondsEl = document.getElementById('seconds');

            if (daysEl) daysEl.textContent = days.toString().padStart(2, '0');
            if (hoursEl) hoursEl.textContent = hours.toString().padStart(2, '0');
            if (minutesEl) minutesEl.textContent = minutes.toString().padStart(2, '0');
            if (secondsEl) secondsEl.textContent = seconds.toString().padStart(2, '0');

        } else {
            const elements = ['days', 'hours', 'minutes', 'seconds'];
            elements.forEach(function(id) {
                const el = document.getElementById(id);
                if (el) el.textContent = '00';
            });

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
    log('⏰ Starting countdown...');
    updateCountdown();
    if (countdownInterval) clearInterval(countdownInterval);
    countdownInterval = setInterval(updateCountdown, 1000);
    log('✅ Countdown started');
}

function stopCountdown() {
    if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
        log('⏹️ Countdown stopped');
    }
}

// ============================================
// UI Update Functions
// ============================================

function updateWalletUI() {
    const walletButtonText = document.getElementById('wallet-button-text');
    const walletIcon = document.getElementById('wallet-icon');
    const walletStatusIndicator = document.getElementById('wallet-status-indicator');
    const walletButton = document.querySelector('#connect-wallet .task-button');

    if (tasksCompleted.wallet && connectedWallet) {
        const shortAddress = connectedWallet.substring(0, 6) + '...' + connectedWallet.substring(connectedWallet.length - 4);

        if (walletButtonText) {
            walletButtonText.textContent = 'Connected: ' + shortAddress;
            walletButtonText.style.color = '#ffffff';
        }

        if (walletIcon) {
            walletIcon.className = 'fas fa-check right-icon';
            walletIcon.style.color = '#28a745';
        }

        if (walletButton) walletButton.classList.add('wallet-connected');
        if (walletStatusIndicator) walletStatusIndicator.classList.add('connected');

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

        if (walletButton) walletButton.classList.remove('wallet-connected');
        if (walletStatusIndicator) walletStatusIndicator.classList.remove('connected');

        log('🔄 Wallet UI reset');
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
        if (commissionButton) commissionButton.classList.add('commission-paid');
        log('✅ Commission UI: paid');
    } else {
        if (commissionIcon) {
            commissionIcon.className = 'fas fa-chevron-right right-icon';
            commissionIcon.style.color = '#aaa';
        }
        if (commissionButton) commissionButton.classList.remove('commission-paid');
        log('💰 Commission UI: not paid');
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
        if (taskButton) taskButton.classList.add('tasks-completed');
        log('✅ Tasks UI: completed');
    } else {
        if (taskIcon) {
            taskIcon.className = 'fas fa-chevron-right right-icon';
            taskIcon.style.color = '#aaa';
        }
        if (taskButton) taskButton.classList.remove('tasks-completed');
        log('📋 Tasks UI: not completed');
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
        if (friendsButton) friendsButton.classList.add('friends-invited');
        log('✅ Friends UI: invited');
    } else {
        if (friendsIcon) {
            friendsIcon.className = 'fas fa-chevron-right right-icon';
            friendsIcon.style.color = '#aaa';
        }
        if (friendsButton) friendsButton.classList.remove('friends-invited');
        log('👥 Friends UI: not invited');
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

// ============================================
// Wallet Functions
// ============================================

async function detectPhantom() {
    try {
        if (window.solana && window.solana.isPhantom) {
            phantomProvider = window.solana;
            phantomDetected = true;
            log('✅ Phantom detected');
            return true;
        } else {
            log('❌ Phantom not detected');
            return false;
        }
    } catch (error) {
        log('❌ Phantom detection error: ' + error.message);
        return false;
    }
}

async function handleWalletConnection() {
    try {
        log('🔗 Wallet connection...');

        const walletUrl = '/wallet/browser/connect?telegram_id=' + USER_ID;
        log('Opening: ' + walletUrl);

        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.openLink(walletUrl);
        } else {
            window.open(walletUrl, '_blank');
        }

    } catch (error) {
        log('❌ Wallet error: ' + error.message);
        showToast('Failed to connect wallet', 'error');
    }
}

async function sendWalletToServer(walletAddress) {
    try {
        log('📤 Sending wallet: ' + (walletAddress || 'disconnect'));

        const response = await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({wallet_address: walletAddress})
        });

        if (!response.ok) throw new Error('Server error: ' + response.statusText);

        const data = await response.json();
        log('✅ Response: ' + JSON.stringify(data));
        return data;

    } catch (error) {
        log('❌ Send wallet error: ' + error.message);
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

        showToast('Wallet disconnected!', 'success');
        log('✅ Disconnected');

    } catch (error) {
        log('❌ Disconnect error: ' + error.message);
        showToast('Failed to disconnect', 'error');
    }
}

function changeWallet() {
    handleWalletConnection();
}

// ============================================
// ✅ UPDATED: Commission Payment Function
// ============================================

async function handleCommissionPayment() {
    try {
        log('💰 Starting commission payment...');
        console.log('💰 handleCommissionPayment called');

        // Check wallet connection
        if (!tasksCompleted.wallet || !connectedWallet) {
            showToast('⚠️ ابتدا کیف پول را متصل کنید!', 'error');
            log('❌ Wallet not connected');
            return;
        }

        // Check if already paid
        if (tasksCompleted.pay) {
            showToast('✅ قبلاً پرداخت شده است!', 'info');
            log('ℹ️ Already paid');
            return;
        }

        // Show loading state
        const commissionButton = document.getElementById('commission-button');
        const commissionIcon = document.getElementById('commission-icon');
        
        if (commissionButton) commissionButton.classList.add('loading');
        if (commissionIcon) {
            commissionIcon.className = 'fas fa-spinner right-icon';
        }

        // Build payment URL
        const url = window.location.origin + '/commission/browser/pay?telegram_id=' + USER_ID;
        log('🔗 Payment URL: ' + url);

        // Send link to Telegram chat
        try {
            log('📤 Sending link to chat...');

            const response = await fetch('/commission/send_link_to_chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    telegram_id: USER_ID,
                    payment_url: url
                })
            });

            // Remove loading state
            if (commissionButton) commissionButton.classList.remove('loading');
            if (commissionIcon) {
                commissionIcon.className = 'fas fa-chevron-right right-icon';
            }

            if (!response.ok) {
                throw new Error('Server error: ' + response.status);
            }

            const result = await response.json();
            log('📨 Response: ' + JSON.stringify(result));

            if (result.success) {
                showToast('✅ لینک پرداخت به چت تلگرام ارسال شد!', 'success');
                log('✅ Link sent successfully to chat');

                // Haptic feedback
                if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
                    window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
                }

                // Show instruction
                setTimeout(function() {
                    showToast('💬 لطفاً چت تلگرام خود را بررسی کنید', 'info');
                }, 2000);

                setTimeout(function() {
                    showToast('🔗 روی لینک کلیک کنید تا صفحه پرداخت باز شود', 'info');
                }, 4000);

            } else {
                throw new Error(result.error || 'Failed to send link');
            }

        } catch (fetchError) {
            // Remove loading state on error
            if (commissionButton) commissionButton.classList.remove('loading');
            if (commissionIcon) {
                commissionIcon.className = 'fas fa-chevron-right right-icon';
            }

            log('❌ Send error: ' + fetchError.message);
            console.error('❌ Error:', fetchError);
            showToast('❌ خطا در ارسال لینک. لطفاً دوباره تلاش کنید.', 'error');
        }

    } catch (error) {
        // Remove loading state on error
        const commissionButton = document.getElementById('commission-button');
        const commissionIcon = document.getElementById('commission-icon');
        
        if (commissionButton) commissionButton.classList.remove('loading');
        if (commissionIcon) {
            commissionIcon.className = 'fas fa-chevron-right right-icon';
        }

        log('❌ Commission error: ' + error.message);
        console.error('❌ Error:', error);
        showToast('❌ خطایی رخ داده است', 'error');
    }
}

// ============================================
// Task Handlers
// ============================================

async function handleTaskCompletion() {
    window.location.href = '/earn';
}

async function handleInviteCheck() {
    window.location.href = '/friends';
}

async function handleClaimAirdrop() {
    try {
        log('🎁 Claiming airdrop...');

        const allCompleted = tasksCompleted.task && tasksCompleted.invite && tasksCompleted.wallet && tasksCompleted.pay;

        if (!allCompleted) {
            showToast('⚠️ لطفاً ابتدا تمام مراحل را تکمیل کنید', 'error');
            return;
        }

        showToast('🎉 در حال پردازش...', 'info');

        const response = await fetch('/airdrop/claim', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({telegram_id: USER_ID})
        });

        if (!response.ok) throw new Error('Claim failed');

        const data = await response.json();
        log('✅ Claim response: ' + JSON.stringify(data));

        if (data.success) {
            showToast('🎉 ایردراپ با موفقیت دریافت شد!', 'success');
            
            if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback) {
                window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
            }

            setTimeout(function() {
                window.location.reload();
            }, 2000);
        } else {
            throw new Error(data.error || 'Claim failed');
        }

    } catch (error) {
        log('❌ Claim error: ' + error.message);
        showToast('❌ خطا در دریافت ایردراپ', 'error');
    }
}

// ============================================
// Page Initialization
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    log('📱 Page loaded');

    // Start countdown
    startCountdown();

    // Detect Phantom
    detectPhantom();

    // Update all UI elements
    updateAllTasksUI();

    // Setup claim button
    const claimBtn = document.getElementById('claimBtn');
    if (claimBtn) {
        claimBtn.addEventListener('click', handleClaimAirdrop);
    }

    // Close wallet dropdown when clicking outside
    document.addEventListener('click', function(event) {
        const dropdown = document.getElementById('wallet-dropdown-content');
        const walletButton = document.querySelector('#connect-wallet .task-button');

        if (dropdown && walletButton) {
            if (!walletButton.contains(event.target) && !dropdown.contains(event.target)) {
                dropdown.classList.remove('show');
            }
        }
    });

    log('✅ Initialization complete');
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    stopCountdown();
});
