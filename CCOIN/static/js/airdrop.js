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
        setTimeout(() => {
            if (document.body.contains(toast)) {
                document.body.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

// =============================================================================
// 🔧 WALLET DROPDOWN FUNCTIONALITY - اضافه شده برای حل مشکل منوی کشویی
// =============================================================================

// تابع اصلی handle کردن کلیک روی دکمه wallet
function handleWalletConnection() {
    log('🖱️ Wallet button clicked');
    
    // اگر wallet متصل است، dropdown menu را toggle کن
    if (tasksCompleted.wallet && connectedWallet) {
        log('💳 Wallet connected - toggling dropdown');
        toggleWalletDropdown();
    } else {
        log('🔗 Wallet not connected - starting connection process');
        // اگر متصل نیست، فرآیند اتصال را شروع کن
        connectPhantomWallet();
    }
}

// تابع toggle کردن dropdown menu
function toggleWalletDropdown() {
    const dropdown = document.getElementById('wallet-dropdown-content');
    
    if (!dropdown) {
        log('❌ Dropdown element not found');
        return;
    }
    
    if (dropdown.classList.contains('show')) {
        dropdown.classList.remove('show');
        log('🔽 Wallet dropdown closed');
    } else {
        // ابتدا همه dropdown های دیگر را ببند
        closeAllDropdowns();
        
        dropdown.classList.add('show');
        log('🔼 Wallet dropdown opened');
        
        // Auto close after 10 seconds
        setTimeout(() => {
            if (dropdown.classList.contains('show')) {
                dropdown.classList.remove('show');
                log('⏰ Dropdown auto-closed after 10 seconds');
            }
        }, 10000);
    }
}

// تابع بستن همه dropdown ها
function closeAllDropdowns() {
    const dropdowns = document.querySelectorAll('.wallet-dropdown-content');
    dropdowns.forEach(dropdown => {
        dropdown.classList.remove('show');
    });
    log('🔒 All dropdowns closed');
}

// تابع change wallet
function changeWallet() {
    log('🔄 Changing wallet...');
    closeAllDropdowns();
    
    // نمایش toast
    showToast('Disconnecting current wallet...', 'info');
    
    // disconnect کردن wallet فعلی و اتصال مجدد
    disconnectWallet();
    
    // کمی صبر کن و سپس دوباره connect کن
    setTimeout(() => {
        log('🔄 Reconnecting to new wallet...');
        connectPhantomWallet();
    }, 1000);
}

// تابع disconnect wallet
function disconnectWallet() {
    log('🔌 Disconnecting wallet...');
    closeAllDropdowns();
    
    // نمایش loading state
    const walletButton = document.querySelector('#connect-wallet .task-button');
    if (walletButton) {
        walletButton.classList.add('loading');
    }
    
    // پاک کردن state
    const previousWallet = connectedWallet;
    connectedWallet = '';
    tasksCompleted.wallet = false;
    
    // بروزرسانی UI
    updateWalletUI();
    updateClaimButton();
    
    // ارسال درخواست disconnect به سرور
    fetch('/airdrop/connect_wallet', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            wallet: '' // آدرس خالی برای disconnect
        })
    })
    .then(response => response.json())
    .then(data => {
        // حذف loading state
        if (walletButton) {
            walletButton.classList.remove('loading');
        }
        
        if (data.success) {
            showToast('Wallet disconnected successfully', 'success');
            log(`✅ Wallet ${previousWallet.substring(0,8)}... disconnected from server`);
        } else {
            showToast('Failed to disconnect wallet', 'error');
            log('❌ Failed to disconnect wallet from server');
            
            // در صورت خطا، state را برگردان
            connectedWallet = previousWallet;
            tasksCompleted.wallet = true;
            updateWalletUI();
            updateClaimButton();
        }
    })
    .catch(error => {
        // حذف loading state
        if (walletButton) {
            walletButton.classList.remove('loading');
        }
        
        console.error('Disconnect error:', error);
        showToast('Error disconnecting wallet', 'error');
        log('❌ Network error during disconnect');
        
        // در صورت خطا، state را برگردان
        connectedWallet = previousWallet;
        tasksCompleted.wallet = true;
        updateWalletUI();
        updateClaimButton();
    });
}

// Event listener برای بستن dropdown هنگام کلیک outside
document.addEventListener('click', function(event) {
    const walletDropdown = document.querySelector('.wallet-dropdown');
    const dropdown = document.getElementById('wallet-dropdown-content');
    
    // اگر کلیک خارج از wallet dropdown بود، آن را ببند
    if (dropdown && dropdown.classList.contains('show') && !walletDropdown.contains(event.target)) {
        dropdown.classList.remove('show');
        log('🖱️ Dropdown closed by outside click');
    }
});

// Event listener برای ESC key برای بستن dropdown
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const dropdown = document.getElementById('wallet-dropdown-content');
        if (dropdown && dropdown.classList.contains('show')) {
            closeAllDropdowns();
            log('⌨️ Dropdown closed by ESC key');
        }
    }
});

// تابع مقداردهی اولیه dropdown functionality
function initializeWalletDropdown() {
    log('🔧 Initializing wallet dropdown functionality...');
    
    // بررسی وجود المان‌های ضروری
    const walletButton = document.querySelector('#connect-wallet .task-button');
    const dropdown = document.getElementById('wallet-dropdown-content');
    
    if (!walletButton) {
        log('❌ Wallet button not found');
        return false;
    }
    
    if (!dropdown) {
        log('❌ Dropdown element not found');
        return false;
    }
    
    // تنظیم onclick event
    walletButton.onclick = handleWalletConnection;
    
    log('✅ Wallet dropdown initialized successfully');
    return true;
}

// اضافه کردن به event listener اصلی
document.addEventListener('DOMContentLoaded', function() {
    log('📱 DOM Content Loaded - Initializing wallet dropdown...');
    
    // تاخیر کوتاه برای اطمینان از load شدن همه المان‌ها
    setTimeout(() => {
        const success = initializeWalletDropdown();
        if (success) {
            log('🎉 Wallet dropdown functionality ready!');
        } else {
            log('⚠️ Failed to initialize wallet dropdown');
        }
    }, 100);
});
