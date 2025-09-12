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

// **New: Enhanced Phantom detection**
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

// **New: Show intermediate modal**
function showPhantomIntermediateModal(type, data) {
    const modal = document.getElementById('phantom-intermediate-modal');
    const title = document.getElementById('intermediate-modal-title');
    const content = document.getElementById('intermediate-modal-content');
    const actionBtn = document.getElementById('intermediate-action-btn');
    
    if (!modal || !title || !content || !actionBtn) {
        console.error("Modal elements not found");
        return;
    }
    
    if (type === 'connect') {
        title.textContent = 'Connect to Phantom Wallet';
        content.innerHTML = `
            <p>The following information will be sent to connect to Phantom wallet:</p>
            <div class="data-display">
                <p><strong>Request Type:</strong> Wallet Connection</p>
                <p><strong>Domain:</strong> ${window.location.host}</p>
                <p><strong>Network:</strong> Solana Devnet</p>
            </div>
            <p>Do you want to proceed to the external browser to open Phantom app?</p>
        `;
        actionBtn.textContent = 'Open Phantom';
        actionBtn.onclick = () => openPhantomForConnect(data.deeplink);
    } else if (type === 'transaction') {
        title.textContent = 'Send Transaction';
        content.innerHTML = `
            <p>The following transaction will be sent to Phantom wallet:</p>
            <div class="data-display">
                <p><strong>Transaction Type:</strong> Commission Payment</p>
                <p><strong>Amount:</strong> ${COMMISSION_AMOUNT} SOL</p>
                <p><strong>Recipient:</strong> ${ADMIN_WALLET}</p>
                <p><strong>Network:</strong> Solana Devnet</p>
            </div>
            <p>Do you want to proceed to the external browser to open Phantom app?</p>
        `;
        actionBtn.textContent = 'Open Phantom';
        actionBtn.onclick = () => openPhantomForTransaction(data.deeplink);
    }
    
    modal.style.display = 'flex';
    modal.classList.add('show');
}

// **New: Close intermediate modal**
function closeIntermediateModal() {
    const modal = document.getElementById('phantom-intermediate-modal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    }
}

// **New: Open Phantom for connection**
function openPhantomForConnect(deeplink) {
    closeIntermediateModal();
    
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    if (isMobile) {
        window.location.href = deeplink;
        
        setTimeout(() => {
            const phantom_app_url = /iPhone|iPad|iPod/.test(navigator.userAgent) 
                ? "https://apps.apple.com/app/phantom-solana-wallet/1598432977"
                : "https://play.google.com/store/apps/details?id=app.phantom";
            window.open(phantom_app_url, '_blank');
        }, 3000);
    } else {
        if (phantomProvider) {
            connectWalletDirect();
        } else {
            showToast("Please install Phantom extension first", "info");
            window.open("https://phantom.app/download", '_blank');
        }
    }
}

// **New: Open Phantom for transaction**
function openPhantomForTransaction(deeplink) {
    closeIntermediateModal();
    
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    if (isMobile) {
        window.location.href = deeplink;
        
        setTimeout(() => {
            const phantom_app_url = /iPhone|iPad|iPod/.test(navigator.userAgent) 
                ? "https://apps.apple.com/app/phantom-solana-wallet/1598432977"
                : "https://play.google.com/store/apps/details?id=app.phantom";
            window.open(phantom_app_url, '_blank');
        }, 3000);
    } else {
        if (phantomProvider && connectedWallet) {
            sendCommissionTransaction();
        } else {
            showToast("Please connect wallet first", "error");
        }
    }
}

// **Modified: Wallet connection handler**
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
            showToast("Wallet connected successfully!", "success");
        } else {
            throw new Error("Failed to save wallet connection");
        }
        
    } catch (error) {
        console.error("Connection failed:", error);
        showToast("Wallet connection failed", "error");
    }
}

// **Modified: Commission payment**
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
        
        const signedTransaction = await phantomProvider.signTransaction(transaction);
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
            updateCommissionUI();
            showToast("Commission paid successfully!", "success");
        } else {
            throw new Error("Failed to confirm transaction");
        }
        
    } catch (error) {
        console.error("Transaction failed:", error);
        showToast("Commission payment failed", "error");
    }
}

