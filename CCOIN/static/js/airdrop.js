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

// **تابع اصلاح شده برای تشخیص Phantom با retry logic**
async function detectPhantomWallet(maxRetries = 30, retryDelay = 200) {
    console.log("Detecting Phantom wallet...");

    for (let i = 0; i < maxRetries; i++) {
        // بررسی Phantom جدید
        if (window.phantom?.solana?.isPhantom) {
            console.log("Phantom detected via window.phantom.solana");
            return window.phantom.solana;
        }

        // بررسی Phantom قدیمی (legacy)
        if (window.solana?.isPhantom) {
            console.log("Phantom detected via window.solana (legacy)");
            return window.solana;
        }

        console.log(`Attempt ${i + 1}/${maxRetries}: Phantom not yet available, waiting...`);
        await new Promise(resolve => setTimeout(resolve, retryDelay));
    }

    console.log("Phantom wallet not found after all retries");
    return null;
}

// **تابع اصلاح شده برای دریافت provider**
async function getPhantomProvider() {
    if (phantomProvider) {
        return phantomProvider;
    }

    phantomProvider = await detectPhantomWallet();
    return phantomProvider;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async function() {
    console.log("DOM loaded, initializing...");

    // تشخیص Phantom با صبر
    phantomProvider = await getPhantomProvider();
    if (phantomProvider) {
        console.log("Phantom successfully detected!");
        setupPhantomListeners();
    } else {
        console.log("Phantom not found - user needs to install it");
    }

    updateTasksUI();
    initCountdown();

    // بررسی وضعیت اتصال wallet
    if (INITIAL_WALLET_CONNECTED && INITIAL_WALLET_ADDRESS) {
        updateWalletUI(INITIAL_WALLET_ADDRESS, true);
    }
});

// **تابع جدید برای تنظیم event listeners برای Phantom**
function setupPhantomListeners() {
    if (!phantomProvider) return;

    phantomProvider.on('connect', (publicKey) => {
        console.log('Phantom connected:', publicKey.toString());
    });

    phantomProvider.on('disconnect', () => {
        console.log('Phantom disconnected');
        connectedWallet = '';
        tasksCompleted.wallet = 'false';
        updateWalletUI('', false);
        updateTasksUI();
    });

    phantomProvider.on('accountChanged', (publicKey) => {
        if (publicKey) {
            console.log('Account changed:', publicKey.toString());
            connectedWallet = publicKey.toString();
            updateWalletUI(connectedWallet, true);
        } else {
            console.log('Account disconnected');
            connectedWallet = '';
            tasksCompleted.wallet = 'false';
            updateWalletUI('', false);
            updateTasksUI();
        }
    });
}

// **شمارش معکوس با تاریخ درست**
function initCountdown() {
    // تاریخ را به سال 2025 تغییر دادیم
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
}

// بروزرسانی UI وظایف
function updateTasksUI() {
    // Tasks completion
    const taskBox = document.getElementById('task-completion');
    const taskButton = taskBox.querySelector('.task-button');
    const taskIcon = taskButton.querySelector('.right-icon');

    if (tasksCompleted.task === 'true') {
        taskBox.classList.add('completed');
        taskButton.classList.add('tasks-completed');
        taskIcon.classList.remove('fa-chevron-right');
        taskIcon.classList.add('fa-check');
    }

    // Inviting friends
    const inviteBox = document.getElementById('inviting-friends');
    const inviteButton = inviteBox.querySelector('.task-button');
    const inviteIcon = inviteButton.querySelector('.right-icon');

    if (tasksCompleted.invite === 'true') {
        inviteBox.classList.add('completed');
        inviteButton.classList.add('friends-invited');
        inviteIcon.classList.remove('fa-chevron-right');
        inviteIcon.classList.add('fa-check');
    }

    // Wallet connection
    updateWalletUI(connectedWallet, tasksCompleted.wallet === 'true');

    // Commission payment
    const commissionBox = document.getElementById('pay-commission');
    const commissionButton = commissionBox.querySelector('.task-button');
    const commissionIcon = commissionButton.querySelector('.right-icon');
    const commissionText = commissionButton.querySelector('.left-text');

    if (tasksCompleted.pay === 'true') {
        commissionBox.classList.add('completed');
        commissionButton.classList.add('commission-paid');
        commissionIcon.classList.remove('fa-chevron-right');
        commissionIcon.classList.add('fa-check');
        commissionText.textContent = 'Commission Paid ✓';
        commissionButton.disabled = true;
    } else {
        commissionText.textContent = `Pay Commission (${COMMISSION_AMOUNT} SOL)`;
    }
}

