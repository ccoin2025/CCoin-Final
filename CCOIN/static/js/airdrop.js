// =============================================================================
// 🚀 CCOIN AIRDROP PAGE - COMPLETE JAVASCRIPT FILE
// =============================================================================

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

// =============================================================================
// ⏰ COUNTDOWN TIMER FUNCTIONALITY
// =============================================================================

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

// =============================================================================
// 🎨 UI UPDATE FUNCTIONS
// =============================================================================

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
            walletButtonText.style.color = '#ffffff';
            walletButtonText.title = `Full address: ${connectedWallet}`; // tooltip برای آدرس کامل
        }

        // تغییر آیکون به چک سبز
        if (walletIcon) {
            walletIcon.className = 'fas fa-check right-icon';
            walletIcon.style.color = '#28a745';
        }

        // اضافه کردن کلاس connected
        if (walletButton) {
            walletButton.classList.add('wallet-connected');
            walletButton.title = 'Click to manage wallet'; // tooltip
        }

        // نمایش status indicator سبز
        if (walletStatusIndicator) {
            walletStatusIndicator.classList.add('connected');
        }

        log(`✅ Wallet UI updated: ${shortAddress}`);

    } else {
        // حالت disconnect
        if (walletButtonText) {
            walletButtonText.textContent = 'Connect Wallet';
            walletButtonText.style.color = '#ffffff';
            walletButtonText.title = 'Click to connect your Phantom wallet';
        }

        if (walletIcon) {
            walletIcon.className = 'fas fa-chevron-right right-icon';
            walletIcon.style.color = '#aaa';
        }

        if (walletButton) {
            walletButton.classList.remove('wallet-connected');
            walletButton.title = 'Connect your Phantom wallet to continue';
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
        
        // نمایش پیام تبریک
        const congratsMessage = document.getElementById('congratulationsMessage');
        if (congratsMessage) {
            congratsMessage.style.display = 'block';
        }
    } else {
        claimButton.disabled = true;
        claimButton.textContent = 'Complete all tasks to claim';
        claimButton.style.background = 'rgba(255, 255, 255, 0.1)';
        claimButton.style.color = 'rgba(255, 255, 255, 0.5)';
        
        // مخفی کردن پیام تبریک
        const congratsMessage = document.getElementById('congratulationsMessage');
        if (congratsMessage) {
            congratsMessage.style.display = 'none';
        }
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

// =============================================================================
// 🔔 TOAST NOTIFICATIONS
// =============================================================================

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
// 👻 PHANTOM WALLET DETECTION AND CONNECTION
// =============================================================================

// **تابع detect کردن Phantom Wallet**
async function detectPhantom() {
    try {
        if (window.solana && window.solana.isPhantom) {
            phantomProvider = window.solana;
            phantomDetected = true;
            log('✅ Phantom wallet detected');
            return true;
        }

        // تلاش مجدد بعد از 500ms
        await new Promise(resolve => setTimeout(resolve, 500));
        
        if (window.solana && window.solana.isPhantom) {
            phantomProvider = window.solana;
            phantomDetected = true;
            log('✅ Phantom wallet detected (retry)');
            return true;
        }

        log('⚠️ Phantom wallet not detected');
        return false;

    } catch (error) {
        console.error('❌ Error detecting Phantom:', error);
        return false;
    }
}

// تابع بهبود یافته اتصال به Phantom
async function connectPhantomWallet() {
    log('🔗 Starting Phantom wallet connection...');
    
    try {
        // بررسی وجود Phantom
        if (!phantomDetected || !phantomProvider) {
            log('❌ Phantom not detected - showing modal');
            showPhantomModal();
            return;
        }
        
        // نمایش loading state
        const walletButton = document.querySelector('#connect-wallet .task-button');
        if (walletButton) {
            walletButton.classList.add('loading');
        }
        
        showToast('Connecting to Phantom Wallet...', 'info');
        
        // درخواست اتصال
        const response = await phantomProvider.connect();
        
        if (response.publicKey) {
            const walletAddress = response.publicKey.toString();
            log(`✅ Phantom connected: ${walletAddress}`);
            
            // ارسال به سرور
            const serverResponse = await fetch('/airdrop/connect_wallet', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    wallet: walletAddress
                })
            });
            
            const serverData = await serverResponse.json();
            
            if (serverData.success) {
                // بروزرسانی state
                connectedWallet = walletAddress;
                tasksCompleted.wallet = true;
                
                // بروزرسانی UI
                updateWalletUI();
                updateClaimButton();
                
                showToast('Wallet connected successfully!', 'success');
                log(`✅ Wallet connected and saved to server: ${walletAddress}`);
                
            } else {
                throw new Error(serverData.message || 'Server rejected wallet connection');
            }
        } else {
            throw new Error('No public key received from Phantom');
        }
        
    } catch (error) {
        console.error('❌ Phantom connection error:', error);
        
        let errorMessage = 'Failed to connect wallet';
        if (error.message.includes('User rejected')) {
            errorMessage = 'Connection cancelled by user';
        } else if (error.message.includes('already connected')) {
            errorMessage = 'Wallet already connected to another account';
        }
        
        showToast(errorMessage, 'error');
        log(`❌ Connection failed: ${error.message}`);
        
    } finally {
        // حذف loading state
        const walletButton = document.querySelector('#connect-wallet .task-button');
        if (walletButton) {
            walletButton.classList.remove('loading');
        }
    }
}

