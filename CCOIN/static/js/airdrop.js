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

// Fix: Ensure bs58 is properly loaded
function ensureBS58() {
    if (typeof bs58 === 'undefined') {
        if (typeof window.bs58 !== 'undefined') {
            window.bs58 = window.bs58;
            return true;
        }
        console.error('BS58 library not loaded');
        return false;
    }
    return true;
}

// **Fixed: Countdown Timer**
function updateCountdown() {
    // Set the target date (30 days from now for example)
    const targetDate = new Date();
    targetDate.setDate(targetDate.getDate() + 30);
    
    const now = new Date().getTime();
    const distance = targetDate.getTime() - now;
    
    if (distance > 0) {
        const days = Math.floor(distance / (1000 * 60 * 60 * 24));
        const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);
        
        document.getElementById('days').textContent = days.toString().padStart(2, '0');
        document.getElementById('hours').textContent = hours.toString().padStart(2, '0');
        document.getElementById('minutes').textContent = minutes.toString().padStart(2, '0');
        document.getElementById('seconds').textContent = seconds.toString().padStart(2, '0');
    } else {
        document.getElementById('days').textContent = '00';
        document.getElementById('hours').textContent = '00';
        document.getElementById('minutes').textContent = '00';
        document.getElementById('seconds').textContent = '00';
    }
}

// Enhanced Phantom detection
async function detectPhantomWallet() {
    console.log("🔍 Starting Phantom detection...");
    
    if (window.phantom?.solana?.isPhantom) {
        console.log("✅ Phantom detected via window.phantom.solana");
        phantomDetected = true;
        return window.phantom.solana;
    }
    
    if (window.solana?.isPhantom) {
        console.log("✅ Phantom detected via window.solana (legacy)");
        phantomDetected = true;
        return window.solana;
    }
    
    console.log("⏳ Waiting for Phantom extension to load...");
    for (let i = 0; i < 50; i++) {
        await new Promise(resolve => setTimeout(resolve, 100));
        if (window.phantom?.solana?.isPhantom) {
            console.log("✅ Phantom detected after waiting");
            phantomDetected = true;
            return window.phantom.solana;
        }
        if (window.solana?.isPhantom) {
            console.log("✅ Phantom detected (legacy) after waiting");
            phantomDetected = true;
            return window.solana;
        }
    }
    
    console.log("❌ Phantom wallet not found");
    phantomDetected = false;
    return null;
}

async function getPhantomProvider() {
    if (phantomProvider && phantomDetected) {
        return phantomProvider;
    }
    phantomProvider = await detectPhantomWallet();
    return phantomProvider;
}

// **اصلاح شده: تشخیص محیط Telegram**
function isTelegramEnvironment() {
    return window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData;
}

// **اصلاح شده: باز کردن لینک در مرورگر خارجی**
function openExternalLink(url) {
    console.log("🔗 Opening external link:", url);
    
    if (isTelegramEnvironment()) {
        console.log("📱 Telegram environment detected, using Telegram API");
        try {
            // روش اول: استفاده از Telegram WebApp API
            if (window.Telegram.WebApp.openTelegramLink) {
                window.Telegram.WebApp.openTelegramLink(url);
                return;
            }
            
            // روش دوم: استفاده از openLink
            if (window.Telegram.WebApp.openLink) {
                window.Telegram.WebApp.openLink(url);
                return;
            }
            
            // روش سوم: fallback به window.open
            console.log("🔄 Falling back to window.open");
            window.open(url, '_blank');
            
        } catch (error) {
            console.error("Error opening Telegram link:", error);
            // آخرین fallback
            window.location.href = url;
        }
    } else {
        console.log("🌐 Standard browser environment");
        // برای دسکتاپ یا مرورگر عادی
        window.open(url, '_blank');
    }
}

