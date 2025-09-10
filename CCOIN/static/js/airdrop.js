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

// **Event listeners برای buttons**
function setupEventListeners() {
    console.log("🔧 Setting up event listeners...");

    // Task completion button
    const taskBtn = document.getElementById('task-completion-btn');
    if (taskBtn) {
        taskBtn.addEventListener('click', handleTaskCompletion);
        console.log("✅ Task completion listener added");
    }

    // Inviting friends button
    const inviteBtn = document.getElementById('inviting-friends-btn');
    if (inviteBtn) {
        inviteBtn.addEventListener('click', handleInviteCheck);
        console.log("✅ Invite friends listener added");
    }

    // Wallet connect button
    const walletBtn = document.getElementById('wallet-connect-btn');
    if (walletBtn) {
        walletBtn.addEventListener('click', toggleWalletDropdown);
        console.log("✅ Wallet connect listener added");
    }

    // Change wallet button
    const changeBtn = document.getElementById('change-wallet-btn');
    if (changeBtn) {
        changeBtn.addEventListener('click', changeWallet);
        console.log("✅ Change wallet listener added");
    }

    // Disconnect wallet button
    const disconnectBtn = document.getElementById('disconnect-wallet-btn');
    if (disconnectBtn) {
        disconnectBtn.addEventListener('click', disconnectWallet);
        console.log("✅ Disconnect wallet listener added");
    }

    // Commission payment button
    const commissionBtn = document.getElementById('commission-button');
    if (commissionBtn) {
        commissionBtn.addEventListener('click', payCommission);
        console.log("✅ Commission payment listener added");
    }

    // Click outside to close dropdown
    document.addEventListener('click', function(event) {
        const dropdown = document.getElementById('wallet-dropdown');
        const dropdownContent = document.getElementById('wallet-dropdown-content');

        if (dropdown && dropdownContent && !dropdown.contains(event.target)) {
            dropdownContent.classList.remove('show');
        }

        // Close modal when clicking outside
        const modal = document.getElementById('phantom-modal');
        if (modal && !modal.querySelector('div').contains(event.target)) {
            closePhantomModal();
        }
    });

    console.log("✅ All event listeners setup complete");
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async function() {
    console.log("🚀 DOM loaded, initializing application...");

    // Setup event listeners first
    setupEventListeners();

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
    // تاریخ 2025 درست شده
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
        if (commissionText) commissionText.textContent = 'Commission Paid ✓';
        if (commissionButton) commissionButton.disabled = true;
        console.log("✅ Commission payment marked as complete");
    } else {
        if (commissionText) commissionText.textContent = `Pay Commission (${COMMISSION_AMOUNT} SOL)`;
    }

    console.log("✅ Tasks UI update complete");
}

