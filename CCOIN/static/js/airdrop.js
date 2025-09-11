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
            showToast(`Connection failed: ${errorData.detail}`, "error");
        }
        
    } catch (error) {
        console.error("❌ Wallet connection failed:", error);
        
        if (error.code === 4001) {
            showToast("Connection cancelled by user", "error");
        } else if (error.message.includes('User rejected')) {
            showToast("Connection rejected by user", "error");
        } else {
            showToast("Failed to connect wallet", "error");
        }
    }
}

// **تابع جدید برای تغییر wallet**
async function changeWallet() {
    console.log("🔄 Changing wallet...");
    showToast("Changing wallet...", "info");
    
    const dropdownContent = document.getElementById('wallet-dropdown-content');
    dropdownContent?.classList.remove('show');
    
    // Disconnect current wallet first
    const provider = await getPhantomProvider();
    if (provider) {
        try {
            await provider.disconnect();
            console.log("✅ Current wallet disconnected");
        } catch (error) {
            console.log("⚠️ Error disconnecting current wallet:", error);
        }
    }
    
    // Reset UI
    updateWalletUI('', false);
    
    // Connect new wallet
    setTimeout(() => {
        connectWallet();
    }, 500);
}

// **تابع جدید برای قطع اتصال wallet**
async function disconnectWallet() {
    console.log("🔄 Disconnecting wallet...");
    showToast("Disconnecting wallet...", "info");
    
    const dropdownContent = document.getElementById('wallet-dropdown-content');
    dropdownContent?.classList.remove('show');
    
    const provider = await getPhantomProvider();
    if (provider) {
        try {
            await provider.disconnect();
            console.log("✅ Wallet disconnected successfully");
            
            // Update backend
            const result = await fetch('/airdrop/connect_wallet', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    wallet: ""
                })
            });
            
            if (result.ok) {
                console.log("✅ Wallet disconnection saved to backend");
            }
            
            updateWalletUI('', false);
            showToast("Wallet disconnected successfully", "success");
            
        } catch (error) {
            console.error("❌ Error disconnecting wallet:", error);
            showToast("Error disconnecting wallet", "error");
        }
    } else {
        // If no provider, just update UI
        updateWalletUI('', false);
        showToast("Wallet disconnected", "success");
    }
}

// **تابع بهبود یافته برای پرداخت کمیسیون**
async function payCommission() {
    console.log("🔄 Starting commission payment...");
    
    if (!tasksCompleted.wallet || !connectedWallet) {
        showToast("Please connect your wallet first", "error");
        return;
    }
    
    if (tasksCompleted.pay) {
        showToast("Commission already paid!", "info");
        return;
    }
    
    // Show modal for commission payment
    showCommissionModal();
}