// **اصلاح شده: هدایت مستقیم بدون مودال واسطه**
function redirectToPhantomApp(deeplink) {
    console.log("🦄 Redirecting directly to Phantom:", deeplink);
    
    // هدایت مستقیم بدون هیچ تاخیر یا مودال
    openExternalLink(deeplink);
    
    // نمایش پیام موفقیت
    showToast("Redirecting to Phantom wallet...", "info");
}

// Wallet connection handler
async function handleWalletConnection() {
    if (!tasksCompleted.wallet) {
        await connectWallet();
    } else {
        toggleWalletDropdown();
    }
}

// **اصلاح شده: اتصال مستقیم کیف پول**
async function connectWallet() {
    console.log("🔗 Starting wallet connection...");
    
    const provider = await getPhantomProvider();
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|OperaMini/i.test(navigator.userAgent);
    
    if (isMobile || isTelegramEnvironment()) {
        console.log("📱 Mobile/Telegram environment - using deeplink");
        try {
            const params = new URLSearchParams({
                cluster: "devnet",
                app_url: window.location.origin,
                redirect_link: `${window.location.origin}/airdrop?phantom_action=connect`
            });
            
            const connectUrl = `https://phantom.app/ul/v1/connect?${params.toString()}`;
            
            // **تغییر اصلی: هدایت مستقیم بدون مودال**
            redirectToPhantomApp(connectUrl);
            
        } catch (error) {
            console.error("Error creating deeplink:", error);
            showToast("Error creating connection link", "error");
        }
    } else {
        // برای دسکتاپ
        if (provider) {
            await connectWalletDirect();
        } else {
            showPhantomModal();
        }
    }
}

async function connectWalletDirect() {
    try {
        const response = await phantomProvider.connect();
        connectedWallet = response.publicKey.toString();
        
        const saveResponse = await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                wallet: connectedWallet
            })
        });
        
        if (saveResponse.ok) {
            tasksCompleted.wallet = true;
            updateWalletUI();
            updateTasksUI();
            showToast("Wallet connected successfully!", "success");
        } else {
            throw new Error("Failed to save wallet connection");
        }
    } catch (error) {
        console.error("Connection failed:", error);
        showToast("Wallet connection failed", "error");
    }
}

// **اصلاح شده: پرداخت کمیسیون**
async function payCommission() {
    if (!connectedWallet) {
        showToast("Please connect wallet first", "error");
        return;
    }
    
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|OperaMini/i.test(navigator.userAgent);
    
    if (isMobile || isTelegramEnvironment()) {
        console.log("📱 Mobile/Telegram environment - opening commission page");
        try {
            // هدایت به صفحه commission browser
            const commissionUrl = `/airdrop/commission_browser_pay?telegram_id=${USER_ID}`;
            openExternalLink(commissionUrl);
            
        } catch (error) {
            console.error("Error opening commission page:", error);
            showToast("Error opening commission page", "error");
        }
    } else {
        if (phantomProvider && connectedWallet) {
            await sendCommissionTransaction();
        } else {
            showToast("Please connect wallet first", "error");
        }
    }
}

async function sendCommissionTransaction() {
    try {
        // Check if bs58 is available
        if (!ensureBS58()) {
            throw new Error('BS58 library not available');
        }

        const transaction = await createCommissionTransaction();
        const signed = await phantomProvider.signTransaction(transaction);
        
        const response = await fetch('/airdrop/pay_commission', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                transaction: signed.serialize()
            })
        });
        
        if (response.ok) {
            tasksCompleted.pay = true;
            updateTasksUI();
            showToast("Commission paid successfully!", "success");
        } else {
            throw new Error("Failed to process commission");
        }
    } catch (error) {
        console.error("Commission payment failed:", error);
        showToast("Commission payment failed", "error");
    }
}