// Toast notification
function showToast(message, type = 'info') {
    console.log(`📢 Toast: ${message} (${type})`);
    
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

// **نمایش modal اصلاح شده برای Phantom**
function showPhantomModal(type = 'install') {
    console.log(`🔄 Showing Phantom modal: ${type}`);
    
    const existingModal = document.getElementById('phantom-modal');
    if (existingModal) {
        existingModal.remove();
    }

    const modal = document.createElement('div');
    modal.id = 'phantom-modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
    `;

    let title, description, buttonText, buttonAction, buttonClass;

    if (type === 'install') {
        title = 'Phantom Wallet Required';
        description = 'To continue, you need to install Phantom wallet extension first.';
        buttonText = 'Install Phantom Wallet';
        buttonAction = 'installPhantom()';
        buttonClass = 'phantom-modal-btn';
    } else if (type === 'connect') {
        title = 'Connect Phantom Wallet';
        description = 'Phantom wallet detected! Click to connect your wallet.';
        buttonText = 'Open Phantom App';
        buttonAction = 'connectWalletFromModal()';
        buttonClass = 'phantom-modal-btn open-app';
    } else if (type === 'payment') {
        title = 'Pay Commission';
        description = `Click to open Phantom app and pay ${COMMISSION_AMOUNT} SOL commission.`;
        buttonText = 'Open Phantom App';
        buttonAction = 'processCommissionPayment()';
        buttonClass = 'phantom-modal-btn open-app';
    }

    modal.innerHTML = `
        <div style="
            background: #1a1a1a;
            padding: 30px;
            border-radius: 15px;
            text-align: center;
            max-width: 350px;
            width: 90%;
            border: 2px solid #333;
        ">
            <div style="font-size: 48px; margin-bottom: 20px;">👛</div>
            <h2 style="color: white; margin-bottom: 15px;">${title}</h2>
            <p style="color: #ccc; margin-bottom: 25px; line-height: 1.5;">
                ${description}
            </p>
            <button class="${buttonClass}" onclick="${buttonAction}">
                <div class="phantom-icon"></div>
                ${buttonText}
            </button>
            <button onclick="closePhantomModal()" style="
                background: transparent;
                color: #999;
                border: 1px solid #444;
                padding: 12px 20px;
                border-radius: 8px;
                cursor: pointer;
                width: 100%;
                margin-top: 10px;
            ">
                Cancel
            </button>
        </div>
    `;

    document.body.appendChild(modal);
    console.log(`✅ Phantom modal displayed: ${type}`);
}

// نصب Phantom
function installPhantom() {
    console.log("📥 Opening Phantom installation page...");
    window.open('https://phantom.app/', '_blank');
    closePhantomModal();
    
    // بررسی مجدد بعد از چند ثانیه
    setTimeout(async () => {
        phantomProvider = await getPhantomProvider();
        if (phantomProvider) {
            showToast('Phantom wallet detected! You can now connect.', 'success');
        }
    }, 3000);
}

// اتصال از modal
async function connectWalletFromModal() {
    console.log("🔗 Connecting wallet from modal...");
    closePhantomModal();
    await connectWallet();
}

// پردازش پرداخت از modal
async function processCommissionPayment() {
    console.log("💳 Processing commission payment from modal...");
    closePhantomModal();
    
    const provider = await getPhantomProvider();
    if (provider) {
        await processCommissionTransaction(provider);
    }
}

// بستن modal
function closePhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.remove();
        console.log("✅ Phantom modal closed");
    }
}

// بروزرسانی UI کیف پول
function updateWalletUI(address, connected) {
    console.log(`🔄 Updating wallet UI: ${address}, connected: ${connected}`);
    
    const walletButton = document.getElementById('wallet-button-text');
    const walletIcon = document.getElementById('wallet-icon');
    const walletIndicator = document.getElementById('wallet-status-indicator');
    const walletDropdownAddress = document.getElementById('wallet-address-dropdown');
    const connectWalletBox = document.getElementById('connect-wallet');

    if (connected && address) {
        if (walletButton) walletButton.textContent = `${address.slice(0,4)}...${address.slice(-4)}`;
        walletIcon?.classList.remove('fa-chevron-right');
        walletIcon?.classList.add('fa-check');
        walletIndicator?.classList.add('connected');
        if (walletDropdownAddress) walletDropdownAddress.textContent = address;
        connectWalletBox?.classList.add('completed');
        connectWalletBox?.querySelector('.task-button')?.classList.add('wallet-connected');
        console.log("✅ Wallet UI updated - connected");
    } else {
        if (walletButton) walletButton.textContent = 'Connect Wallet';
        walletIcon?.classList.remove('fa-check');
        walletIcon?.classList.add('fa-chevron-right');
        walletIndicator?.classList.remove('connected');
        connectWalletBox?.classList.remove('completed');
        connectWalletBox?.querySelector('.task-button')?.classList.remove('wallet-connected');
        console.log("✅ Wallet UI updated - disconnected");
    }
}

// **Toggle wallet dropdown - اصلاح شده**
async function toggleWalletDropdown() {
    console.log("👛 Toggle wallet dropdown clicked");
    
    const dropdown = document.getElementById('wallet-dropdown-content');
    
    // بررسی Phantom
    const provider = await getPhantomProvider();
    if (!provider) {
        console.log("❌ Phantom not installed, showing install modal");
        showPhantomModal('install');
        return;
    }

    // اگر wallet متصل است - نمایش/مخفی کردن منوی کشویی
    if (connectedWallet && tasksCompleted.wallet === true) {
        console.log("📋 Toggling dropdown menu for connected wallet");
        dropdown?.classList.toggle('show');
        return;
    }

    // اگر wallet متصل نیست - نمایش modal برای اتصال
    console.log("🔗 Wallet not connected, showing connect modal");
    dropdown?.classList.remove('show');
    showPhantomModal('connect');
}

// **تابع اصلاح شده برای اتصال wallet**
async function connectWallet() {
    console.log("🔗 Connect wallet clicked");

    const provider = await getPhantomProvider();
    if (!provider) {
        console.log("❌ Phantom not found for connection");
        showPhantomModal('install');
        return;
    }

    try {
        console.log("📱 Requesting wallet connection...");
        const response = await provider.connect();
        console.log('✅ Connected to wallet:', response.publicKey.toString());

        const walletAddress = response.publicKey.toString();

        // بروزرسانی backend
        console.log("💾 Updating backend with wallet address...");
        const backendResponse = await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                wallet: walletAddress
            })
        });

        const result = await backendResponse.json();
        console.log("Backend response for wallet connection:", result);

        if (result.success) {
            connectedWallet = walletAddress;
            tasksCompleted.wallet = true;
            updateWalletUI(walletAddress, true);
            updateTasksUI();
            showToast('Wallet connected successfully!', 'success');
            console.log("✅ Wallet connection completed!");
        } else {
            throw new Error(result.message || 'Failed to save wallet address');
        }

    } catch (error) {
        console.error('❌ Wallet connection failed:', error);

        let errorMessage = 'Failed to connect wallet: ' + error.message;
        if (error.code === 4001) {
            errorMessage = 'Connection cancelled by user';
        }
        showToast(errorMessage, 'error');
    }
}

// تغییر wallet
async function changeWallet() {
    console.log("🔄 Change wallet clicked");
    try {
        if (phantomProvider) {
            await phantomProvider.disconnect();
        }
        connectedWallet = '';
        tasksCompleted.wallet = false;
        updateWalletUI('', false);
        updateTasksUI();
        document.getElementById('wallet-dropdown-content')?.classList.remove('show');
        showToast('Wallet disconnected. Click to connect a new one.', 'info');
        // فوراً اتصال جدید برقرار کنیم
        setTimeout(() => showPhantomModal('connect'), 500);
    } catch (error) {
        console.error('Failed to change wallet:', error);
    }
}

// قطع اتصال wallet
async function disconnectWallet() {
    console.log("🚫 Disconnect wallet clicked");
    try {
        if (phantomProvider) {
            await phantomProvider.disconnect();
        }
        connectedWallet = '';
        tasksCompleted.wallet = false;
        updateWalletUI('', false);
        updateTasksUI();
        document.getElementById('wallet-dropdown-content')?.classList.remove('show');
        showToast('Wallet disconnected successfully!', 'success');
    } catch (error) {
        console.error('Failed to disconnect wallet:', error);
        showToast('Failed to disconnect wallet', 'error');
    }
}

// **تابع پرداخت کمیسیون اصلاح شده**
async function payCommission() {
    console.log("💰 Pay commission clicked");

    if (tasksCompleted.pay === true) {
        showToast('Commission already paid!', 'info');
        return;
    }

    // بررسی Phantom
    const provider = await getPhantomProvider();
    if (!provider) {
        console.log("❌ Phantom not detected, showing install modal");
        showPhantomModal('install');
        return;
    }

    // بررسی اتصال wallet
    if (!connectedWallet || tasksCompleted.wallet !== true) {
        showToast('Please connect your wallet first!', 'error');
        showPhantomModal('connect');
        return;
    }

    // نمایش modal پرداخت
    console.log("💳 Showing payment modal");
    showPhantomModal('payment');
}

// **تابع پردازش تراکنش**
async function processCommissionTransaction(provider) {
    if (!ADMIN_WALLET) {
        showToast('Admin wallet not configured!', 'error');
        return;
    }

    const commissionButton = document.getElementById('commission-button');
    const commissionIcon = document.getElementById('commission-icon');
    const commissionText = document.getElementById('commission-button-text');

    try {
        console.log("💳 Starting commission payment...");
        
        // Loading state
        commissionButton?.classList.add('loading');
        commissionIcon?.classList.add('fa-spinner');
        commissionIcon?.classList.remove('fa-chevron-right');
        if (commissionText) commissionText.textContent = 'Processing payment...';

        // ساخت تراکنش
        const connection = new solanaWeb3.Connection(SOLANA_RPC_URL || solanaWeb3.clusterApiUrl('mainnet-beta'));
        const transaction = new solanaWeb3.Transaction();
        const lamports = Math.floor(COMMISSION_AMOUNT * solanaWeb3.LAMPORTS_PER_SOL);

        console.log(`Creating transaction: ${COMMISSION_AMOUNT} SOL (${lamports} lamports) to ${ADMIN_WALLET}`);

        transaction.add(
            solanaWeb3.SystemProgram.transfer({
                fromPubkey: provider.publicKey,
                toPubkey: new solanaWeb3.PublicKey(ADMIN_WALLET),
                lamports: lamports
            })
        );

        const { blockhash } = await connection.getLatestBlockhash();
        transaction.recentBlockhash = blockhash;
        transaction.feePayer = provider.publicKey;

        console.log('Transaction prepared, requesting signature...');

        // امضا و ارسال
        const { signature } = await provider.signAndSendTransaction(transaction);
        
        console.log('Transaction signature received:', signature);
        if (commissionText) commissionText.textContent = 'Confirming transaction...';

        // تأیید تراکنش
        console.log("Waiting for transaction confirmation...");
        const confirmation = await connection.confirmTransaction(signature, 'confirmed');

        if (confirmation.value.err) {
            throw new Error('Transaction failed to confirm: ' + JSON.stringify(confirmation.value.err));
        }

        console.log('Transaction confirmed successfully:', signature);

        // بروزرسانی backend
        console.log("Updating backend...");
        const response = await fetch('/airdrop/confirm_commission', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
            },
            body: JSON.stringify({
                signature: signature,
                amount: COMMISSION_AMOUNT,
                recipient: ADMIN_WALLET
            })
        });

        const result = await response.json();
        console.log("Backend response:", result);

        if (result.success) {
            tasksCompleted.pay = true;
            updateTasksUI();
            showToast(`Commission paid successfully! (${COMMISSION_AMOUNT} SOL)`, 'success');
            console.log("Commission payment completed successfully!");
        } else {
            throw new Error(result.message || 'Failed to confirm payment');
        }

    } catch (error) {
        console.error('Payment failed:', error);
        
        let errorMessage = 'Payment failed: ' + error.message;
        if (error.message.includes('User rejected') || error.code === 4001) {
            errorMessage = 'Payment cancelled by user';
        } else if (error.message.includes('insufficient funds') || error.code === 1) {
            errorMessage = `Insufficient funds. You need at least ${COMMISSION_AMOUNT} SOL + network fees`;
        } else if (error.message.includes('Transaction failed') || error.message.includes('blockhash')) {
            errorMessage = 'Network error. Please try again';
        } else if (error.message.includes('Invalid') && error.message.includes('account')) {
            errorMessage = 'Invalid wallet address. Please reconnect your wallet';
        }
        
        showToast(errorMessage, 'error');

    } finally {
        // Reset button state
        commissionButton?.classList.remove('loading');
        commissionIcon?.classList.remove('fa-spinner');
        commissionIcon?.classList.add('fa-chevron-right');
        if (commissionText) commissionText.textContent = `Pay Commission (${COMMISSION_AMOUNT} SOL)`;
    }
}

// Handle task completion click
function handleTaskCompletion() {
    if (tasksCompleted.task === true) {
        showToast('Tasks already completed!', 'info');
    } else {
        showToast('Please complete the required tasks first', 'info');
        window.location.href = '/earn';
    }
}

// Handle invite check click
function handleInviteCheck() {
    if (tasksCompleted.invite === true) {
        showToast('Friends already invited!', 'info');
    } else {
        showToast('Please invite friends to earn rewards', 'info');
        window.location.href = '/friends';
    }
}

// **بررسی خودکار اتصال wallet در صورت وجود**
window.addEventListener('load', async function() {
    console.log("🔄 Window loaded, checking for existing connections...");
    
    // صبر برای تشخیص phantom
    const provider = await getPhantomProvider();
    if (provider && provider.isConnected && !connectedWallet) {
        try {
            console.log('🔗 Auto-connecting to previously connected wallet...');
            const publicKey = provider.publicKey?.toString();
            if (publicKey) {
                connectedWallet = publicKey;
                tasksCompleted.wallet = true;
                updateWalletUI(publicKey, true);
                updateTasksUI();
                console.log('✅ Auto-connected to wallet:', publicKey);
            }
        } catch (error) {
            console.log('❌ Auto-connect failed:', error);
        }
    }
});

// **اضافه کردن event listener برای تشخیص نصب Phantom**
window.addEventListener('focus', async function() {
    if (!phantomProvider) {
        console.log('🔄 Window focused, re-checking for Phantom...');
        phantomProvider = await getPhantomProvider();
        if (phantomProvider) {
            console.log('✅ Phantom detected after window focus!');
            setupPhantomListeners();
            closePhantomModal();
            showToast('Phantom wallet detected! You can now connect.', 'success');
        }
    }
});
