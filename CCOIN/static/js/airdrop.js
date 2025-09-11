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

// متغیرهای جدید برای مدیریت session
let dappKeyPair = null;
let sharedSecret = null;
let phantomSession = null;

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

// **تابع جدید برای تولید کلیدهای رمزنگاری**
function generateDappKeyPair() {
    if (typeof nacl !== 'undefined') {
        dappKeyPair = nacl.box.keyPair();
        return dappKeyPair;
    } else {
        // Fallback برای محیط‌هایی که nacl ندارند
        console.warn("NaCl not available, using fallback");
        return null;
    }
}

// **تابع جدید برای رمزنگاری payload**
function encryptPayload(payload, sharedSecret) {
    if (!sharedSecret || typeof nacl === 'undefined') {
        return [null, JSON.stringify(payload)];
    }
    
    const nonce = nacl.randomBytes(24);
    const encryptedPayload = nacl.box.after(
        Buffer.from(JSON.stringify(payload)),
        nonce,
        sharedSecret
    );
    return [nonce, encryptedPayload];
}

// **تابع جدید برای رمزگشایی payload**
function decryptPayload(data, nonce, sharedSecret) {
    if (!sharedSecret || typeof nacl === 'undefined') {
        return JSON.parse(data);
    }
    
    const decryptedData = nacl.box.open.after(
        typeof data === 'string' ? base58.decode(data) : data,
        typeof nonce === 'string' ? base58.decode(nonce) : nonce,
        sharedSecret
    );
    return JSON.parse(Buffer.from(decryptedData).toString("utf8"));
}

// **تابع جدید برای نمایش پنجره واسط**
function showPhantomIntermediateModal(type, data) {
    const modal = document.getElementById('phantom-intermediate-modal');
    const title = document.getElementById('intermediate-modal-title');
    const content = document.getElementById('intermediate-modal-content');
    const actionBtn = document.getElementById('intermediate-action-btn');
    
    if (type === 'connect') {
        title.textContent = 'اتصال به کیف پول Phantom';
        content.innerHTML = `
            <p>برای اتصال به کیف پول Phantom، اطلاعات زیر به اپ ارسال می‌شود:</p>
            <div class="data-display">
                <p><strong>نوع درخواست:</strong> اتصال کیف پول</p>
                <p><strong>دامنه:</strong> ${window.location.host}</p>
                <p><strong>شبکه:</strong> Solana Devnet</p>
                <p><strong>کلید عمومی dApp:</strong> ${data.publicKey}</p>
            </div>
            <p>آیا می‌خواهید به اپ Phantom منتقل شوید؟</p>
        `;
        actionBtn.textContent = 'باز کردن Phantom';
        actionBtn.onclick = () => openPhantomForConnect(data.deeplink);
    } else if (type === 'transaction') {
        title.textContent = 'ارسال تراکنش';
        content.innerHTML = `
            <p>تراکنش زیر به کیف پول Phantom ارسال می‌شود:</p>
            <div class="data-display">
                <p><strong>نوع تراکنش:</strong> پرداخت کمیسیون</p>
                <p><strong>مقدار:</strong> ${COMMISSION_AMOUNT} SOL</p>
                <p><strong>مقصد:</strong> ${ADMIN_WALLET}</p>
                <p><strong>شبکه:</strong> Solana Devnet</p>
            </div>
            <p>آیا می‌خواهید به اپ Phantom منتقل شوید؟</p>
        `;
        actionBtn.textContent = 'باز کردن Phantom';
        actionBtn.onclick = () => openPhantomForTransaction(data.deeplink);
    }
    
    modal.style.display = 'flex';
    modal.classList.add('show');
}

// **تابع جدید برای بستن پنجره واسط**
function closeIntermediateModal() {
    const modal = document.getElementById('phantom-intermediate-modal');
    modal.classList.remove('show');
    setTimeout(() => {
        modal.style.display = 'none';
    }, 300);
}

// **تابع جدید برای باز کردن Phantom برای اتصال**
function openPhantomForConnect(deeplink) {
    closeIntermediateModal();
    
    // تشخیص موبایل
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    if (isMobile) {
        // برای موبایل از deeplink استفاده کنیم
        window.location.href = deeplink;
        
        // Fallback به app store
        setTimeout(() => {
            const phantom_app_url = /iPhone|iPad|iPod/.test(navigator.userAgent) 
                ? "https://apps.apple.com/app/phantom-solana-wallet/1598432977"
                : "https://play.google.com/store/apps/details?id=app.phantom";
            window.open(phantom_app_url, '_blank');
        }, 3000);
    } else {
        // برای دسکتاپ
        if (phantomProvider) {
            connectWalletDirect();
        } else {
            showToast("لطفاً ابتدا افزونه Phantom را نصب کنید", "info");
            window.open("https://phantom.app/download", '_blank');
        }
    }
}