// =============================================================================
// 🔧 WALLET DROPDOWN FUNCTIONALITY
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

// =============================================================================
// 📋 TASK HANDLERS
// =============================================================================

// **تابع handle کردن task completion**
async function handleTaskCompletion() {
    log('📋 Checking task completion...');
    
    try {
        const response = await fetch('/airdrop/tasks_status');
        const data = await response.json();
        
        if (data.tasks_completed) {
            tasksCompleted.task = true;
            updateTaskCompleteUI();
            updateClaimButton();
            showToast('Tasks completed successfully!', 'success');
            log('✅ Tasks marked as completed');
        } else {
            // هدایت به صفحه earn
            window.location.href = '/earn';
            log('📋 Redirecting to earn page');
        }
        
    } catch (error) {
        console.error('❌ Error checking tasks:', error);
        showToast('Error checking tasks', 'error');
        
        // در صورت خطا، هدایت به صفحه earn
        window.location.href = '/earn';
    }
}

// **تابع handle کردن invite check**
async function handleInviteCheck() {
    log('👥 Checking invite status...');
    
    try {
        const response = await fetch('/airdrop/referral_status');
        const data = await response.json();
        
        if (data.has_referrals) {
            tasksCompleted.invite = true;
            updateInviteFriendsUI();
            updateClaimButton();
            showToast(`You have invited ${data.referral_count} friends!`, 'success');
            log(`✅ Referrals confirmed: ${data.referral_count}`);
        } else {
            // هدایت به صفحه friends
            window.location.href = '/friends';
            log('👥 Redirecting to friends page');
        }
        
    } catch (error) {
        console.error('❌ Error checking referrals:', error);
        showToast('Error checking referrals', 'error');
        
        // در صورت خطا، هدایت به صفحه friends
        window.location.href = '/friends';
    }
}

// **تابع handle کردن commission payment**
async function handleCommissionPayment() {
    log('💰 Starting commission payment...');
    
    // بررسی وجود wallet متصل
    if (!tasksCompleted.wallet || !connectedWallet) {
        showToast('Please connect your wallet first', 'error');
        log('❌ No wallet connected for commission payment');
        return;
    }
    
    // بررسی اینکه آیا قبلاً پرداخت شده یا نه
    if (tasksCompleted.pay) {
        showToast('Commission already paid', 'info');
        log('ℹ️ Commission already paid');
        return;
    }
    
    try {
        // نمایش loading state
        const commissionButton = document.getElementById('commission-button');
        if (commissionButton) {
            commissionButton.classList.add('loading');
        }
        
        showToast('Processing commission payment...', 'info');
        
        // ایجاد transaction
        if (!phantomProvider) {
            throw new Error('Phantom wallet not available');
        }
        
        const { Connection, PublicKey, Transaction, SystemProgram, LAMPORTS_PER_SOL } = window.solanaWeb3;
        const connection = new Connection(SOLANA_RPC_URL);
        
        // مقدار کمیسیون به lamports
        const lamports = Math.floor(COMMISSION_AMOUNT * LAMPORTS_PER_SOL);
        
        // ایجاد transaction
        const transaction = new Transaction().add(
            SystemProgram.transfer({
                fromPubkey: new PublicKey(connectedWallet),
                toPubkey: new PublicKey(ADMIN_WALLET),
                lamports: lamports,
            })
        );
        
        // دریافت recent blockhash
        const { blockhash } = await connection.getRecentBlockhash();
        transaction.recentBlockhash = blockhash;
        transaction.feePayer = new PublicKey(connectedWallet);
        
        // امضا کردن transaction
        const signedTransaction = await phantomProvider.signTransaction(transaction);
        
        // ارسال transaction
        const signature = await connection.sendRawTransaction(signedTransaction.serialize());
        
        log(`📝 Transaction sent: ${signature}`);
        showToast('Transaction sent, confirming...', 'info');
        
        // تأیید transaction
        await connection.confirmTransaction(signature);
        
        // ارسال تأیید به سرور
        const response = await fetch('/airdrop/confirm_commission', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                signature: signature,
                amount: COMMISSION_AMOUNT,
                recipient: ADMIN_WALLET
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            tasksCompleted.pay = true;
            updateCommissionUI();
            updateClaimButton();
            showToast('Commission paid successfully!', 'success');
            log(`✅ Commission payment confirmed: ${signature}`);
        } else {
            throw new Error(data.message || 'Server rejected commission payment');
        }
        
    } catch (error) {
        console.error('❌ Commission payment error:', error);
        
        let errorMessage = 'Failed to pay commission';
        if (error.message.includes('User rejected')) {
            errorMessage = 'Payment cancelled by user';
        } else if (error.message.includes('insufficient funds')) {
            errorMessage = 'Insufficient SOL balance';
        }
        
        showToast(errorMessage, 'error');
        log(`❌ Commission payment failed: ${error.message}`);
        
    } finally {
        // حذف loading state
        const commissionButton = document.getElementById('commission-button');
        if (commissionButton) {
            commissionButton.classList.remove('loading');
        }
    }
}