// **New: Handle Phantom redirects**
function handlePhantomRedirect() {
    const urlParams = new URLSearchParams(window.location.search);
    const action = urlParams.get('phantom_action');
    
    if (action === 'connect') {
        const publicKey = urlParams.get('public_key');
        
        if (publicKey) {
            connectedWallet = publicKey;
            
            fetch('/airdrop/connect_wallet', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    wallet: connectedWallet
                })
            }).then(response => {
                if (response.ok) {
                    tasksCompleted.wallet = true;
                    updateWalletUI();
                    showToast("Wallet connected successfully!", "success");
                }
            });
        }
        
        window.history.replaceState({}, document.title, window.location.pathname);
        
    } else if (action === 'sign') {
        const signature = urlParams.get('signature');
        
        if (signature) {
            fetch('/airdrop/confirm_commission', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    signature: signature
                })
            }).then(response => {
                if (response.ok) {
                    tasksCompleted.pay = true;
                    updateCommissionUI();
                    showToast("Commission paid successfully!", "success");
                } else {
                    showToast("Error confirming transaction", "error");
                }
            });
        }
        
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

// **New: UI update functions**
function updateWalletUI() {
    const button = document.getElementById('wallet-button-text');
    const icon = document.getElementById('wallet-icon');
    const indicator = document.getElementById('wallet-status-indicator');
    const addressDiv = document.getElementById('wallet-address-dropdown');
    
    if (tasksCompleted.wallet && connectedWallet) {
        button.textContent = 'Wallet Connected';
        icon.className = 'fas fa-check right-icon';
        indicator.classList.add('connected');
        
        if (addressDiv) {
            addressDiv.textContent = connectedWallet;
        }
    }
}

function updateCommissionUI() {
    const button = document.getElementById('commission-button-text');
    const icon = document.getElementById('commission-icon');
    
    if (tasksCompleted.pay) {
        button.textContent = 'Commission Paid';
        icon.className = 'fas fa-check right-icon';
    }
}

function showToast(message, type = 'info') {
    const existingToasts = document.querySelectorAll('.toast');
    existingToasts.forEach(toast => toast.remove());
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 100);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// Keep original functions
function toggleWalletDropdown() {
    if (!tasksCompleted.wallet) return;
    
    const dropdown = document.getElementById('wallet-dropdown-content');
    if (dropdown) {
        dropdown.classList.toggle('show');
    }
}

async function disconnectWallet() {
    try {
        if (phantomProvider && phantomProvider.disconnect) {
            await phantomProvider.disconnect();
        }
        
        const response = await fetch('/airdrop/connect_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                wallet: ""
            })
        });
        
        if (response.ok) {
            connectedWallet = null;
            tasksCompleted.wallet = false;
            tasksCompleted.pay = false;
            
            // Reset UI
            document.getElementById('wallet-button-text').textContent = 'Connect Wallet';
            document.getElementById('wallet-icon').className = 'fas fa-chevron-right right-icon';
            document.getElementById('wallet-status-indicator').classList.remove('connected');
            document.getElementById('commission-button-text').textContent = 'Pay for the Commission';
            document.getElementById('commission-icon').className = 'fas fa-chevron-right right-icon';
            
            showToast("Wallet disconnected", "info");
            
            const dropdown = document.getElementById('wallet-dropdown-content');
            if (dropdown) {
                dropdown.classList.remove('show');
            }
        }
    } catch (error) {
        console.error("Disconnect failed:", error);
        showToast("Error disconnecting wallet", "error");
    }
}

function changeWallet() {
    disconnectWallet();
    setTimeout(() => connectWallet(), 500);
}

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
    const isMobile = /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|OperaMini/i.test(navigator.userAgent);
    
    if (isMobile) {
        window.location.href = "phantom://browse/" + encodeURIComponent(window.location.href);
        
        setTimeout(() => {
            window.open("https://phantom.app/download", "_blank");
        }, 2000);
    } else {
        showToast("Please install Phantom extension for your browser", "info");
        window.open("https://phantom.app/download", "_blank");
    }
    
    closePhantomModal();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async function() {
    console.log("🚀 DOM loaded, initializing application...");
    
    handlePhantomRedirect();
    
    phantomProvider = await getPhantomProvider();
    
    if (phantomProvider) {
        console.log("✅ Phantom successfully detected!");
    } else {
        console.log("⚠️ Phantom not found - user needs to install it");
    }
    
    updateWalletUI();
    updateCommissionUI();
    
    // Close intermediate modal on cancel
    document.getElementById('intermediate-close-btn').addEventListener('click', closeIntermediateModal);
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.wallet-dropdown')) {
            const dropdowns = document.querySelectorAll('.wallet-dropdown-content.show');
            dropdowns.forEach(dropdown => {
                dropdown.classList.remove('show');
            });
        }
    });
});

// Keep all other original functions as they were...
function handleTaskCompletion() {
    // Original function
}

function handleInviteCheck() {
    // Original function  
}

function initCountdown() {
    // Original function
}
