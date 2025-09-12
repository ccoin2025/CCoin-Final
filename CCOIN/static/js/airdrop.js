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

// Show intermediate modal with user data
function showPhantomIntermediateModal(type, data) {
    const modal = document.getElementById('phantom-intermediate-modal');
    const title = document.getElementById('intermediate-modal-title');
    const content = document.getElementById('intermediate-modal-content');
    const actionBtn = document.getElementById('intermediate-action-btn');
    const closeBtn = document.getElementById('intermediate-close-btn');
    
    if (!modal || !title || !content || !actionBtn) {
        console.error("Modal elements not found");
        return;
    }
    
    if (type === 'connect') {
        title.textContent = 'Connect Wallet';
        content.innerHTML = `
            <p>Your user data will be sent to external browser:</p>
            <div class="data-display">
                <p><strong>User ID:</strong> ${USER_ID || 'Guest'}</p>
                <p><strong>Domain:</strong> ${window.location.host}</p>
                <p><strong>Network:</strong> Solana Devnet</p>
                <p><strong>Action:</strong> Connect Phantom Wallet</p>
            </div>
            <p>Click Connect Wallet to proceed:</p>
        `;
        actionBtn.textContent = 'Connect Wallet';
        actionBtn.onclick = () => redirectToExternalBrowser(data.deeplink);
    } else if (type === 'transaction') {
        title.textContent = 'Send Transaction';
        content.innerHTML = `
            <p>Your transaction data will be sent to external browser:</p>
            <div class="data-display">
                <p><strong>User ID:</strong> ${USER_ID || 'Guest'}</p>
                <p><strong>Amount:</strong> ${COMMISSION_AMOUNT} SOL</p>
                <p><strong>Recipient:</strong> ${ADMIN_WALLET}</p>
                <p><strong>Network:</strong> Solana Devnet</p>
            </div>
            <p>Click Connect Wallet to proceed:</p>
        `;
        actionBtn.textContent = 'Connect Wallet';
        actionBtn.onclick = () => redirectToExternalBrowser(data.deeplink);
    }
    
    closeBtn.onclick = closeIntermediateModal;
    
    modal.style.display = 'flex';
    modal.classList.add('show');
}