// Toast notification
function showToast(message, type = 'info') {
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

// **نمایش دکمه نصب Phantom**
function showInstallPhantomModal() {
    const existingModal = document.getElementById('phantom-install-modal');
    if (existingModal) {
        existingModal.remove();
    }

    const modal = document.createElement('div');
    modal.id = 'phantom-install-modal';
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
            <h2 style="color: white; margin-bottom: 15px;">Phantom Wallet Required</h2>
            <p style="color: #ccc; margin-bottom: 25px; line-height: 1.5;">
                To pay commission, you need to install Phantom wallet extension first.
            </p>
            <button class="install-phantom-btn" onclick="installPhantom()">
                <div class="phantom-icon"></div>
                Install Phantom Wallet
            </button>
            <button onclick="closeInstallModal()" style="
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
}

function installPhantom() {
    window.open('https://phantom.app/', '_blank');
    closeInstallModal();
}

function closeInstallModal() {
    const modal = document.getElementById('phantom-install-modal');
    if (modal) {
        modal.remove();
    }
}

// بروزرسانی UI کیف پول
function updateWalletUI(address, connected) {
    const walletButton = document.getElementById('wallet-button-text');
    const walletIcon = document.getElementById('wallet-icon');
    const walletIndicator = document.getElementById('wallet-status-indicator');
    const walletDropdownAddress = document.getElementById('wallet-address-dropdown');
    const connectWalletBox = document.getElementById('connect-wallet');

    if (connected && address) {
        walletButton.textContent = `${address.slice(0,4)}...${address.slice(-4)}`;
        walletIcon.classList.remove('fa-chevron-right');
        walletIcon.classList.add('fa-check');
        walletIndicator.classList.add('connected');
        walletDropdownAddress.textContent = address;
        connectWalletBox.classList.add('completed');
        connectWalletBox.querySelector('.task-button').classList.add('wallet-connected');
    } else {
        walletButton.textContent = 'Connect Wallet';
        walletIcon.classList.remove('fa-check');
        walletIcon.classList.add('fa-chevron-right');
        walletIndicator.classList.remove('connected');
        connectWalletBox.classList.remove('completed');
        connectWalletBox.querySelector('.task-button').classList.remove('wallet-connected');
    }
}

// **تابع اصلی پرداخت کمیسیون - اصلاح شده**
async function payCommission() {
    console.log("Pay commission clicked");

    if (tasksCompleted.pay === 'true') {
        showToast('Commission already paid!', 'info');
        return;
    }

    // **بررسی دقیق تشخیص Phantom**
    const provider = await getPhantomProvider();
    if (!provider) {
        console.log("Phantom not detected, showing install modal");
        showInstallPhantomModal();
        return;
    }

    console.log("Phantom detected, proceeding...");

    if (!connectedWallet || tasksCompleted.wallet !== 'true') {
        showToast('Please connect your wallet first!', 'error');
        toggleWalletDropdown(); // باز کردن dropdown برای اتصال
        return;
    }

    if (!ADMIN_WALLET) {
        showToast('Admin wallet not configured!', 'error');
        return;
    }

    const commissionButton = document.getElementById('commission-button');
    const commissionIcon = document.getElementById('commission-icon');
    const commissionText = document.getElementById('commission-button-text');

    try {
        console.log("Starting commission payment process...");
        // Set loading state
        commissionButton.classList.add('loading');
        commissionIcon.classList.add('fa-spinner');
        commissionIcon.classList.remove('fa-chevron-right');
        commissionText.textContent = 'Processing payment...';

        // Connect to Solana network
        const connection = new solanaWeb3.Connection(SOLANA_RPC_URL || solanaWeb3.clusterApiUrl('mainnet-beta'));

        // Create transaction
        const transaction = new solanaWeb3.Transaction();
        const lamports = Math.floor(COMMISSION_AMOUNT * solanaWeb3.LAMPORTS_PER_SOL);

        console.log(`Creating transaction: ${COMMISSION_AMOUNT} SOL (${lamports} lamports) to ${ADMIN_WALLET}`);

        // Add transfer instruction
        transaction.add(
            solanaWeb3.SystemProgram.transfer({
                fromPubkey: provider.publicKey,
                toPubkey: new solanaWeb3.PublicKey(ADMIN_WALLET),
                lamports: lamports
            })
        );

        // Get recent blockhash
        console.log("Getting latest blockhash...");
        const { blockhash } = await connection.getLatestBlockhash();
        transaction.recentBlockhash = blockhash;
        transaction.feePayer = provider.publicKey;

        console.log('Transaction prepared, requesting signature...');

        // Sign and send transaction
        const { signature } = await provider.signAndSendTransaction(transaction);

        console.log('Transaction signature received:', signature);
        commissionText.textContent = 'Confirming transaction...';

        // Confirm transaction
        console.log("Waiting for transaction confirmation...");
        const confirmation = await connection.confirmTransaction(signature, 'confirmed');

        if (confirmation.value.err) {
            throw new Error('Transaction failed to confirm: ' + JSON.stringify(confirmation.value.err));
        }

        console.log('Transaction confirmed successfully:', signature);

        // Update backend
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
            // Update state
            tasksCompleted.pay = 'true';
            updateTasksUI();
            showToast(`Commission paid successfully! (${COMMISSION_AMOUNT} SOL)`, 'success');
            console.log("Commission payment completed successfully!");
        } else {
            throw new Error(result.message || 'Failed to confirm commission payment');
        }

    } catch (error) {
        console.error('Commission payment failed:', error);
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
        commissionButton.classList.remove('loading');
        commissionIcon.classList.remove('fa-spinner');
        commissionIcon.classList.add('fa-chevron-right');
        commissionText.textContent = `Pay Commission (${COMMISSION_AMOUNT} SOL)`;
    }
}

