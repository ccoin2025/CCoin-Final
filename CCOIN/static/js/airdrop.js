// استفاده از متغیرهای global از HTML
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

console.log("Initial states:", {
    tasks: INITIAL_TASKS_COMPLETED,
    friends: INITIAL_INVITED_FRIENDS,
    wallet: INITIAL_WALLET_CONNECTED,
    commission: INITIAL_COMMISSION_PAID,
    address: INITIAL_WALLET_ADDRESS
});

let tasksCompleted = {
    task: INITIAL_TASKS_COMPLETED,
    invite: INITIAL_INVITED_FRIENDS,
    wallet: INITIAL_WALLET_CONNECTED,
    pay: INITIAL_COMMISSION_PAID
};

let connectedWallet = INITIAL_WALLET_ADDRESS;
let phantomProvider = null;
let phantomDetected = false;

// **تابع بهبود یافته برای تشخیص Phantom**
async function detectPhantomWallet() {
    console.log("🔍 Starting Phantom detection...");
    
    // متد 1: بررسی مستقیم window.phantom
    if (window.phantom?.solana?.isPhantom) {
        console.log("✅ Phantom detected via window.phantom.solana");
        phantomDetected = true;
        return window.phantom.solana;
    }
    
    // متد 2: بررسی legacy window.solana
    if (window.solana?.isPhantom) {
        console.log("✅ Phantom detected via window.solana (legacy)");
        phantomDetected = true;
        return window.solana;
    }
    
    // متد 3: صبر برای لود شدن extension
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

// **تابع اصلاح شده برای دریافت provider**
async function getPhantomProvider() {
    if (phantomProvider && phantomDetected) {
        return phantomProvider;
    }
    
    phantomProvider = await detectPhantomWallet();
    return phantomProvider;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async function() {
    console.log("🚀 DOM loaded, initializing application...");
    
    // تشخیص Phantom
    phantomProvider = await getPhantomProvider();
    
    if (phantomProvider) {
        console.log("✅ Phantom successfully detected!");
        setupPhantomListeners();
    } else {
        console.log("⚠️ Phantom not found - user needs to install it");
    }
    
    updateTasksUI();
    initCountdown();
    
    // بررسی وضعیت اتصال wallet
    if (INITIAL_WALLET_CONNECTED && INITIAL_WALLET_ADDRESS) {
        updateWalletUI(INITIAL_WALLET_ADDRESS, true);
    }
    
    // Close dropdown when clicking outside
    document.addEventListener('click', function(event) {
        const dropdown = document.getElementById('wallet-dropdown');
        const dropdownContent = document.getElementById('wallet-dropdown-content');
        if (dropdown && dropdownContent && !dropdown.contains(event.target)) {
            dropdownContent.classList.remove('show');
        }
        
        // Close modal when clicking outside
        const modal = document.getElementById('phantom-modal');
        if (modal && event.target === modal) {
            closePhantomModal();
        }
    });
    
    console.log("✅ Application initialization complete");
});

// **تابع جدید برای تنظیم event listeners برای Phantom**
function setupPhantomListeners() {
    if (!phantomProvider) return;
    
    console.log("🔧 Setting up Phantom event listeners...");
    
    phantomProvider.on('connect', (publicKey) => {
        console.log('👛 Phantom connected:', publicKey.toString());
    });
    
    phantomProvider.on('disconnect', () => {
        console.log('👛 Phantom disconnected');
        connectedWallet = '';
        tasksCompleted.wallet = false;
        updateWalletUI('', false);
        updateTasksUI();
    });
    
    phantomProvider.on('accountChanged', (publicKey) => {
        if (publicKey) {
            console.log('👛 Account changed:', publicKey.toString());
            connectedWallet = publicKey.toString();
            updateWalletUI(connectedWallet, true);
        } else {
            console.log('👛 Account disconnected');
            connectedWallet = '';
            tasksCompleted.wallet = false;
            updateWalletUI('', false);
            updateTasksUI();
        }
    });
    
    console.log("✅ Phantom listeners setup complete");
}

// **شمارش معکوس با تاریخ درست (2025)**
function initCountdown() {
    console.log("⏰ Initializing countdown...");
    const countdownDate = new Date("2025-12-31T23:59:59").getTime();
    
    const timer = setInterval(function() {
        const now = new Date().getTime();
        const distance = countdownDate - now;
        
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
    
    console.log("✅ Countdown initialized");
}

// بروزرسانی UI وظایف
function updateTasksUI() {
    console.log("🔄 Updating tasks UI...", tasksCompleted);
    
    // Tasks completion
    const taskBox = document.getElementById('task-completion');
    const taskButton = taskBox?.querySelector('.task-button');
    const taskIcon = taskButton?.querySelector('.right-icon');
    
    if (tasksCompleted.task === true) {
        taskBox?.classList.add('completed');
        taskButton?.classList.add('tasks-completed');
        taskIcon?.classList.remove('fa-chevron-right');
        taskIcon?.classList.add('fa-check');
        console.log("✅ Tasks completion marked as complete");
    }
    
    // Inviting friends
    const inviteBox = document.getElementById('inviting-friends');
    const inviteButton = inviteBox?.querySelector('.task-button');
    const inviteIcon = inviteButton?.querySelector('.right-icon');
    
    if (tasksCompleted.invite === true) {
        inviteBox?.classList.add('completed');
        inviteButton?.classList.add('friends-invited');
        inviteIcon?.classList.remove('fa-chevron-right');
        inviteIcon?.classList.add('fa-check');
        console.log("✅ Friends invitation marked as complete");
    }
    
    // Wallet connection
    updateWalletUI(connectedWallet, tasksCompleted.wallet === true);
    
    // Commission payment
    const commissionBox = document.getElementById('pay-commission');
    const commissionButton = commissionBox?.querySelector('.task-button');
    const commissionIcon = commissionButton?.querySelector('.right-icon');
    const commissionText = commissionButton?.querySelector('.left-text');
    
    if (tasksCompleted.pay === true) {
        commissionBox?.classList.add('completed');
        commissionButton?.classList.add('commission-paid');
        commissionIcon?.classList.remove('fa-chevron-right');
        commissionIcon?.classList.add('fa-check');
        commissionText.textContent = "Commission Paid";
        console.log("✅ Commission payment marked as complete");
    }
    
    console.log("✅ Tasks UI update complete");
}

// **تابع بهبود یافته برای بروزرسانی UI wallet**
function updateWalletUI(walletAddress, isConnected) {
    console.log("🔄 Updating wallet UI:", { walletAddress, isConnected });
    
    const walletBox = document.getElementById('connect-wallet');
    const walletButton = walletBox?.querySelector('.task-button');
    const walletButtonText = document.getElementById('wallet-button-text');
    const walletIcon = document.getElementById('wallet-icon');
    const walletIndicator = document.getElementById('wallet-status-indicator');
    const walletDropdownContent = document.getElementById('wallet-dropdown-content');
    const walletAddressDropdown = document.getElementById('wallet-address-dropdown');
    
    if (isConnected && walletAddress) {
        // Connected state
        walletBox?.classList.add('completed');
        walletButton?.classList.add('wallet-connected');
        walletButtonText.textContent = "Wallet Connected";
        walletIcon?.classList.remove('fa-chevron-right');
        walletIcon?.classList.add('fa-check');
        walletIndicator?.classList.add('connected');
        walletAddressDropdown.textContent = walletAddress;
        
        tasksCompleted.wallet = true;
        connectedWallet = walletAddress;
        console.log("✅ Wallet UI updated to connected state");
    } else {
        // Disconnected state
        walletBox?.classList.remove('completed');
        walletButton?.classList.remove('wallet-connected');
        walletButtonText.textContent = "Connect Wallet";
        walletIcon?.classList.remove('fa-check');
        walletIcon?.classList.add('fa-chevron-right');
        walletIndicator?.classList.remove('connected');
        walletAddressDropdown.textContent = "";
        walletDropdownContent?.classList.remove('show');
        
        tasksCompleted.wallet = false;
        connectedWallet = '';
        console.log("✅ Wallet UI updated to disconnected state");
    }
}

// **تابع toggle برای منوی کشویی wallet**
function toggleWalletDropdown() {
    console.log("🔄 Toggling wallet dropdown...");
    
    if (!tasksCompleted.wallet) {
        // اگر wallet متصل نیست، سعی کن وصل کن
        connectWallet();
        return;
    }
    
    const dropdownContent = document.getElementById('wallet-dropdown-content');
    if (dropdownContent) {
        dropdownContent.classList.toggle('show');
        console.log("✅ Wallet dropdown toggled");
    }
}

// **تابع اصلاح شده برای اتصال wallet**
async function connectWallet() {
    console.log("🔄 Starting wallet connection...");
    showToast("Connecting to Phantom wallet...", "info");
    
    const provider = await getPhantomProvider();
    
    if (!provider) {
        console.log("⚠️ Phantom not detected, showing modal");
        showPhantomModal();
        return;
    }
    
    try {
        console.log("🔄 Attempting to connect to Phantom...");
        const response = await provider.connect();
        const walletAddress = response.publicKey.toString();
        
        console.log("✅ Phantom connected:", walletAddress);
        
        // Send to backend
        const result = await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                wallet: walletAddress
            })
        });
        
        if (result.ok) {
            const data = await result.json();
            console.log("✅ Wallet saved to backend:", data);
            
            updateWalletUI(walletAddress, true);
            showToast("Wallet connected successfully!", "success");
        } else {
            const errorData = await result.json();
            console.error("❌ Backend error:", errorData);
            showToast("Error saving wallet: " + errorData.detail, "error");
        }
        
    } catch (error) {
        console.error("❌ Wallet connection failed:", error);
        showToast("Failed to connect wallet: " + error.message, "error");
    }
}