async function createCommissionTransaction() {
    const connection = new solanaWeb3.Connection(SOLANA_RPC_URL);
    const fromPubkey = new solanaWeb3.PublicKey(connectedWallet);
    const toPubkey = new solanaWeb3.PublicKey(ADMIN_WALLET);
    
    const transaction = new solanaWeb3.Transaction().add(
        solanaWeb3.SystemProgram.transfer({
            fromPubkey,
            toPubkey,
            lamports: COMMISSION_AMOUNT * solanaWeb3.LAMPORTS_PER_SOL
        })
    );
    
    const { blockhash } = await connection.getRecentBlockhash();
    transaction.recentBlockhash = blockhash;
    transaction.feePayer = fromPubkey;
    
    return transaction;
}

// **باقی توابع بدون تغییر**
function toggleWalletDropdown() {
    const dropdown = document.querySelector('.wallet-dropdown-content');
    if (dropdown) {
        dropdown.classList.toggle('show');
    }
}

function updateWalletUI() {
    const button = document.querySelector('#connect-wallet .task-button');
    const leftText = button.querySelector('.left-text');
    const rightIcon = button.querySelector('.right-icon');
    const statusIndicator = button.querySelector('.wallet-status-indicator');
    
    if (tasksCompleted.wallet) {
        leftText.textContent = 'Wallet Connected';
        rightIcon.className = 'fas fa-chevron-down right-icon';
        button.classList.add('wallet-connected');
        if (statusIndicator) {
            statusIndicator.classList.add('connected');
        }
        
        // Update dropdown content
        updateWalletDropdown();
    }
}

function updateWalletDropdown() {
    const dropdown = document.querySelector('.wallet-dropdown-content');
    if (dropdown && connectedWallet) {
        dropdown.innerHTML = `
            <div class="wallet-info-dropdown">
                <div class="wallet-address-dropdown">${connectedWallet}</div>
                <div class="wallet-actions-dropdown">
                    <button class="wallet-action-btn change-btn" onclick="changeWallet()">Change</button>
                    <button class="wallet-action-btn disconnect-btn" onclick="disconnectWallet()">Disconnect</button>
                </div>
            </div>
        `;
    }
}

function updateTasksUI() {
    // Update task completion
    const taskBox = document.querySelector('#task-completion');
    if (tasksCompleted.task) {
        taskBox.classList.add('completed');
        taskBox.querySelector('.right-icon').className = 'fas fa-check right-icon';
    }
    
    // Update invite friends
    const inviteBox = document.querySelector('#inviting-friends');
    if (tasksCompleted.invite) {
        inviteBox.classList.add('completed');
        inviteBox.querySelector('.right-icon').className = 'fas fa-check right-icon';
    }
    
    // Update commission payment
    const payBox = document.querySelector('#pay-commission');
    if (tasksCompleted.pay) {
        payBox.classList.add('completed');
        payBox.querySelector('.right-icon').className = 'fas fa-check right-icon';
    }
    
    // Update claim button
    updateClaimButton();
}

function updateClaimButton() {
    const claimButton = document.getElementById('claimButton');
    const allCompleted = tasksCompleted.task && tasksCompleted.invite && 
                        tasksCompleted.wallet && tasksCompleted.pay;
    
    if (allCompleted) {
        claimButton.disabled = false;
        claimButton.textContent = 'Claim Airdrop';
        claimButton.style.background = 'linear-gradient(135deg, #28a745, #20c997)';
    } else {
        claimButton.disabled = true;
        claimButton.textContent = 'Complete all tasks first';
        claimButton.style.background = '#6c757d';
    }
}

// Task handlers
async function handleTaskCompletion() {
    if (!tasksCompleted.task) {
        window.location.href = '/earn';
    }
}

async function handleInviteCheck() {
    if (!tasksCompleted.invite) {
        window.location.href = '/friends';
    }
}

// Modals
function showPhantomModal() {
    document.getElementById('phantomModal').classList.add('show');
}

function closePhantomModal() {
    document.getElementById('phantomModal').classList.remove('show');
}

function showCommissionModal() {
    document.getElementById('commissionModal').classList.add('show');
}

function closeCommissionModal() {
    document.getElementById('commissionModal').classList.remove('show');
}

