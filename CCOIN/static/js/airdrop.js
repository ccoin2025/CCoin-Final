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
        // تاریخ هدف: 1 ژانویه 2025 (میتونید تغییر بدید)
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

            // بروزرسانی با انیمیشن
            if (daysElement) {
                const newValue = days.toString().padStart(2, '0');
                if (daysElement.textContent !== newValue) {
                    daysElement.classList.add('flip');
                    setTimeout(() => {
                        daysElement.textContent = newValue;
                        daysElement.classList.remove('flip');
                    }, 300);
                }
            }

            if (hoursElement) {
                const newValue = hours.toString().padStart(2, '0');
                if (hoursElement.textContent !== newValue) {
                    hoursElement.classList.add('flip');
                    setTimeout(() => {
                        hoursElement.textContent = newValue;
                        hoursElement.classList.remove('flip');
                    }, 300);
                }
            }

            if (minutesElement) {
                const newValue = minutes.toString().padStart(2, '0');
                if (minutesElement.textContent !== newValue) {
                    minutesElement.classList.add('flip');
                    setTimeout(() => {
                        minutesElement.textContent = newValue;
                        minutesElement.classList.remove('flip');
                    }, 300);
                }
            }

            if (secondsElement) {
                const newValue = seconds.toString().padStart(2, '0');
                if (secondsElement.textContent !== newValue) {
                    secondsElement.classList.add('flip');
                    setTimeout(() => {
                        secondsElement.textContent = newValue;
                        secondsElement.classList.remove('flip');
                    }, 300);
                }
            }

            // فقط هر 10 ثانیه log کن تا spam نشود
            if (seconds % 10 === 0) {
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
                log('👥 Referral status: ' + (referralData.has_referrals ? 'Has referrals' : 'No referrals'));
            }
        } catch (e) {
            log('⚠️ Could not check referral status: ' + e.message);
        }

        // چک کردن وضعیت tasks
        try {
            const tasksResponse = await fetch('/airdrop/tasks_status');
            if (tasksResponse.ok) {
                const tasksData = await tasksResponse.json();
                tasksCompleted.task = tasksData.tasks_completed;
                log('📋 Tasks status: ' + (tasksData.tasks_completed ? 'Completed' : 'Not completed'));
            }
        } catch (e) {
            log('⚠️ Could not check tasks status: ' + e.message);
        }

        // بروزرسانی UI
        updateAllTasksUI();
        
        log('✅ All status checked successfully');
    } catch (error) {
        console.error('❌ Error checking status from server:', error);
        showToast('Error checking status from server', 'error');
    }
}

// **تابع نمایش Toast**
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    const container = document.getElementById('toast-container') || document.body;
    container.appendChild(toast);
    
    // نمایش toast
    setTimeout(() => toast.classList.add('show'), 10);
    
    // حذف پس از 3 ثانیه
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// **تابع‌های مختلف handlers**
async function handleTaskCompletion() {
    log('📋 Handling task completion...');
    // Redirect to tasks page
    window.location.href = '/earn?telegram_id=' + USER_ID;
}

async function handleInviteCheck() {
    log('👥 Handling invite check...');
    // Redirect to friends page
    window.location.href = '/friends?telegram_id=' + USER_ID;
}

async function handleWalletConnection() {
    log('💼 Handling wallet connection...');
    
    if (tasksCompleted.wallet && connectedWallet) {
        // اگر کیف پول متصل است، dropdown را نمایش بده
        toggleWalletDropdown();
    } else {
        // اگر کیف پول متصل نیست، اتصال را شروع کن
        await connectPhantomWallet();
    }
}

function toggleWalletDropdown() {
    const dropdown = document.getElementById('wallet-dropdown');
    const addressDisplay = document.getElementById('wallet-address-display');
    
    if (dropdown && connectedWallet) {
        dropdown.classList.toggle('show');
        
        if (addressDisplay) {
            addressDisplay.textContent = connectedWallet;
        }
        
        log('🔄 Wallet dropdown toggled');
    }
}

async function connectPhantomWallet() {
    try {
        log('🔗 Attempting to connect Phantom wallet...');
        
        if (typeof window.solana === 'undefined' || !window.solana.isPhantom) {
            log('❌ Phantom wallet not found');
            showPhantomModal();
            return;
        }

        phantomProvider = window.solana;
        phantomDetected = true;

        const response = await phantomProvider.connect();
        connectedWallet = response.publicKey.toString();
        tasksCompleted.wallet = true;

        // ارسال آدرس کیف پول به سرور
        const submitResponse = await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                wallet_address: connectedWallet
            })
        });

        if (submitResponse.ok) {
            showToast('Wallet connected successfully!', 'success');
            updateWalletUI();
            updateClaimButton();
            log('✅ Wallet connected: ' + connectedWallet.substring(0, 8) + '...');
        } else {
            throw new Error('Failed to save wallet address');
        }

    } catch (error) {
        console.error('❌ Wallet connection error:', error);
        showToast('Failed to connect wallet: ' + error.message, 'error');
    }
}

async function changeWallet() {
    log('🔄 Changing wallet...');
    await disconnectWallet();
    setTimeout(() => connectPhantomWallet(), 500);
}

async function disconnectWallet() {
    try {
        log('🔌 Disconnecting wallet...');
        
        if (phantomProvider && phantomProvider.disconnect) {
            await phantomProvider.disconnect();
        }
        
        connectedWallet = null;
        tasksCompleted.wallet = false;
        
        const dropdown = document.getElementById('wallet-dropdown');
        if (dropdown) {
            dropdown.classList.remove('show');
        }
        
        updateWalletUI();
        updateClaimButton();
        showToast('Wallet disconnected', 'info');
        log('✅ Wallet disconnected successfully');
        
    } catch (error) {
        console.error('❌ Disconnect error:', error);
        showToast('Error disconnecting wallet', 'error');
    }
}