// **تابع جدید برای تغییر wallet**
async function changeWallet() {
    console.log("🔄 Changing wallet...");
    showToast("Connecting to new wallet...", "info");
    
    // Hide dropdown first
    const dropdownContent = document.getElementById('wallet-dropdown-content');
    dropdownContent?.classList.remove('show');
    
    const provider = await getPhantomProvider();
    
    if (!provider) {
        showPhantomModal();
        return;
    }
    
    try {
        // Disconnect first
        await provider.disconnect();
        
        // Then reconnect
        const response = await provider.connect();
        const walletAddress = response.publicKey.toString();
        
        console.log("✅ New wallet connected:", walletAddress);
        
        // Send to backend
        const result = await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                wallet: walletAddress
            })
        });
        
        if (result.ok) {
            const data = await result.json();
            console.log("✅ New wallet saved to backend:", data);
            
            updateWalletUI(walletAddress, true);
            showToast("Wallet changed successfully!", "success");
        } else {
            const errorData = await result.json();
            console.error("❌ Backend error:", errorData);
            showToast("Error changing wallet: " + errorData.detail, "error");
        }
        
    } catch (error) {
        console.error("❌ Wallet change failed:", error);
        showToast("Failed to change wallet: " + error.message, "error");
    }
}

// **تابع جدید برای قطع اتصال wallet**
async function disconnectWallet() {
    console.log("🔄 Disconnecting wallet...");
    showToast("Disconnecting wallet...", "info");
    
    // Hide dropdown first
    const dropdownContent = document.getElementById('wallet-dropdown-content');
    dropdownContent?.classList.remove('show');
    
    const provider = await getPhantomProvider();
    
    if (provider) {
        try {
            await provider.disconnect();
            console.log("✅ Phantom disconnected");
        } catch (error) {
            console.error("❌ Error disconnecting Phantom:", error);
        }
    }
    
    // Update UI and state
    updateWalletUI('', false);
    showToast("Wallet disconnected successfully!", "success");
    
    // Clear from backend (optional - you might want to keep the wallet saved)
    try {
        await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                wallet: ""
            })
        });
    } catch (error) {
        console.log("Note: Could not clear wallet from backend");
    }
}