function openCommissionPage() {
    const commissionUrl = `/airdrop/commission_browser_pay?telegram_id=${USER_ID}`;
    openExternalLink(commissionUrl);
    closeCommissionModal();
}

// Wallet management
async function changeWallet() {
    if (phantomProvider) {
        try {
            await phantomProvider.disconnect();
            connectedWallet = null;
            tasksCompleted.wallet = false;
            updateWalletUI();
            updateTasksUI();
            showToast("Wallet disconnected", "info");
            
            // Reconnect
            setTimeout(() => {
                connectWallet();
            }, 1000);
        } catch (error) {
            console.error("Error changing wallet:", error);
            showToast("Error changing wallet", "error");
        }
    }
    toggleWalletDropdown();
}

async function disconnectWallet() {
    if (phantomProvider) {
        try {
            await phantomProvider.disconnect();
            connectedWallet = null;
            tasksCompleted.wallet = false;
            
            // Update UI
            const button = document.querySelector('#connect-wallet .task-button');
            const leftText = button.querySelector('.left-text');
            const rightIcon = button.querySelector('.right-icon');
            const statusIndicator = button.querySelector('.wallet-status-indicator');
            
            leftText.textContent = 'Connect Wallet';
            rightIcon.className = 'fas fa-chevron-right right-icon';
            button.classList.remove('wallet-connected');
            if (statusIndicator) {
                statusIndicator.classList.remove('connected');
            }
            
            updateTasksUI();
            showToast("Wallet disconnected successfully", "success");
        } catch (error) {
            console.error("Error disconnecting wallet:", error);
            showToast("Error disconnecting wallet", "error");
        }
    }
    toggleWalletDropdown();
}

// Toast notifications
function showToast(message, type = 'info') {
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
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}

// Claim airdrop
async function claimAirdrop() {
    const allCompleted = tasksCompleted.task && tasksCompleted.invite && 
                        tasksCompleted.wallet && tasksCompleted.pay;
    
    if (!allCompleted) {
        showToast("Please complete all tasks first", "error");
        return;
    }
    
    try {
        const response = await fetch('/airdrop/claim', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                telegram_id: USER_ID
            })
        });
        
        if (response.ok) {
            showToast("Airdrop claimed successfully!", "success");
            // Redirect or update UI as needed
        } else {
            throw new Error("Failed to claim airdrop");
        }
    } catch (error) {
        console.error("Claim failed:", error);
        showToast("Failed to claim airdrop", "error");
    }
}

// Handle URL parameters for wallet connection callback
function handleURLParams() {
    const urlParams = new URLSearchParams(window.location.search);
    const phantomAction = urlParams.get('phantom_action');
    const publicKey = urlParams.get('public_key');
    
    if (phantomAction === 'connect' && publicKey) {
        connectedWallet = publicKey;
        tasksCompleted.wallet = true;
        updateWalletUI();
        updateTasksUI();
        showToast("Wallet connected successfully!", "success");
        
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    
    if (phantomAction === 'sign') {
        const signature = urlParams.get('signature');
        if (signature) {
            tasksCompleted.pay = true;
            updateTasksUI();
            showToast("Commission paid successfully!", "success");
        }
        
        // Clean URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    if (window.Telegram?.WebApp) {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
    }
    
    // Initialize UI based on current state
    updateWalletUI();
    updateTasksUI();
    
    // Handle URL parameters
    handleURLParams();
    
    // Start countdown timer
    updateCountdown();
    setInterval(updateCountdown, 1000);
    
    // Close dropdown when clicking outside
    document.addEventListener('click', (event) => {
        const dropdown = document.querySelector('.wallet-dropdown');
        if (dropdown && !dropdown.contains(event.target)) {
            const dropdownContent = document.querySelector('.wallet-dropdown-content');
            if (dropdownContent) {
                dropdownContent.classList.remove('show');
            }
        }
    });
});