async function handleCommissionPayment() {
    log('💰 Handling commission payment...');
    
    if (tasksCompleted.pay) {
        showToast('Commission already paid!', 'info');
        return;
    }
    
    if (!tasksCompleted.wallet || !connectedWallet) {
        showToast('Please connect your wallet first', 'error');
        return;
    }
    
    showCommissionModal();
}

async function processCommissionPayment() {
    try {
        log('💳 Processing commission payment...');
        
        closeCommissionModal();
        
        const commissionButton = document.querySelector('#pay-commission .task-button');
        const commissionIcon = document.getElementById('commission-icon');
        
        // نمایش loading
        if (commissionButton) {
            commissionButton.classList.add('loading');
        }
        if (commissionIcon) {
            commissionIcon.className = 'fas fa-spinner fa-spin right-icon';
        }
        
        const response = await fetch('/airdrop/pay_commission', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                wallet_address: connectedWallet
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            tasksCompleted.pay = true;
            updateCommissionUI();
            updateClaimButton();
            showToast('Commission paid successfully!', 'success');
            log('✅ Commission payment completed');
        } else {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Commission payment failed');
        }
        
    } catch (error) {
        console.error('❌ Commission payment error:', error);
        showToast('Commission payment failed: ' + error.message, 'error');
    } finally {
        // حذف loading state
        const commissionButton = document.querySelector('#pay-commission .task-button');
        if (commissionButton) {
            commissionButton.classList.remove('loading');
        }
        updateCommissionUI();
    }
}

async function handleClaim() {
    log('🎯 Handling claim...');
    
    const allCompleted = tasksCompleted.task && tasksCompleted.invite && tasksCompleted.wallet && tasksCompleted.pay;
    
    if (!allCompleted) {
        showToast('Please complete all tasks first', 'error');
        return;
    }
    
    try {
        const response = await fetch('/airdrop/claim', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            showToast('Airdrop claimed successfully! 🎉', 'success');
            
            // نمایش پیام تبریک
            const congratulations = document.getElementById('congratulations');
            if (congratulations) {
                congratulations.style.display = 'block';
                congratulations.scrollIntoView({ behavior: 'smooth' });
            }
            
            log('✅ Airdrop claimed successfully');
        } else {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Claim failed');
        }
        
    } catch (error) {
        console.error('❌ Claim error:', error);
        showToast('Claim failed: ' + error.message, 'error');
    }
}

// **تابع‌های Modal**
function showPhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.classList.add('show');
    }
}

function closePhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.classList.remove('show');
    }
}

function showCommissionModal() {
    const modal = document.getElementById('commission-modal');
    if (modal) {
        modal.classList.add('show');
    }
}

function closeCommissionModal() {
    const modal = document.getElementById('commission-modal');
    if (modal) {
        modal.classList.remove('show');
    }
}

// **Event Listeners**
document.addEventListener('DOMContentLoaded', function() {
    log('🚀 DOM loaded, initializing airdrop page...');
    
    // شروع شمارگر معکوس - **این خط مهمترین بخشه که اضافه شده**
    startCountdown();
    
    // بروزرسانی اولیه UI
    updateAllTasksUI();
    
    // چک کردن وضعیت از سرور
    checkAllStatusFromServer();
    
    // اضافه کردن event listener برای کلیک خارج از dropdown
    document.addEventListener('click', function(event) {
        const dropdown = document.getElementById('wallet-dropdown');
        const walletButton = document.querySelector('.wallet-connect-button');
        
        if (dropdown && !walletButton.contains(event.target) && !dropdown.contains(event.target)) {
            dropdown.classList.remove('show');
        }
    });
    
    log('✅ Airdrop page initialized successfully');
});

// **تمیز کردن interval هنگام خروج از صفحه**
window.addEventListener('beforeunload', function() {
    stopCountdown();
});

// **تابع برای تست شمارگر معکوس**
function testCountdown() {
    // تست با تاریخ 30 ثانیه آینده
    const testDate = new Date(Date.now() + 30000);
    console.log('🧪 Testing countdown with date:', testDate.toISOString());
    
    // موقتاً تاریخ هدف را تغییر بده
    const originalUpdate = updateCountdown;
    window.updateCountdown = function() {
        const targetDate = testDate.getTime();
        const now = new Date().getTime();
        const distance = targetDate - now;

        if (distance > 0) {
            const days = Math.floor(distance / (1000 * 60 * 60 * 24));
            const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((distance % (1000 * 60)) / 1000);

            document.getElementById('days').textContent = days.toString().padStart(2, '0');
            document.getElementById('hours').textContent = hours.toString().padStart(2, '0');
            document.getElementById('minutes').textContent = minutes.toString().padStart(2, '0');
            document.getElementById('seconds').textContent = seconds.toString().padStart(2, '0');
            
            console.log(`🧪 Test countdown: ${days}d ${hours}h ${minutes}m ${seconds}s`);
        } else {
            console.log('🧪 Test countdown finished!');
            // بازگشت به تابع اصلی
            window.updateCountdown = originalUpdate;
        }
    };
    
    startCountdown();
    
    // بعد از 35 ثانیه بازگشت به حالت عادی
    setTimeout(() => {
        window.updateCountdown = originalUpdate;
        startCountdown();
        console.log('🧪 Test finished, returned to normal countdown');
    }, 35000);
}