// **تابع جدید برای باز کردن Phantom برای تراکنش**
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
            showToast("ابتدا کیف پول را متصل کنید", "error");
        }
    }
}

// **تابع اصلاح شده برای اتصال کیف پول**
async function connectWallet() {
    console.log("🔗 Starting wallet connection...");
    
    const provider = await getPhantomProvider();
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    if (isMobile) {
        // برای موبایل از deeplink استفاده کنیم
        try {
            // تولید کلیدهای رمزنگاری
            if (!dappKeyPair) {
                generateDappKeyPair();
            }
            
            let publicKeyParam = '';
            if (dappKeyPair && typeof base58 !== 'undefined') {
                publicKeyParam = base58.encode(dappKeyPair.publicKey);
            }
            
            // ساخت URL deeplink
            const params = new URLSearchParams({
                dapp_encryption_public_key: publicKeyParam,
                cluster: "devnet",
                app_url: window.location.origin,
                redirect_link: `${window.location.origin}/airdrop?phantom_action=connect`
            });
            
            const connectUrl = `https://phantom.app/ul/v1/connect?${params.toString()}`;
            
            // نمایش پنجره واسط
            showPhantomIntermediateModal('connect', {
                publicKey: publicKeyParam,
                deeplink: connectUrl
            });
            
        } catch (error) {
            console.error("Error creating deeplink:", error);
            showToast("خطا در ایجاد لینک اتصال", "error");
        }
    } else {
        // برای دسکتاپ از روش مستقیم استفاده کنیم
        if (provider) {
            await connectWalletDirect();
        } else {
            showPhantomModal();
        }
    }
}

// **تابع جدید برای اتصال مستقیم کیف پول**
async function connectWalletDirect() {
    try {
        const response = await phantomProvider.connect();
        connectedWallet = response.publicKey.toString();
        
        // ذخیره در backend
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
            updateTasksUI();
            showToast("کیف پول با موفقیت متصل شد!", "success");
        } else {
            throw new Error("Failed to save wallet connection");
        }
        
    } catch (error) {
        console.error("Connection failed:", error);
        showToast("اتصال کیف پول ناموفق بود", "error");
    }
}

// **تابع اصلاح شده برای پرداخت کمیسیون**
async function payCommission() {
    if (!connectedWallet) {
        showToast("ابتدا کیف پول را متصل کنید", "error");
        return;
    }
    
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    if (isMobile) {
        // برای موبایل از deeplink استفاده کنیم
        try {
            if (!phantomSession) {
                showToast("جلسه Phantom نامعتبر است. لطفاً مجدداً متصل شوید", "error");
                return;
            }
            
            // ساخت تراکنش
            const transaction = await createCommissionTransaction();
            const payload = {
                session: phantomSession,
                transaction: base58.encode(transaction.serialize({ verifySignatures: false }))
            };
            
            // رمزنگاری payload
            const [nonce, encryptedPayload] = encryptPayload(payload, sharedSecret);
            
            let nonceParam = '';
            let payloadParam = '';
            
            if (nonce && encryptedPayload && typeof base58 !== 'undefined') {
                nonceParam = base58.encode(nonce);
                payloadParam = base58.encode(encryptedPayload);
            }
            
            // ساخت URL deeplink برای تراکنش
            const params = new URLSearchParams({
                dapp_encryption_public_key: base58.encode(dappKeyPair.publicKey),
                nonce: nonceParam,
                redirect_link: `${window.location.origin}/airdrop?phantom_action=sign`,
                payload: payloadParam
            });
            
            const signUrl = `https://phantom.app/ul/v1/signTransaction?${params.toString()}`;
            
            // نمایش پنجره واسط
            showPhantomIntermediateModal('transaction', {
                deeplink: signUrl
            });
            
        } catch (error) {
            console.error("Error creating transaction deeplink:", error);
            showToast("خطا در ایجاد تراکنش", "error");
        }
    } else {
        // برای دسکتاپ از روش مستقیم استفاده کنیم
        if (phantomProvider && connectedWallet) {
            await sendCommissionTransaction();
        } else {
            showToast("ابتدا کیف پول را متصل کنید", "error");
        }
    }
}