// Close intermediate modal
function closeIntermediateModal() {
    const modal = document.getElementById('phantom-intermediate-modal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    }
}

// Redirect to external browser with Open Phantom App button
function redirectToExternalBrowser(deeplink) {
    closeIntermediateModal();
    
    // Create a new page content for external browser
    const newWindow = window.open('', '_blank');
    if (newWindow) {
        newWindow.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>Connect to Phantom</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {
                        font-family: 'Arial', sans-serif;
                        background: linear-gradient(135deg, #1a1a1a, #2d2d2d);
                        margin: 0;
                        padding: 20px;
                        min-height: 100vh;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        color: white;
                    }
                    .container {
                        background: #1a1a1a;
                        padding: 40px;
                        border-radius: 20px;
                        text-align: center;
                        max-width: 500px;
                        width: 100%;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                        border: 2px solid #333;
                    }
                    h1 {
                        color: #AB9FF2;
                        margin-bottom: 20px;
                        font-size: 28px;
                    }
                    p {
                        color: #ccc;
                        line-height: 1.6;
                        margin-bottom: 30px;
                        font-size: 16px;
                    }
                    .phantom-btn {
                        background: linear-gradient(135deg, #AB9FF2, #7B68EE);
                        color: white;
                        border: none;
                        padding: 15px 30px;
                        border-radius: 10px;
                        font-size: 18px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: all 0.3s ease;
                        text-decoration: none;
                        display: inline-block;
                        margin: 10px;
                    }
                    .phantom-btn:hover {
                        background: linear-gradient(135deg, #9A8DF0, #6A57DC);
                        transform: translateY(-2px);
                    }
                    .data-info {
                        background: #2d2d2d;
                        padding: 20px;
                        border-radius: 10px;
                        margin: 20px 0;
                        border: 1px solid #444;
                        text-align: left;
                    }
                    .data-info p {
                        margin: 8px 0;
                        font-size: 14px;
                    }
                    .data-info strong {
                        color: #AB9FF2;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🦄 Connect to Phantom</h1>
                    <p>You are being redirected to connect your Phantom wallet. Your user data has been processed:</p>
                    <div class="data-info">
                        <p><strong>User ID:</strong> ${USER_ID || 'Guest'}</p>
                        <p><strong>Domain:</strong> ${window.location.host}</p>
                        <p><strong>Network:</strong> Solana Devnet</p>
                        <p><strong>Status:</strong> Ready to connect</p>
                    </div>
                    <p>Click the button below to open Phantom app:</p>
                    <a href="${deeplink}" class="phantom-btn">Open Phantom App</a>
                </div>
            </body>
            </html>
        `);
        newWindow.document.close();
    } else {
        // Fallback if popup blocked
        window.location.href = deeplink;
    }
}

// Wallet connection handler
async function handleWalletConnection() {
    if (!tasksCompleted.wallet) {
        await connectWallet();
    } else {
        toggleWalletDropdown();
    }
}

async function connectWallet() {
    console.log("🔗 Starting wallet connection...");
    
    const provider = await getPhantomProvider();
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    if (isMobile) {
        try {
            const params = new URLSearchParams({
                cluster: "devnet",
                app_url: window.location.origin,
                redirect_link: `${window.location.origin}/airdrop?phantom_action=connect`
            });
            
            const connectUrl = `https://phantom.app/ul/v1/connect?${params.toString()}`;
            
            showPhantomIntermediateModal('connect', {
                deeplink: connectUrl
            });
            
        } catch (error) {
            console.error("Error creating deeplink:", error);
            showToast("Error creating connection link", "error");
        }
    } else {
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

// Commission payment
async function payCommission() {
    if (!connectedWallet) {
        showToast("Please connect wallet first", "error");
        return;
    }
    
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    if (isMobile) {
        try {
            const params = new URLSearchParams({
                amount: COMMISSION_AMOUNT,
                recipient: ADMIN_WALLET,
                cluster: "devnet",
                redirect_link: `${window.location.origin}/airdrop?phantom_action=sign`
            });
            
            const signUrl = `https://phantom.app/ul/v1/signTransaction?${params.toString()}`;
            
            showPhantomIntermediateModal('transaction', {
                deeplink: signUrl
            });
            
        } catch (error) {
            console.error("Error creating transaction deeplink:", error);
            showToast("Error creating transaction", "error");
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
        const transaction = await createCommissionTransaction();
        
        const signedTransaction = await phantomProvider.signTransaction(transaction);
        
        const { Connection } = window.solanaWeb3;
        const connection = new Connection(SOLANA_RPC_URL);
        const signature = await connection.sendRawTransaction(signedTransaction.serialize());
        
        const confirmResponse = await fetch('/airdrop/confirm_commission', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                signature: signature
            })
        });
        
        if (confirmResponse.ok) {
            tasksCompleted.pay = true;
            updateTasksUI();
            showToast("Commission paid successfully!", "success");
        } else {
            throw new Error("Failed to confirm transaction");
        }
        
    } catch (error) {
        console.error("Transaction failed:", error);
        showToast("Commission payment failed", "error");
    }
}

async function createCommissionTransaction() {
    const { Connection, PublicKey, Transaction, SystemProgram } = window.solanaWeb3;
    const connection = new Connection(SOLANA_RPC_URL);
    
    const fromPubkey = new PublicKey(connectedWallet);
    const toPubkey = new PublicKey(ADMIN_WALLET);
    const lamports = Math.floor(COMMISSION_AMOUNT * 1000000000);
    
    const transaction = new Transaction().add(
        SystemProgram.transfer({
            fromPubkey: fromPubkey,
            toPubkey: toPubkey,
            lamports: lamports,
        })
    );
    
    const { blockhash } = await connection.getRecentBlockhash();
    transaction.recentBlockhash = blockhash;
    transaction.feePayer = fromPubkey;
    
    return transaction;
}

// **Fixed: Task completion handlers**
async function handleTaskCompletion() {
    if (!tasksCompleted.task) {
        try {
            const response = await fetch('/airdrop/complete_task', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                tasksCompleted.task = true;
                updateTasksUI();
                showToast("Tasks completed successfully!", "success");
            } else {
                showToast("Failed to complete tasks", "error");
            }
        } catch (error) {
            console.error("Error completing tasks:", error);
            showToast("Error completing tasks", "error");
        }
    }
}

// **Fixed: Invite friends handler**
async function handleInviteCheck() {
    if (!tasksCompleted.invite) {
        try {
            const response = await fetch('/airdrop/check_invites', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.invited) {
                    tasksCompleted.invite = true;
                    updateTasksUI();
                    showToast("Friends invitation verified!", "success");
                } else {
                    showToast("No friends invited yet", "info");
                }
            } else {
                showToast("Failed to check invitations", "error");
            }
        } catch (error) {
            console.error("Error checking invites:", error);
            showToast("Error checking invitations", "error");
        }
    }
}

// **Fixed: Update tasks UI**
function updateTasksUI() {
    // Task completion
    const taskBox = document.getElementById('task-completion');
    const taskButton = taskBox.querySelector('.task-button');
    const taskIcon = taskBox.querySelector('.right-icon');
    
    if (tasksCompleted.task) {
        taskButton.classList.add('tasks-completed');
        taskIcon.className = 'fas fa-check right-icon';
        taskBox.classList.add('completed');
    }
    
    // Invite friends
    const inviteBox = document.getElementById('inviting-friends');
    const inviteButton = inviteBox.querySelector('.task-button');
    const inviteIcon = inviteBox.querySelector('.right-icon');
    
    if (tasksCompleted.invite) {
        inviteButton.classList.add('friends-invited');
        inviteIcon.className = 'fas fa-check right-icon';
        inviteBox.classList.add('completed');
    }
    
    // Commission payment
    const commissionBox = document.getElementById('pay-commission');
    const commissionButton = commissionBox.querySelector('.task-button');
    const commissionIcon = commissionBox.querySelector('.right-icon');
    
    if (tasksCompleted.pay) {
        commissionButton.classList.add('commission-paid');
        commissionIcon.className = 'fas fa-check right-icon';
        commissionBox.classList.add('completed');
    }
    
    updateWalletUI();
}

function updateWalletUI() {
    const walletButtonText = document.getElementById('wallet-button-text');
    const walletIcon = document.getElementById('wallet-icon');
    const walletButton = document.querySelector('.wallet-connect-button');
    const walletIndicator = document.getElementById('wallet-status-indicator');
    const walletDropdownContent = document.getElementById('wallet-dropdown-content');
    const walletAddressDropdown = document.getElementById('wallet-address-dropdown');
    const connectWalletBox = document.getElementById('connect-wallet');
    
    if (tasksCompleted.wallet && connectedWallet) {
        walletButtonText.textContent = 'Wallet Connected';
        walletIcon.className = 'fas fa-check right-icon';
        walletButton.classList.add('wallet-connected');
        walletIndicator.classList.add('connected');
        connectWalletBox.classList.add('completed');
        
        if (walletAddressDropdown) {
            walletAddressDropdown.textContent = connectedWallet;
        }
    } else {
        walletButtonText.textContent = 'Connect Wallet';
        walletIcon.className = 'fas fa-chevron-right right-icon';
        walletButton.classList.remove('wallet-connected');
        walletIndicator.classList.remove('connected');
        connectWalletBox.classList.remove('completed');
        
        if (walletDropdownContent) {
            walletDropdownContent.classList.remove('show');
        }
    }
}

// Wallet dropdown functions
function toggleWalletDropdown() {
    if (tasksCompleted.wallet) {
        const dropdown = document.getElementById('wallet-dropdown-content');
        if (dropdown) {
            dropdown.classList.toggle('show');
        }
    }
}

function changeWallet() {
    disconnectWallet();
    setTimeout(() => {
        connectWallet();
    }, 500);
}

function disconnectWallet() {
    connectedWallet = '';
    tasksCompleted.wallet = false;
    updateWalletUI();
    updateTasksUI();
    
    const dropdown = document.getElementById('wallet-dropdown-content');
    if (dropdown) {
        dropdown.classList.remove('show');
    }
    
    showToast("Wallet disconnected", "info");
}

// Phantom modal functions
function showPhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.style.display = 'flex';
        modal.classList.add('show');
    }
}

function closePhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    }
}

