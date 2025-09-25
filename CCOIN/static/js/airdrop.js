// تشخیص وجود APP_CONFIG و ایجاد fallback در صورت عدم وجود
if (typeof window.APP_CONFIG === 'undefined') {
    console.error('❌ APP_CONFIG not found! Using fallback values.');
    window.APP_CONFIG = {
        USER_ID: '123456789',
        SOLANA_RPC_URL: 'https://api.devnet.solana.com',
        COMMISSION_AMOUNT: 0.001,
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
let countdownInterval = null; // برای مدیریت interval شمارش معکوس

function log(msg) {
    console.log('[Airdrop] ' + msg);
}

// **تابع شمارش معکوس اصلاح شده**
function updateCountdown() {
    try {
        // تاریخ هدف: 31 دسامبر 2025 (اصلاح شده)
        const targetDate = new Date('2025-12-31T23:59:59Z').getTime();
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

            // بروزرسانی با انیمیشن
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

            // فقط هر 30 ثانیه log کن تا spam نشود
            if (seconds % 30 === 0) {
                console.log(`⏰ Countdown: ${days}d ${hours}h ${minutes}m ${seconds}s`);
            }

        } else {
            // تمام شد
            const elements = ['days', 'hours', 'minutes', 'seconds'];
            elements.forEach(id => {
                const element = document.getElementById(id);
                if (element) element.textContent = '00';
            });

            console.log('🎉 Countdown finished!');

            // تغییر عنوان countdown
            const countdownTitle = document.querySelector('.countdown-title');
            if (countdownTitle) {
                countdownTitle.textContent = '🎉 Airdrop is LIVE!';
                countdownTitle.style.color = '#ffd700';
            }

            // متوقف کردن شمارش معکوس
            if (countdownInterval) {
                clearInterval(countdownInterval);
                countdownInterval = null;
            }
        }

    } catch (error) {
        console.error('❌ Countdown error:', error);
    }
}

// **شروع شمارش معکوس**
function startCountdown() {
    log('⏰ Starting countdown timer...');
    
    // اجرا فوری
    updateCountdown();
    
    // شروع interval
    if (countdownInterval) {
        clearInterval(countdownInterval);
    }
    countdownInterval = setInterval(updateCountdown, 1000);
    
    log('✅ Countdown timer started successfully');
}

// **متوقف کردن شمارش معکوس**
function stopCountdown() {
    if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
        log('⏹️ Countdown timer stopped');
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
            // اصلاح رنگ متن به سفید
            walletButtonText.style.color = '#ffffff';
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
            walletButtonText.style.color = '#ffffff'; // رنگ سفید برای متن
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

// **تابع بروزرسانی همه UI ها**
function updateAllTasksUI() {
    updateTaskCompleteUI();
    updateInviteFriendsUI();
    updateWalletUI();
    updateCommissionUI();
    updateClaimButton();
}

// **تابع نمایش Toast**
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    // نمایش toast
    setTimeout(() => toast.classList.add('show'), 100);
    
    // حذف toast
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => document.body.removeChild(toast), 300);
    }, 3000);
}

// **تابع detect کردن Phantom Wallet**
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

// **تابع connect کردن کیف پول**
async function connectWallet() {
    try {
        if (!await detectPhantom()) {
            showPhantomModal();
            return;
        }

        log('🔗 Connecting to Phantom Wallet...');
        const resp = await phantomProvider.connect();
        
        if (resp.publicKey) {
            connectedWallet = resp.publicKey.toString();
            tasksCompleted.wallet = true;
            
            // ارسال به سرور
            await sendWalletToServer(connectedWallet);
            
            updateWalletUI();
            showToast('Wallet connected successfully!', 'success');
            
            log('✅ Wallet connected: ' + connectedWallet);
        }

    } catch (error) {
        log('❌ Wallet connection failed: ' + error.message);
        showToast('Failed to connect wallet: ' + error.message, 'error');
    }
}

// **تابع disconnect کردن کیف پول**
async function disconnectWallet() {
    try {
        if (phantomProvider && phantomProvider.disconnect) {
            await phantomProvider.disconnect();
        }
        
        // ارسال درخواست disconnect به سرور
        await sendWalletToServer('');
        
        connectedWallet = '';
        tasksCompleted.wallet = false;
        
        updateWalletUI();
        showToast('Wallet disconnected successfully!', 'info');
        
        log('🔌 Wallet disconnected');

    } catch (error) {
        log('❌ Wallet disconnect failed: ' + error.message);
        showToast('Failed to disconnect wallet: ' + error.message, 'error');
    }
}