// **تابع جدید برای ساخت تراکنش کمیسیون**
async function createCommissionTransaction() {
    const { Connection, PublicKey, Transaction, SystemProgram } = window.solanaWeb3;
    const connection = new Connection(SOLANA_RPC_URL);
    
    const fromPubkey = new PublicKey(connectedWallet);
    const toPubkey = new PublicKey(ADMIN_WALLET);
    const lamports = Math.floor(COMMISSION_AMOUNT * 1000000000); // Convert SOL to lamports
    
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

// **تابع جدید برای ارسال مستقیم تراکنش**
async function sendCommissionTransaction() {
    try {
        const transaction = await createCommissionTransaction();
        
        // امضای تراکنش توسط Phantom
        const signedTransaction = await phantomProvider.signTransaction(transaction);
        
        // ارسال تراکنش
        const { Connection } = window.solanaWeb3;
        const connection = new Connection(SOLANA_RPC_URL);
        const signature = await connection.sendRawTransaction(signedTransaction.serialize());
        
        // تأیید تراکنش در backend
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
            showToast("کمیسیون با موفقیت پرداخت شد!", "success");
        } else {
            throw new Error("Failed to confirm transaction");
        }
        
    } catch (error) {
        console.error("Transaction failed:", error);
        showToast("پرداخت کمیسیون ناموفق بود", "error");
    }
}

// **تابع جدید برای پردازش نتایج Phantom**
function handlePhantomRedirect() {
    const urlParams = new URLSearchParams(window.location.search);
    const action = urlParams.get('phantom_action');
    
    if (action === 'connect') {
        // پردازش نتیجه اتصال
        const phantomPublicKey = urlParams.get('phantom_encryption_public_key');
        const data = urlParams.get('data');
        const nonce = urlParams.get('nonce');
        
        if (phantomPublicKey && data && nonce && dappKeyPair) {
            try {
                // ایجاد shared secret
                if (typeof nacl !== 'undefined' && typeof base58 !== 'undefined') {
                    sharedSecret = nacl.box.before(
                        base58.decode(phantomPublicKey),
                        dappKeyPair.secretKey
                    );
                    
                    // رمزگشایی اطلاعات
                    const connectData = decryptPayload(data, nonce, sharedSecret);
                    phantomSession = connectData.session;
                    connectedWallet = connectData.public_key;
                    
                    // ذخیره در backend
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
                            updateTasksUI();
                            showToast("کیف پول با موفقیت متصل شد!", "success");
                        }
                    });
                }
            } catch (error) {
                console.error("Error processing connection result:", error);
                showToast("خطا در پردازش نتیجه اتصال", "error");
            }
        }
        
        // پاک کردن URL parameters
        window.history.replaceState({}, document.title, window.location.pathname);
        
    } else if (action === 'sign') {
        // پردازش نتیجه امضای تراکنش
        const data = urlParams.get('data');
        const nonce = urlParams.get('nonce');
        
        if (data && nonce && sharedSecret) {
            try {
                const signData = decryptPayload(data, nonce, sharedSecret);
                const signature = signData.signature;
                
                // تأیید تراکنش در backend
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
                        updateTasksUI();
                        showToast("کمیسیون با موفقیت پرداخت شد!", "success");
                    } else {
                        showToast("خطا در تأیید تراکنش", "error");
                    }
                });
                
            } catch (error) {
                console.error("Error processing transaction result:", error);
                showToast("خطا در پردازش نتیجه تراکنش", "error");
            }
        }
        
        // پاک کردن URL parameters
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async function() {
    console.log("🚀 DOM loaded, initializing application...");
    
    // بررسی redirect از Phantom
    handlePhantomRedirect();
    
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
    checkInitialStates();
});