// =============================================================================
// 🎁 CLAIM AIRDROP FUNCTIONALITY
// =============================================================================

// **تابع claim کردن airdrop**
async function claimAirdrop() {
    log('🎁 Starting airdrop claim...');
    
    // بررسی تکمیل همه تسک‌ها
    if (!tasksCompleted.task || !tasksCompleted.invite || !tasksCompleted.wallet || !tasksCompleted.pay) {
        showToast('Please complete all tasks first', 'error');
        log('❌ Not all tasks completed for claim');
        return;
    }
    
    try {
        showToast('Processing airdrop claim...', 'info');
        
        // درخواست claim به سرور
        const response = await fetch('/airdrop/claim', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Airdrop claimed successfully!', 'success');
            log('🎉 Airdrop claimed successfully');
            
            // بروزرسانی UI
            const claimButton = document.getElementById('claimBtn');
            if (claimButton) {
                claimButton.textContent = 'Claimed Successfully!';
                claimButton.disabled = true;
                claimButton.style.background = '#28a745';
                claimButton.style.color = '#fff';
            }
            
        } else {
            throw new Error(data.message || 'Failed to claim airdrop');
        }
        
    } catch (error) {
        console.error('❌ Claim error:', error);
        showToast('Failed to claim airdrop', 'error');
        log(`❌ Claim failed: ${error.message}`);
    }
}

// =============================================================================
// 📱 MODAL FUNCTIONS
// =============================================================================

// **تابع نمایش Phantom modal**
function showPhantomModal() {
    const modal = document.getElementById('phantomModal');
    if (modal) {
        modal.classList.add('show');
        log('👻 Phantom modal shown');
    }
}

// **تابع بستن Phantom modal**
function closePhantomModal() {
    const modal = document.getElementById('phantomModal');
    if (modal) {
        modal.classList.remove('show');
        log('👻 Phantom modal closed');
    }
}

// **تابع باز کردن Phantom wallet**
function openPhantomWallet() {
    log('👻 Opening Phantom wallet...');
    closePhantomModal();
    
    // باز کردن لینک دانلود Phantom
    window.open('https://phantom.app/', '_blank');
    
    showToast('Please install Phantom wallet and refresh the page', 'info');
}

// =============================================================================
// 🎯 EVENT LISTENERS
// =============================================================================

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

// Event listener برای جلوگیری از propagation روی dropdown content
document.addEventListener('DOMContentLoaded', function() {
    const dropdownContent = document.getElementById('wallet-dropdown-content');
    if (dropdownContent) {
        dropdownContent.addEventListener('click', function(event) {
            event.stopPropagation();
        });
    }
});

// =============================================================================
// 🚀 INITIALIZATION FUNCTIONS
// =============================================================================

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