// **تابع ارسال آدرس کیف پول به سرور**
async function sendWalletToServer(walletAddress) {
    try {
        const response = await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ wallet: walletAddress })
        });

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || 'Failed to update wallet');
        }

        log('✅ Wallet updated on server: ' + (walletAddress || 'disconnected'));
        return true;

    } catch (error) {
        log('❌ Server update failed: ' + error.message);
        throw error;
    }
}

// **تابع نمایش modal برای Phantom**
function showPhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.classList.add('show');
    }
}

// **تابع بستن modal Phantom**
function hidePhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.classList.remove('show');
    }
}

// **تابع بارگذاری وضعیت از سرور**
async function loadStatusFromServer() {
    try {
        log('📊 Loading status from server...');
        
        // بارگذاری وضعیت tasks
        const tasksResponse = await fetch('/airdrop/tasks_status');
        const tasksData = await tasksResponse.json();
        
        // بارگذاری وضعیت referrals
        const referralResponse = await fetch('/airdrop/referral_status');
        const referralData = await referralResponse.json();
        
        // بارگذاری وضعیت commission
        const commissionResponse = await fetch('/airdrop/commission_status');
        const commissionData = await commissionResponse.json();

        // بروزرسانی state
        tasksCompleted.task = tasksData.tasks_completed || false;
        tasksCompleted.invite = referralData.has_referrals || false;
        tasksCompleted.wallet = commissionData.wallet_connected || false;
        tasksCompleted.pay = commissionData.commission_paid || false;
        
        if (commissionData.wallet_address) {
            connectedWallet = commissionData.wallet_address;
        }

        // بروزرسانی UI
        updateAllTasksUI();
        
        log('✅ Status loaded from server');

    } catch (error) {
        log('❌ Failed to load status: ' + error.message);
        showToast('Failed to load current status', 'error');
    }
}

// **Event Listeners**
document.addEventListener('DOMContentLoaded', function() {
    log('🚀 DOM loaded, initializing airdrop page...');
    
    // شروع شمارشگر معکوس
    startCountdown();
    
    // بارگذاری وضعیت از سرور
    loadStatusFromServer();
    
    // تنظیم event listeners
    const connectWalletBtn = document.getElementById('connect-wallet');
    if (connectWalletBtn) {
        connectWalletBtn.addEventListener('click', connectWallet);
    }

    // تنظیم dropdown برای کیف پول
    const walletDropdown = document.querySelector('.wallet-dropdown');
    if (walletDropdown) {
        walletDropdown.addEventListener('click', function(e) {
            e.stopPropagation();
            if (tasksCompleted.wallet && connectedWallet) {
                const dropdown = this.querySelector('.wallet-dropdown-content');
                if (dropdown) {
                    dropdown.classList.toggle('show');
                }
            }
        });
    }

    // بستن dropdown با کلیک خارج
    document.addEventListener('click', function() {
        const dropdowns = document.querySelectorAll('.wallet-dropdown-content');
        dropdowns.forEach(dropdown => {
            dropdown.classList.remove('show');
        });
    });

    // دکمه disconnect در dropdown
    const disconnectBtn = document.getElementById('disconnect-wallet');
    if (disconnectBtn) {
        disconnectBtn.addEventListener('click', disconnectWallet);
    }

    // بستن modal phantom
    const closePhantomBtn = document.getElementById('close-phantom-modal');
    if (closePhantomBtn) {
        closePhantomBtn.addEventListener('click', hidePhantomModal);
    }

    log('✅ Airdrop page initialized successfully');
});

// **تمیز کردن interval ها هنگام خروج**
window.addEventListener('beforeunload', function() {
    stopCountdown();
});

// **Export functions برای استفاده در HTML**
window.connectWallet = connectWallet;
window.disconnectWallet = disconnectWallet;
window.showPhantomModal = showPhantomModal;
window.hidePhantomModal = hidePhantomModal;