// **تابع برای پرداخت کمیسیون**
async function payCommission() {
    console.log("🔄 Starting commission payment...");
    
    if (!connectedWallet) {
        showToast("Please connect your wallet first!", "error");
        return;
    }
    
    if (tasksCompleted.pay) {
        showToast("Commission already paid!", "info");
        return;
    }
    
    showCommissionModal();
}

// **تابع برای نمایش مودال پرداخت کمیسیون**
function showCommissionModal() {
    showToast("Opening Phantom for commission payment...", "info");
    
    // Create commission modal HTML if not exists
    let modal = document.getElementById('commission-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'commission-modal';
        modal.className = 'phantom-modal';
        modal.innerHTML = `
            <div class="phantom-modal-content">
                <h3>Pay Commission</h3>
                <p>You need to pay ${COMMISSION_AMOUNT} SOL as commission fee. Click below to proceed with payment via Phantom.</p>
                <div class="phantom-modal-buttons">
                    <button onclick="processCommissionPayment()" class="phantom-modal-btn primary">
                        💳 Pay Commission
                    </button>
                    <button onclick="closeCommissionModal()" class="phantom-modal-btn secondary">
                        Cancel
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }
    
    modal.classList.add('show');
}

// **تابع برای بستن مودال کمیسیون**
function closeCommissionModal() {
    const modal = document.getElementById('commission-modal');
    if (modal) {
        modal.classList.remove('show');
    }
}

// **تابع برای پردازش پرداخت کمیسیون**
async function processCommissionPayment() {
    console.log("🔄 Processing commission payment...");
    
    const provider = await getPhantomProvider();
    
    if (!provider) {
        showToast("Phantom wallet not found!", "error");
        return;
    }
    
    if (!provider.isConnected) {
        showToast("Please connect your wallet first!", "error");
        return;
    }
    
    try {
        // Set loading state
        const commissionButton = document.getElementById('commission-button');
        const commissionIcon = document.getElementById('commission-icon');
        commissionButton?.classList.add('loading');
        commissionIcon?.classList.remove('fa-chevron-right');
        commissionIcon?.classList.add('fa-spinner', 'fa-spin');
        
        showToast("Processing payment...", "info");
        
        // Create transaction
        const connection = new solanaWeb3.Connection(SOLANA_RPC_URL);
        const transaction = new solanaWeb3.Transaction();
        
        // Add transfer instruction
        const lamports = COMMISSION_AMOUNT * solanaWeb3.LAMPORTS_PER_SOL;
        
        transaction.add(
            solanaWeb3.SystemProgram.transfer({
                fromPubkey: provider.publicKey,
                toPubkey: new solanaWeb3.PublicKey(ADMIN_WALLET),
                lamports: lamports
            })
        );
        
        // Get recent blockhash
        const { blockhash } = await connection.getLatestBlockhash();
        transaction.recentBlockhash = blockhash;
        transaction.feePayer = provider.publicKey;
        
        // Sign and send transaction
        const signedTransaction = await provider.signTransaction(transaction);
        const signature = await connection.sendRawTransaction(signedTransaction.serialize());
        
        console.log("✅ Transaction sent:", signature);
        showToast("Payment sent! Confirming...", "info");
        
        // Wait for confirmation
        await connection.confirmTransaction(signature);
        
        console.log("✅ Transaction confirmed:", signature);
        
        // Send confirmation to backend
        const result = await fetch('/airdrop/confirm_commission', {
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
        
        if (result.ok) {
            const data = await result.json();
            console.log("✅ Commission confirmed by backend:", data);
            
            tasksCompleted.pay = true;
            updateTasksUI();
            showToast("Commission paid successfully!", "success");
            closeCommissionModal();
        } else {
            const errorData = await result.json();
            console.error("❌ Backend confirmation failed:", errorData);
            showToast("Payment sent but confirmation failed: " + errorData.detail, "error");
        }
        
    } catch (error) {
        console.error("❌ Commission payment failed:", error);
        showToast("Payment failed: " + error.message, "error");
    } finally {
        // Remove loading state
        const commissionButton = document.getElementById('commission-button');
        const commissionIcon = document.getElementById('commission-icon');
        commissionButton?.classList.remove('loading');
        commissionIcon?.classList.remove('fa-spinner', 'fa-spin');
        commissionIcon?.classList.add('fa-chevron-right');
    }
}

// **تابع برای بررسی وظایف**
async function handleTaskCompletion() {
    console.log("🔄 Checking task completion...");
    
    if (tasksCompleted.task) {
        showToast("Tasks already completed!", "info");
        return;
    }
    
    // Redirect to tasks page
    window.location.href = '/earn';
}

// **تابع برای بررسی دعوت دوستان**
async function handleInviteCheck() {
    console.log("🔄 Checking invite status...");
    
    try {
        const response = await fetch('/friends', {
            method: 'GET',
        });
        
        if (response.ok) {
            // Redirect to friends page
            window.location.href = '/friends';
        } else {
            showToast("Error checking invite status", "error");
        }
    } catch (error) {
        console.error("❌ Error checking invites:", error);
        showToast("Error checking invite status", "error");
    }
}

// **تابع برای نمایش مودال Phantom**
function showPhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.classList.add('show');
    }
}

// **تابع برای بستن مودال Phantom**
function closePhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.classList.remove('show');
    }
}

// **تابع برای باز کردن اپ Phantom**
function openPhantomApp() {
    // Try to open Phantom app
    const phantomUrl = "https://phantom.app/ul/browse/https://ccoin-final.onrender.com/airdrop?ref=phantom";
    
    // For mobile, try to open the app directly
    if (/Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {
        window.location.href = "phantom://browse/" + encodeURIComponent(window.location.href);
        
        // Fallback to app store if phantom app is not installed
        setTimeout(() => {
            window.open("https://phantom.app/download", "_blank");
        }, 2000);
    } else {
        // For desktop, just show install message
        showToast("Please install Phantom extension for your browser", "info");
        window.open("https://phantom.app/download", "_blank");
    }
    
    closePhantomModal();
}

// **تابع برای نمایش Toast notifications**
function showToast(message, type = 'info') {
    console.log(`📢 Toast: ${message} (${type})`);
    
    // Remove existing toasts
    const existingToasts = document.querySelectorAll('.toast');
    existingToasts.forEach(toast => toast.remove());
    
    // Create new toast
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    // Show toast
    setTimeout(() => toast.classList.add('show'), 100);
    
    // Hide and remove toast
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// **بررسی وضعیت اولیه tasks و بروزرسانی UI**
function checkInitialStates() {
    // بررسی دوباره از backend
    fetch('/airdrop/commission_status')
        .then(response => response.json())
        .then(data => {
            if (data.commission_paid !== tasksCompleted.pay) {
                tasksCompleted.pay = data.commission_paid;
                updateTasksUI();
            }
            
            if (data.wallet_connected !== tasksCompleted.wallet) {
                tasksCompleted.wallet = data.wallet_connected;
                if (data.wallet_address) {
                    connectedWallet = data.wallet_address;
                }
                updateTasksUI();
            }
        })
        .catch(error => {
            console.log("Could not fetch commission status:", error);
        });
}

// Check initial states after a short delay
setTimeout(checkInitialStates, 1000);