// **تابع مقداردهی اولیه صفحه**
async function initializePage() {
    log('🚀 Initializing airdrop page...');
    
    try {
        // شروع شمارش معکوس
        startCountdown();
        
        // detect کردن Phantom wallet
        await detectPhantom();
        
        // مقداردهی اولیه UI
        updateAllTasksUI();
        
        // مقداردهی dropdown
        const dropdownSuccess = initializeWalletDropdown();
        
        // تنظیم claim button event
        const claimButton = document.getElementById('claimBtn');
        if (claimButton) {
            claimButton.onclick = claimAirdrop;
        }
        
        log('✅ Page initialization completed successfully');
        
        // نمایش وضعیت اولیه
        if (phantomDetected) {
            log('👻 Phantom wallet is available');
        } else {
            log('⚠️ Phantom wallet not detected');
        }
        
        log(`🎯 Initial task status: Task=${tasksCompleted.task}, Invite=${tasksCompleted.invite}, Wallet=${tasksCompleted.wallet}, Pay=${tasksCompleted.pay}`);
        
    } catch (error) {
        console.error('❌ Initialization error:', error);
        showToast('Initialization error', 'error');
    }
}

// تابع پیش‌بارگذاری داده‌ها از سرور
async function loadInitialData() {
    log('📊 Loading initial data from server...');
    
    try {
        // بارگذاری وضعیت tasks
        const tasksResponse = await fetch('/airdrop/tasks_status');
        const tasksData = await tasksResponse.json();
        tasksCompleted.task = tasksData.tasks_completed;
        
        // بارگذاری وضعیت referrals
        const referralResponse = await fetch('/airdrop/referral_status');
        const referralData = await referralResponse.json();
        tasksCompleted.invite = referralData.has_referrals;
        
        // بارگذاری وضعیت wallet و commission
        const commissionResponse = await fetch('/airdrop/commission_status');
        const commissionData = await commissionResponse.json();
        tasksCompleted.wallet = commissionData.wallet_connected;
        tasksCompleted.pay = commissionData.commission_paid;
        connectedWallet = commissionData.wallet_address || '';
        
        log('✅ Initial data loaded successfully');
        
        // بروزرسانی UI
        updateAllTasksUI();
        
    } catch (error) {
        console.error('❌ Error loading initial data:', error);
        log('⚠️ Using default values due to server error');
    }
}

// =============================================================================
// 🛠️ DEBUG AND UTILITY FUNCTIONS
// =============================================================================

// Debug function برای تست
window.debugWalletDropdown = function() {
    console.log('🔍 Wallet Dropdown Debug Info:');
    console.log('Connected Wallet:', connectedWallet);
    console.log('Tasks Completed:', tasksCompleted);
    console.log('Phantom Detected:', phantomDetected);
    
    const dropdown = document.getElementById('wallet-dropdown-content');
    console.log('Dropdown Element:', dropdown);
    console.log('Dropdown Classes:', dropdown ? dropdown.className : 'Not found');
    
    const walletButton = document.querySelector('#connect-wallet .task-button');
    console.log('Wallet Button:', walletButton);
    console.log('Button Classes:', walletButton ? walletButton.className : 'Not found');
};

// Debug function برای تست همه functionality ها
window.debugAirdropPage = function() {
    console.log('🔍 Airdrop Page Debug Info:');
    console.log('APP_CONFIG:', window.APP_CONFIG);
    console.log('Tasks Completed:', tasksCompleted);
    console.log('Connected Wallet:', connectedWallet);
    console.log('Phantom Provider:', phantomProvider);
    console.log('Phantom Detected:', phantomDetected);
    console.log('Countdown Interval:', countdownInterval);
    
    // تست همه المان‌ها
    const elements = {
        'claimBtn': document.getElementById('claimBtn'),
        'wallet-button': document.querySelector('#connect-wallet .task-button'),
        'dropdown': document.getElementById('wallet-dropdown-content'),
        'countdown-days': document.getElementById('days'),
        'countdown-hours': document.getElementById('hours'),
        'countdown-minutes': document.getElementById('minutes'),
        'countdown-seconds': document.getElementById('seconds')
    };
    
    console.log('Page Elements:', elements);
};

// =============================================================================
// 🎬 MAIN INITIALIZATION
// =============================================================================

// اجرای اصلی هنگام بارگذاری DOM
document.addEventListener('DOMContentLoaded', async function() {
    log('📱 DOM Content Loaded - Starting initialization...');
    
    try {
        // بارگذاری داده‌های اولیه
        await loadInitialData();
        
        // مقداردهی اولیه صفحه
        await initializePage();
        
        log('🎉 Airdrop page ready!');
        
    } catch (error) {
        console.error('❌ Critical initialization error:', error);
        showToast('Page initialization failed', 'error');
    }
});

// تمیز کردن resources هنگام خروج از صفحه
window.addEventListener('beforeunload', function() {
    stopCountdown();
    log('🧹 Page cleanup completed');
});

log('✅ Airdrop.js loaded successfully!');