// **تابع handle کردن کلیک دکمه commission**
async function handleCommissionPayment() {
    try {
        log('💰 Commission payment clicked');

        // بررسی اتصال کیف پول
        if (!tasksCompleted.wallet || !connectedWallet) {
            showToast('Please connect your wallet first', 'error');
            log('❌ Wallet not connected for commission payment');
            return;
        }

        // بررسی اینکه قبلاً پرداخت شده باشد
        if (tasksCompleted.pay) {
            showToast('Commission already paid!', 'info');
            log('ℹ️ Commission already paid');
            return;
        }

        // نمایش loading state
        const commissionButton = document.querySelector('#pay-commission .task-button');
        const commissionIcon = document.getElementById('commission-icon');
        
        if (commissionButton) {
            commissionButton.classList.add('loading');
        }
        if (commissionIcon) {
            commissionIcon.className = 'fas fa-spinner fa-spin right-icon';
        }

        log('🔄 Starting commission payment process...');

        // هدایت به صفحه پرداخت
        const commissionUrl = `/commission/browser/pay?telegram_id=${USER_ID}`;
        window.location.href = commissionUrl;

    } catch (error) {
        log('❌ Commission payment error: ' + error.message);
        showToast('Commission payment failed: ' + error.message, 'error');

        // برگرداندن UI به حالت عادی
        const commissionButton = document.querySelector('#pay-commission .task-button');
        const commissionIcon = document.getElementById('commission-icon');
        
        if (commissionButton) {
            commissionButton.classList.remove('loading');
        }
        if (commissionIcon) {
            commissionIcon.className = 'fas fa-chevron-right right-icon';
        }
    }
}

// **تابع handle کردن کلیک دکمه task completion**
async function handleTaskCompletion() {
    try {
        log('📋 Task completion clicked');
        
        if (tasksCompleted.task) {
            showToast('Tasks already completed!', 'info');
            return;
        }

        // هدایت به صفحه earn
        window.location.href = '/earn';
        
    } catch (error) {
        log('❌ Task completion error: ' + error.message);
        showToast('Failed to navigate to tasks: ' + error.message, 'error');
    }
}

// **تابع handle کردن کلیک دکمه invite friends**
async function handleInviteCheck() {
    try {
        log('👥 Invite friends clicked');
        
        if (tasksCompleted.invite) {
            showToast('Friends already invited!', 'info');
            return;
        }

        // هدایت به صفحه friends
        window.location.href = '/friends';
        
    } catch (error) {
        log('❌ Invite friends error: ' + error.message);
        showToast('Failed to navigate to friends: ' + error.message, 'error');
    }
}

// **تابع بررسی وضعیت پرداخت کمیسیون از سرور**
async function checkCommissionStatus() {
    try {
        log('🔍 Checking commission status...');
        
        const response = await fetch(`/commission/status?telegram_id=${USER_ID}`);
        const data = await response.json();

        if (response.ok) {
            if (data.commission_paid) {
                tasksCompleted.pay = true;
                updateCommissionUI();
                log('✅ Commission payment confirmed by server');
            }
        } else {
            log('⚠️ Failed to check commission status: ' + data.detail);
        }

    } catch (error) {
        log('❌ Commission status check error: ' + error.message);
    }
}

// **تابع بررسی وضعیت اتصال کیف پول از سرور**
async function checkWalletStatus() {
    try {
        log('🔍 Checking wallet status...');
        
        const response = await fetch(`/airdrop/wallet_status?telegram_id=${USER_ID}`);
        const data = await response.json();

        if (response.ok) {
            if (data.wallet_connected && data.wallet_address) {
                connectedWallet = data.wallet_address;
                tasksCompleted.wallet = true;
                updateWalletUI();
                log('✅ Wallet connection confirmed by server: ' + data.wallet_address);
            } else {
                connectedWallet = '';
                tasksCompleted.wallet = false;
                updateWalletUI();
                log('ℹ️ No wallet connected on server');
            }
        } else {
            log('⚠️ Failed to check wallet status: ' + data.detail);
        }

    } catch (error) {
        log('❌ Wallet status check error: ' + error.message);
    }
}

// **بررسی وضعیت‌ها هنگام load شدن صفحه**
async function initializePageStatus() {
    log('🚀 Initializing page status...');
    
    try {
        // بررسی وضعیت کیف پول
        await checkWalletStatus();
        
        // بررسی وضعیت کمیسیون
        await checkCommissionStatus();
        
        // بروزرسانی همه UI ها
        updateAllTasksUI();
        
        log('✅ Page status initialized successfully');
        
    } catch (error) {
        log('❌ Failed to initialize page status: ' + error.message);
    }
}