// **تابع جدید برای نمایش modal کمیسیون**
function showCommissionModal() {
    // Create modal if it doesn't exist
    let modal = document.getElementById('commission-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'commission-modal';
        modal.className = 'phantom-modal';
        modal.innerHTML = `
            <div class="phantom-modal-content">
                <h3>Pay Commission</h3>
                <p>You need to pay ${COMMISSION_AMOUNT} SOL commission to complete the airdrop criteria.</p>
                <div class="phantom-modal-buttons">
                    <button onclick="processCommissionPayment()" class="phantom-modal-btn primary">
                        💰 Pay Commission
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

// **تابع جدید برای بستن modal کمیسیون**
function closeCommissionModal() {
    const modal = document.getElementById('commission-modal');
    if (modal) {
        modal.classList.remove('show');
    }
}

// **تابع جدید برای پردازش پرداخت کمیسیون**
async function processCommissionPayment() {
    console.log("🔄 Processing commission payment...");
    closeCommissionModal();
    
    const commissionButton = document.getElementById('commission-button');
    const commissionIcon = document.getElementById('commission-icon');
    
    // Show loading state
    commissionButton?.classList.add('loading');
    commissionIcon?.classList.remove('fa-chevron-right');
    commissionIcon?.classList.add('fa-spinner', 'fa-spin');
    
    showToast("Preparing transaction...", "info");
    
    const provider = await getPhantomProvider();
    if (!provider) {
        showToast("Phantom wallet not found", "error");
        resetCommissionButtonState();
        return;
    }
    
    try {
        // Create transaction
        const { Connection, PublicKey, Transaction, SystemProgram, LAMPORTS_PER_SOL } = solanaWeb3;
        const connection = new Connection(SOLANA_RPC_URL, 'confirmed');
        
        const fromPubkey = new PublicKey(connectedWallet);
        const toPubkey = new PublicKey(ADMIN_WALLET);
        const lamports = COMMISSION_AMOUNT * LAMPORTS_PER_SOL;
        
        console.log("🔄 Creating transaction...", {
            from: connectedWallet,
            to: ADMIN_WALLET,
            amount: COMMISSION_AMOUNT
        });
        
        const transaction = new Transaction().add(
            SystemProgram.transfer({
                fromPubkey,
                toPubkey,
                lamports
            })
        );
        
        const { blockhash } = await connection.getLatestBlockhash();
        transaction.recentBlockhash = blockhash;
        transaction.feePayer = fromPubkey;
        
        console.log("🔄 Requesting transaction signature...");
        showToast("Please approve transaction in Phantom", "info");
        
        const signedTransaction = await provider.signTransaction(transaction);
        
        console.log("🔄 Sending transaction...");
        showToast("Sending transaction...", "info");
        
        const signature = await connection.sendRawTransaction(signedTransaction.serialize());
        
        console.log("🔄 Confirming transaction...", signature);
        showToast("Confirming transaction...", "info");
        
        await connection.confirmTransaction(signature, 'confirmed');
        
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
            showToast("Commission paid successfully! ✅", "success");
            
        } else {
            const errorData = await result.json();
            console.error("❌ Backend confirmation failed:", errorData);
            showToast(`Confirmation failed: ${errorData.detail}`, "error");
        }
        
    } catch (error) {
        console.error("❌ Commission payment failed:", error);
        
        if (error.code === 4001) {
            showToast("Transaction cancelled by user", "error");
        } else if (error.message.includes('User rejected')) {
            showToast("Transaction rejected by user", "error");
        } else if (error.message.includes('insufficient funds')) {
            showToast("Insufficient SOL balance for transaction", "error");
        } else {
            showToast("Transaction failed: " + error.message, "error");
        }
    } finally {
        resetCommissionButtonState();
    }
}

// **تابع کمکی برای reset کردن وضعیت دکمه کمیسیون**
function resetCommissionButtonState() {
    const commissionButton = document.getElementById('commission-button');
    const commissionIcon = document.getElementById('commission-icon');
    
    commissionButton?.classList.remove('loading');
    commissionIcon?.classList.remove('fa-spinner', 'fa-spin');
    
    if (!tasksCompleted.pay) {
        commissionIcon?.classList.add('fa-chevron-right');
    }
}

// **تابع برای نمایش modal Phantom**
function showPhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.classList.add('show');
    }
}

// **تابع برای بستن modal Phantom**
function closePhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.classList.remove('show');
    }
}

// **تابع برای باز کردن اپ Phantom**
function openPhantomApp() {
    const phantomAppUrl = 'https://phantom.app/download';
    
    // Try to open Phantom app (mobile)
    const phantomDeepLink = 'phantom://';
    
    // Create a temporary link to test deep link
    const link = document.createElement('a');
    link.href = phantomDeepLink;
    link.click();
    
    // Fallback to download page after a short delay
    setTimeout(() => {
        window.open(phantomAppUrl, '_blank');
        closePhantomModal();
    }, 1000);
}

// **تابع برای بررسی وضعیت tasks**
async function handleTaskCompletion() {
    console.log("🔄 Checking task completion...");
    showToast("Checking your tasks...", "info");
    
    try {
        const response = await fetch('/earn');
        if (response.ok) {
            // Redirect to earn page
            window.location.href = '/earn';
        } else {
            showToast("Failed to load tasks page", "error");
        }
    } catch (error) {
        console.error("❌ Error checking tasks:", error);
        showToast("Error checking tasks", "error");
    }
}

// **تابع بهبود یافته برای بررسی دعوت دوستان**
async function handleInviteCheck() {
    console.log("🔄 Checking friend invitations...");
    showToast("Checking your referrals...", "info");
    
    try {
        const response = await fetch('/friends');
        const text = await response.text();
        
        // Simple check to see if user has referrals
        if (text.includes('Total Referred') || text.includes('referral')) {
            // Parse the page to check for referral count
            const parser = new DOMParser();
            const doc = parser.parseFromString(text, 'text/html');
            
            // Look for referral indicators
            const referralElements = doc.querySelectorAll('*');
            let hasReferrals = false;
            
            for (let element of referralElements) {
                if (element.textContent.includes('Total Referred: ') && 
                    !element.textContent.includes('Total Referred: 0')) {
                    hasReferrals = true;
                    break;
                }
            }
            
            if (hasReferrals) {
                tasksCompleted.invite = true;
                updateTasksUI();
                showToast("Friends invitation completed! ✅", "success");
            } else {
                showToast("No friend invitations found. Share your referral link!", "info");
                // Redirect to friends page
                setTimeout(() => {
                    window.location.href = '/friends';
                }, 1500);
            }
        } else {
            // Redirect to friends page
            window.location.href = '/friends';
        }
        
    } catch (error) {
        console.error("❌ Error checking invitations:", error);
        showToast("Error checking invitations", "error");
        
        // Fallback redirect
        setTimeout(() => {
            window.location.href = '/friends';
        }, 1500);
    }
}

// **تابع بهبود یافته برای نمایش toast**
function showToast(message, type = "info") {
    console.log(`📢 Toast: ${message} (${type})`);
    
    // Remove existing toasts
    const existingToasts = document.querySelectorAll('.toast');
    existingToasts.forEach(toast => toast.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    // Trigger animation
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    
    // Auto remove after 4 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 4000);
}

// **Event listener برای بستن dropdown با کلیک خارج**
document.addEventListener('click', function(event) {
    const dropdown = document.getElementById('wallet-dropdown');
    const dropdownContent = document.getElementById('wallet-dropdown-content');
    
    if (dropdown && dropdownContent && !dropdown.contains(event.target)) {
        dropdownContent.classList.remove('show');
    }
    
    // Close modals when clicking outside
    const phantomModal = document.getElementById('phantom-modal');
    if (phantomModal && event.target === phantomModal) {
        closePhantomModal();
    }
    
    const commissionModal = document.getElementById('commission-modal');
    if (commissionModal && event.target === commissionModal) {
        closeCommissionModal();
    }
});

console.log("✅ Airdrop JavaScript loaded successfully");
