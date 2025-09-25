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

// **تابع debug وضعیت wallet**
async function debugWalletStatus() {
    try {
        const response = await fetch('/airdrop/debug/wallet_status');
        const data = await response.json();
        console.log('🐛 Wallet Debug:', data);
        return data;
    } catch (error) {
        console.error('Debug failed:', error);
        return null;
    }
}

// **تابع پرداخت کمیسیون اصلاح شده**
async function handleCommissionPayment() {
    try {
        // ابتدا debug وضعیت
        const debugInfo = await debugWalletStatus();
        console.log('💳 Debug info before payment:', debugInfo);
        
        if (debugInfo && debugInfo.error) {
            showToast('Session error: ' + debugInfo.error, 'error');
            return;
        }
        
        if (!debugInfo || !debugInfo.wallet_connected) {
            showToast('Please connect your wallet first!', 'error');
            return;
        }
        
        if (debugInfo.commission_paid) {
            showToast('Commission already paid!', 'info');
            tasksCompleted.pay = true;
            updateCommissionUI();
            return;
        }

        // بررسی وجود Phantom
        if (!await detectPhantom()) {
            showPhantomModal();
            return;
        }

        // درخواست پرداخت کمیسیون
        const commissionButton = document.querySelector('#pay-commission .task-button');
        const commissionIcon = document.getElementById('commission-icon');
        
        // نمایش loading
        if (commissionButton) commissionButton.classList.add('loading');
        if (commissionIcon) commissionIcon.className = 'fas fa-spinner right-icon';

        try {
            // ایجاد تراکنش
            const transaction = new solanaWeb3.Transaction().add(
                solanaWeb3.SystemProgram.transfer({
                    fromPubkey: phantomProvider.publicKey,
                    toPubkey: new solanaWeb3.PublicKey(ADMIN_WALLET),
                    lamports: COMMISSION_AMOUNT * solanaWeb3.LAMPORTS_PER_SOL, // تبدیل SOL به lamports
                })
            );

            // دریافت recent blockhash
            const connection = new solanaWeb3.Connection(SOLANA_RPC_URL);
            const { blockhash } = await connection.getRecentBlockhash();
            transaction.recentBlockhash = blockhash;
            transaction.feePayer = phantomProvider.publicKey;

            // امضا و ارسال تراکنش
            const signedTransaction = await phantomProvider.signTransaction(transaction);
            const signature = await connection.sendRawTransaction(signedTransaction.serialize());

            log('✅ Transaction sent: ' + signature);
            showToast('Transaction sent successfully!', 'success');

            // تایید تراکنش
            await connection.confirmTransaction(signature);
            
            // ارسال به سرور
            const serverResponse = await fetch('/airdrop/pay/commission', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    transaction_hash: signature 
                })
            });

            const serverData = await serverResponse.json();

            if (serverResponse.ok && serverData.success) {
                tasksCompleted.pay = true;
                updateCommissionUI();
                showToast('Commission payment recorded successfully!', 'success');
                log('✅ Commission payment completed: ' + signature);
            } else {
                throw new Error(serverData.detail || 'Server recording failed');
            }

        } catch (txError) {
            log('❌ Transaction failed: ' + txError.message);
            showToast('Transaction failed: ' + txError.message, 'error');
        }

    } catch (error) {
        log('❌ Commission payment error: ' + error.message);
        showToast('Payment failed: ' + error.message, 'error');
    } finally {
        // حذف loading
        const commissionButton = document.querySelector('#pay-commission .task-button');
        const commissionIcon = document.getElementById('commission-icon');
        
        if (commissionButton) commissionButton.classList.remove('loading');
        if (commissionIcon && !tasksCompleted.pay) {
            commissionIcon.className = 'fas fa-chevron-right right-icon';
        }
    }
}

// **تابع هندل کردن کلیک tasks**
function handleTaskCompletion() {
    window.location.href = '/earn';
}

// **تابع هندل کردن کلیک invite**
function handleInviteCheck() {
    window.location.href = '/friends';
}

// **Event listeners برای صفحه**
document.addEventListener('DOMContentLoaded', function() {
    log('📄 DOM loaded, initializing airdrop page...');
    
    // شروع شمارش معکوس
    startCountdown();
    
    // بروزرسانی اولیه UI
    updateAllTasksUI();
    
    // تشخیص Phantom
    detectPhantom();

    // Event listener برای کلیک روی wallet button
    const walletButton = document.querySelector('#connect-wallet .task-button');
    if (walletButton) {
        walletButton.addEventListener('click', function(e) {
            e.preventDefault();
            if (tasksCompleted.wallet && connectedWallet) {
                // نمایش dropdown
                const dropdown = document.querySelector('.wallet-dropdown-content');
                if (dropdown) {
                    dropdown.classList.toggle('show');
                }
            } else {
                connectWallet();
            }
        });
    }

    // Event listeners برای دکمه‌های wallet dropdown
    const changeWalletBtn = document.querySelector('.change-wallet-btn');
    if (changeWalletBtn) {
        changeWalletBtn.addEventListener('click', function() {
            connectWallet();
        });
    }

    const disconnectBtn = document.querySelector('.disconnect-btn');
    if (disconnectBtn) {
        disconnectBtn.addEventListener('click', function() {
            disconnectWallet();
        });
    }

    // بستن dropdown با کلیک خارج از آن
    document.addEventListener('click', function(event) {
        const dropdown = document.querySelector('.wallet-dropdown');
        const dropdownContent = document.querySelector('.wallet-dropdown-content');
        
        if (dropdown && dropdownContent && !dropdown.contains(event.target)) {
            dropdownContent.classList.remove('show');
        }
    });

    // Event listener برای بستن Phantom modal
    const phantomModal = document.getElementById('phantom-modal');
    if (phantomModal) {
        phantomModal.addEventListener('click', function(e) {
            if (e.target === phantomModal) {
                hidePhantomModal();
            }
        });
    }

    log('✅ Airdrop page initialized successfully');
});

// **Clean up on page unload**
window.addEventListener('beforeunload', function() {
    stopCountdown();
});