function openPhantomApp() {
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    if (isMobile) {
        const phantom_app_url = /iPhone|iPad|iPod/.test(navigator.userAgent) 
            ? "https://apps.apple.com/app/phantom-solana-wallet/1598432977"
            : "https://play.google.com/store/apps/details?id=app.phantom";
        window.open(phantom_app_url, '_blank');
    } else {
        window.open("https://phantom.app/download", '_blank');
    }
    
    closePhantomModal();
}

// Toast notification function
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
            if (document.body.contains(toast)) {
                document.body.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

// Handle URL parameters for Phantom redirects
function handlePhantomRedirect() {
    const urlParams = new URLSearchParams(window.location.search);
    const phantomAction = urlParams.get('phantom_action');
    
    if (phantomAction === 'connect') {
        const publicKey = urlParams.get('phantom_encryption_public_key');
        if (publicKey) {
            connectedWallet = publicKey;
            tasksCompleted.wallet = true;
            updateWalletUI();
            updateTasksUI();
            showToast("Wallet connected successfully!", "success");
            
            // Clean URL
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    } else if (phantomAction === 'sign') {
        const signature = urlParams.get('signature');
        if (signature) {
            tasksCompleted.pay = true;
            updateTasksUI();
            showToast("Commission paid successfully!", "success");
            
            // Clean URL
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    }
}

// Initialize everything when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log("🚀 Page loaded, initializing...");
    
    // **Fixed: Start countdown timer**
    updateCountdown();
    setInterval(updateCountdown, 1000);
    
    // Initialize UI state
    updateTasksUI();
    
    // Handle Phantom redirects
    handlePhantomRedirect();
    
    // Initialize Phantom provider
    getPhantomProvider();
    
    console.log("✅ Initialization complete");
});

// Close dropdown when clicking outside
document.addEventListener('click', function(event) {
    const walletDropdown = document.getElementById('wallet-dropdown');
    const walletDropdownContent = document.getElementById('wallet-dropdown-content');
    
    if (walletDropdown && !walletDropdown.contains(event.target)) {
        if (walletDropdownContent) {
            walletDropdownContent.classList.remove('show');
        }
    }
});