// Toggle wallet dropdown
function toggleWalletDropdown() {
    const dropdown = document.getElementById('wallet-dropdown-content');

    if (!phantomProvider) {
        showInstallPhantomModal();
        return;
    }

    // اگر wallet متصل نیست، به جای نمایش dropdown اتصال برقرار کنیم
    if (!connectedWallet || tasksCompleted.wallet !== 'true') {
        connectWallet();
        return;
    }

    dropdown.classList.toggle('show');
}

// **تابع اصلاح شده برای اتصال wallet**
async function connectWallet() {
    console.log("Connect wallet clicked");

    const provider = await getPhantomProvider();
    if (!provider) {
        console.log("Phantom not found for connection");
        showInstallPhantomModal();
        return;
    }

    try {
        console.log("Requesting wallet connection...");
        const response = await provider.connect();
        console.log('Connected to wallet:', response.publicKey.toString());

        const walletAddress = response.publicKey.toString();

        // Update backend
        console.log("Updating backend with wallet address...");
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
            tasksCompleted.wallet = 'true';
            updateWalletUI(walletAddress, true);
            updateTasksUI();
            showToast('Wallet connected successfully!', 'success');
            console.log("Wallet connection completed!");
        } else {
            throw new Error(result.message || 'Failed to save wallet address');
        }

    } catch (error) {
        console.error('Wallet connection failed:', error);

        let errorMessage = 'Failed to connect wallet: ' + error.message;
        if (error.code === 4001) {
            errorMessage = 'Connection cancelled by user';
        }
        showToast(errorMessage, 'error');
    }
}

// Change wallet
async function changeWallet() {
    try {
        if (phantomProvider) {
            await phantomProvider.disconnect();
        }
        connectedWallet = '';
        tasksCompleted.wallet = 'false';
        updateWalletUI('', false);
        updateTasksUI();
        document.getElementById('wallet-dropdown-content').classList.remove('show');
        showToast('Wallet disconnected. Click to connect a new one.', 'info');
        // فوراً اتصال جدید برقرار کنیم
        setTimeout(() => connectWallet(), 500);
    } catch (error) {
        console.error('Failed to change wallet:', error);
    }
}

// Disconnect wallet
async function disconnectWallet() {
    try {
        if (phantomProvider) {
            await phantomProvider.disconnect();
        }
        connectedWallet = '';
        tasksCompleted.wallet = 'false';
        updateWalletUI('', false);
        updateTasksUI();
        document.getElementById('wallet-dropdown-content').classList.remove('show');
        showToast('Wallet disconnected successfully!', 'success');
    } catch (error) {
        console.error('Failed to disconnect wallet:', error);
        showToast('Failed to disconnect wallet', 'error');
    }
}

// Handle task completion click
function handleTaskCompletion() {
    if (tasksCompleted.task === 'true') {
        showToast('Tasks already completed!', 'info');
    } else {
        showToast('Please complete the required tasks first', 'info');
        window.location.href = '/earn';
    }
}

// Handle invite check click
function handleInviteCheck() {
    if (tasksCompleted.invite === 'true') {
        showToast('Friends already invited!', 'info');
    } else {
        showToast('Please invite friends to earn rewards', 'info');
        window.location.href = '/friends';
    }
}

// Close dropdown when clicking outside
document.addEventListener('click', function(event) {
    const dropdown = document.getElementById('wallet-dropdown');
    const dropdownContent = document.getElementById('wallet-dropdown-content');

    if (!dropdown.contains(event.target)) {
        dropdownContent.classList.remove('show');
    }

    // Close install modal when clicking outside
    const modal = document.getElementById('phantom-install-modal');
    if (modal && !modal.querySelector('div').contains(event.target)) {
        closeInstallModal();
    }
});

// **بررسی خودکار اتصال wallet در صورت وجود**
document.addEventListener('DOMContentLoaded', async function() {
    // صبر برای تشخیص phantom
    const provider = await getPhantomProvider();
    if (provider && provider.isConnected && !connectedWallet) {
        try {
            console.log('Auto-connecting to previously connected wallet...');
            const publicKey = provider.publicKey?.toString();
            if (publicKey) {
                connectedWallet = publicKey;
                tasksCompleted.wallet = 'true';
                updateWalletUI(publicKey, true);
                updateTasksUI();
                console.log('Auto-connected to wallet:', publicKey);
            }
        } catch (error) {
            console.log('Auto-connect failed:', error);
        }
    }
});

// **اضافه کردن event listener برای تشخیص نصب Phantom**
window.addEventListener('focus', async function() {
    if (!phantomProvider) {
        console.log('Window focused, re-checking for Phantom...');
        phantomProvider = await getPhantomProvider();
        if (phantomProvider) {
            console.log('Phantom detected after window focus!');
            setupPhantomListeners();
            closeInstallModal();
            showToast('Phantom wallet detected! You can now connect.', 'success');
        }
    }
});