// **تابع برای باز کردن اپ Phantom**
function openPhantomApp() {
    // Try to open Phantom app
    const phantomUrl = "https://phantom.app/ul/browse/" + encodeURIComponent(window.location.href);
    
    // For mobile, try to open the app directly
    if (/Android|iPhone|iPad|iPod|BlackBerry|IEMobile|OperaMini/i.test(navigator.userAgent)) {
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

// **تابع برای بروزرسانی UI**
function updateTasksUI() {
    // بروزرسانی دکمه Connect Wallet
    const connectBtn = document.querySelector('#connect-wallet .task-button');
    const connectIcon = document.querySelector('#connect-wallet .right-icon');
    const connectBox = document.getElementById('connect-wallet');
    
    if (tasksCompleted.wallet && connectedWallet) {
        connectBtn.classList.add('wallet-connected');
        connectIcon.className = 'right-icon fas fa-check';
        connectBox.classList.add('completed');
        
        // نمایش dropdown برای wallet
        const dropdown = connectBox.querySelector('.wallet-dropdown-content');
        if (dropdown) {
            const addressDiv = dropdown.querySelector('.wallet-address-dropdown');
            if (addressDiv) {
                addressDiv.textContent = connectedWallet;
            }
        }
    }
    
    // بروزرسانی دکمه Pay Commission
    const commissionBtn = document.querySelector('#pay-commission .task-button');
    const commissionIcon = document.querySelector('#pay-commission .right-icon');
    const commissionBox = document.getElementById('pay-commission');
    
    if (tasksCompleted.pay) {
        commissionBtn.classList.add('commission-paid');
        commissionIcon.className = 'right-icon fas fa-check';
        commissionBox.classList.add('completed');
    }
    
    // سایر tasks...
    if (tasksCompleted.task) {
        const taskBtn = document.querySelector('#complete-tasks .task-button');
        const taskIcon = document.querySelector('#complete-tasks .right-icon');
        const taskBox = document.getElementById('complete-tasks');
        
        if (taskBtn) taskBtn.classList.add('tasks-completed');
        if (taskIcon) taskIcon.className = 'right-icon fas fa-check';
        if (taskBox) taskBox.classList.add('completed');
    }
    
    if (tasksCompleted.invite) {
        const inviteBtn = document.querySelector('#invite-friends .task-button');
        const inviteIcon = document.querySelector('#invite-friends .right-icon');
        const inviteBox = document.getElementById('invite-friends');
        
        if (inviteBtn) inviteBtn.classList.add('friends-invited');
        if (inviteIcon) inviteIcon.className = 'right-icon fas fa-check';
        if (inviteBox) inviteBox.classList.add('completed');
    }
}

// **تابع برای نمایش/مخفی کردن dropdown wallet**
function toggleWalletDropdown() {
    if (!tasksCompleted.wallet) return;
    
    const dropdown = document.querySelector('#connect-wallet .wallet-dropdown-content');
    if (dropdown) {
        dropdown.classList.toggle('show');
    }
}

// **تابع برای disconnect کردن wallet**
async function disconnectWallet() {
    try {
        if (phantomProvider && phantomProvider.disconnect) {
            await phantomProvider.disconnect();
        }
        
        // پاک کردن از backend
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
            phantomSession = null;
            sharedSecret = null;
            tasksCompleted.wallet = false;
            tasksCompleted.pay = false;
            
            updateTasksUI();
            showToast("کیف پول قطع شد", "info");
            
            // بستن dropdown
            const dropdown = document.querySelector('#connect-wallet .wallet-dropdown-content');
            if (dropdown) {
                dropdown.classList.remove('show');
            }
        }
    } catch (error) {
        console.error("Disconnect failed:", error);
        showToast("خطا در قطع اتصال", "error");
    }
}

// **تابع برای copy کردن آدرس wallet**
function copyWalletAddress() {
    if (connectedWallet) {
        navigator.clipboard.writeText(connectedWallet).then(() => {
            showToast("آدرس کپی شد", "success");
        }).catch(() => {
            showToast("خطا در کپی آدرس", "error");
        });
    }
}

// **تابع برای نمایش modal اصلی Phantom**
function showPhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.style.display = 'flex';
        modal.classList.add('show');
    }
}

// **تابع برای بستن modal اصلی Phantom**
function closePhantomModal() {
    const modal = document.getElementById('phantom-modal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 300);
    }
}

// **تابع برای setup کردن event listeners برای Phantom**
function setupPhantomListeners() {
    if (phantomProvider) {
        phantomProvider.on('connect', (publicKey) => {
            console.log("Phantom connected:", publicKey.toString());
            connectedWallet = publicKey.toString();
            tasksCompleted.wallet = true;
            updateTasksUI();
        });
        
        phantomProvider.on('disconnect', () => {
            console.log("Phantom disconnected");
            connectedWallet = null;
            phantomSession = null;
            sharedSecret = null;
            tasksCompleted.wallet = false;
            tasksCompleted.pay = false;
            updateTasksUI();
        });
    }
}

// **تابع برای شروع countdown**
function initCountdown() {
    // Implementation for countdown timer
    const countdownElement = document.querySelector('.countdown');
    if (countdownElement) {
        // Add countdown logic here if needed
    }
}

// Event listeners برای click خارج از dropdown
document.addEventListener('click', function(event) {
    const walletBox = document.getElementById('connect-wallet');
    const dropdown = document.querySelector('#connect-wallet .wallet-dropdown-content');
    
    if (dropdown && !walletBox.contains(event.target)) {
        dropdown.classList.remove('show');
    }
});

// Event listeners برای دکمه‌ها
document.addEventListener('click', function(event) {
    if (event.target.closest('#connect-wallet .task-button')) {
        if (tasksCompleted.wallet) {
            toggleWalletDropdown();
        } else {
            connectWallet();
        }
    }
    
    if (event.target.closest('#pay-commission .task-button')) {
        if (!tasksCompleted.pay) {
            payCommission();
        }
    }
    
    if (event.target.classList.contains('disconnect-btn')) {
        disconnectWallet();
    }
    
    if (event.target.classList.contains('change-btn')) {
        disconnectWallet();
        setTimeout(connectWallet, 500);
    }
    
    if (event.target.classList.contains('copy-btn')) {
        copyWalletAddress();
    }
    
    if (event.target.id === 'intermediate-cancel-btn') {
        closeIntermediateModal();
    }
});
