<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<meta name="csrf-token" content="{{ request.session.csrf_token }}">
<title>Airdrop</title>
<link href="https://fonts.googleapis.com/css2?family=Urbanist:wght@400;600;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{{ url_for('static', path='css/airdrop.css') }}">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<script src="https://unpkg.com/@solana/web3.js@latest/lib/index.iife.min.js"></script>

<style>
/* استایل منوی کشویی کیف پول */
.wallet-dropdown {
position: relative;
display: inline-block;
width:100%;
}

.wallet-dropdown-content {
display: none;
position: absolute;
background-color:#1a1a1a;
min-width:100%;
box-shadow:0px 8px 16px 0px rgba(0,0,0,0.3);
z-index:9999;
border-radius:10px;
border:2px solid #333;
top:calc(100% + 2px);
left:0;
opacity:0;
transform:translateY(-10px);
transition: all 0.3s ease;
margin-top:0;
}

.wallet-dropdown-content.show {
display: block;
opacity:1;
transform:translateY(0);
}

.wallet-info-dropdown {
background:#1a1a1a;
padding:15px;
border-radius:8px;
text-align: left;
color:#fff;
}

.wallet-address-dropdown {
font-family: monospace;
font-size:11px;
word-break: break-all;
background:#2d2d2d;
padding:8px;
border-radius:5px;
margin:8px 0;
color:#fff;
border:1px solid #444;
max-height:60px;
overflow-y: auto;
}

.wallet-actions-dropdown {
display: flex;
gap:8px;
margin-top:10px;
}

.wallet-action-btn {
background:#333;
color: white;
border:1px solid #555;
padding:10px 15px;
border-radius:6px;
font-size:12px;
cursor: pointer;
flex:1;
text-align: center;
transition: all 0.3s ease;
font-weight:500;
}

.wallet-action-btn:hover {
background:#444;
transform:translateY(-1px);
}

.disconnect-btn {
background:#2d2d2d;
color:#ff4757;
border-color:#ff4757;
}

.disconnect-btn:hover {
background:#ff4757;
color:#fff;
}

.change-btn {
background:#2d2d2d;
color:#ffa502;
border-color:#ffa502;
}

.change-btn:hover {
background:#ffa502;
color:#000;
}

/* استایل دکمه کانکت ولت */
.wallet-connect-button {
position: relative;
}

.wallet-status-indicator {
position: absolute;
top:-3px;
right:-3px;
width:14px;
height:14px;
background:#28a745;
border-radius:50%;
display: none;
border:2px solid #fff;
box-shadow:0 0 0 1px #28a745;
}

.wallet-status-indicator.connected {
display: block;
animation: pulse 2s infinite;
}

@keyframes pulse {
0% {
box-shadow:0 0 0 0 rgba(40,167,69,0.7);
}
70% {
box-shadow:0 0 0 10px rgba(40,167,69,0);
}
100% {
box-shadow:0 0 0 0 rgba(40,167,69,0);
}
}

/* تغییر آیکون برای حالت connected */
.task-button.wallet-connected .right-icon,
.task-button.commission-paid .right-icon,
.task-button.tasks-completed .right-icon,
.task-button.friends-invited .right-icon {
color:#28a745!important;
}

/* تغییر رنگ دکمه برای حالت completed */
.task-box.completed {
border-color:#28a745;
}

.task-box.completed .task-button {
background:rgba(40,167,69,0.1);
}

/* استایل بهتر برای آیکون چک */
.fa-check {
color:#28a745;
font-weight: bold;
}

/* تنظیم spacing برای جلوگیری از تداخل با باکس بعدی */
.task-box {
margin-bottom:15px;
position: relative;
}

/* اطمینان از اینکه dropdown روی المان‌های بعدی قرار می‌گیرد */
.wallet-dropdown {
z-index:10;
}

.wallet-dropdown-content {
position: absolute;
top:100%;
left:0;
right:0;
}

/* تنظیم دقیق positioning برای جلوگیری از تداخل */
.task-box:has(.wallet-dropdown) {
z-index:10;
}

.task-box:not(:has(.wallet-dropdown)) {
z-index:1;
}

/* اضافه کردن margin برای جدا کردن dropdown از باکس بعدی */
#connect-wallet {
margin-bottom:20px;
}

#pay-commission {
margin-top:5px;
}

/* استایل برای دکمه commission در حالت loading */
.task-button.loading {
opacity:0.7;
pointer-events: none;
}

.task-button.loading .right-icon {
animation: spin 1s linear infinite;
}

@keyframes spin {
from { transform:rotate(0deg); }
to { transform:rotate(360deg); }
}

/* استایل Toast notifications */
.toast {
position: fixed;
top:20px;
right:20px;
padding:15px 20px;
border-radius:8px;
color: white;
font-weight:500;
z-index:10000;
max-width:300px;
word-wrap: break-word;
box-shadow:0 4px 12px rgba(0,0,0,0.3);
transform:translateX(100%);
transition: transform 0.3s ease;
}

.toast.show {
transform:translateX(0);
}

.toast-success {
background:#28a745;
}

.toast-error {
background:#dc3545;
}

.toast-info {
background:#007bff;
}

/* بهبود responsive */
@media (max-width:480px) {
.wallet-address-dropdown {
font-size:10px;
padding:6px;
}

.wallet-action-btn {
padding:8px 10px;
font-size:11px;
}

.task-box {
margin-bottom:12px;
}

.toast {
top:10px;
right:10px;
left:10px;
max-width: none;
}
}
</style>
</head>

<body>
<div class="container">
<div class="box">
<div class="countdown">
<span id="days">00</span>d :
<span id="hours">00</span>h :
<span id="minutes">00</span>m :
<span id="seconds">00</span>s
</div>
<div class="token-value">
<p>1 CCoin = $ 0.02</p>
</div>
</div>

<div class="airdrop-criteria">
<h2>Airdrop Criteria</h2>

<div id="task-completion" class="task-box">
<button onclick="handleTaskCompletion()" class="task-button">
<span class="left-text">Tasks Completion</span>
<i class="fas fa-chevron-right right-icon"></i>
</button>
</div>

<div id="inviting-friends" class="task-box">
<button onclick="handleInviteCheck()" class="task-button">
<span class="left-text">Inviting Friends</span>
<i class="fas fa-chevron-right right-icon"></i>
</button>
</div>

<!-- کیف پول با منوی کشویی -->
<div id="connect-wallet" class="task-box">
<div class="wallet-dropdown" id="wallet-dropdown">
<button onclick="toggleWalletDropdown()" class="task-button wallet-connect-button">
<span class="left-text" id="wallet-button-text">Connect Wallet</span>
<div class="wallet-status-indicator" id="wallet-status-indicator"></div>
<i class="fas fa-chevron-right right-icon" id="wallet-icon"></i>
</button>
<!-- منوی کشویی -->
<div id="wallet-dropdown-content" class="wallet-dropdown-content">
<div class="wallet-info-dropdown">
<div><strong>✅ Connected Wallet:</strong></div>
<div id="wallet-address-dropdown" class="wallet-address-dropdown"></div>
<div class="wallet-actions-dropdown">
<button onclick="changeWallet()" class="wallet-action-btn change-btn">
🔄 Change
</button>
<button onclick="disconnectWallet()" class="wallet-action-btn disconnect-btn">
🚫 Disconnect
</button>
</div>
</div>
</div>
</div>
</div>

<div id="pay-commission" class="task-box">
<button onclick="payCommission()" class="task-button" id="commission-button">
<span class="left-text" id="commission-button-text">Pay for the Commission</span>
<i class="fas fa-chevron-right right-icon" id="commission-icon"></i>
</button>
</div>

</div>

<div class="footer-icons">
<a href="/leaders" class="footer-btn">
<i class="fas fa-medal"></i>
<span>Leaders</span>
</a>
<a href="/friends" class="footer-btn">
<i class="fas fa-user-friends"></i>
<span>Friends</span>
</a>
<a href="/home" class="footer-btn">
<i class="fas fa-home"></i>
<span>Home</span>
</a>
<a href="/earn" class="footer-btn">
<i class="fas fa-coins"></i>
<span>Earn</span>
</a>
<a href="/airdrop" class="footer-btn active">
<i class="fas fa-rocket"></i>
<span>AirDrop</span>
</a>
</div>
</div>

<script>
const USER_ID = "{{ request.session.telegram_id }}";
const SOLANA_RPC_URL = "{{ config.SOLANA_RPC }}";
const COMMISSION_AMOUNT = {{ config.COMMISSION_AMOUNT if config.COMMISSION_AMOUNT else 0.1 }};
const ADMIN_WALLET = "{{ config.ADMIN_WALLET }}";

// وضعیت‌های اولیه از backend
const INITIAL_TASKS_COMPLETED = {{'true' if tasks_completed else 'false'}};
const INITIAL_INVITED_FRIENDS = {{'true' if invited else 'false'}};
const INITIAL_WALLET_CONNECTED = {{'true' if wallet_connected else 'false'}};
const INITIAL_COMMISSION_PAID = {{'true' if commission_paid else 'false'}};
const INITIAL_WALLET_ADDRESS = "{{ user_wallet_address if user_wallet_address else '' }}";

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

// Initialize Phantom provider
function getPhantomProvider() {
if ("solana" in window) {
const provider = window.solana;
if (provider.isPhantom) {
return provider;
}
}
return null;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
phantomProvider = getPhantomProvider();
updateTasksUI();
initCountdown();

// بررسی وضعیت اتصال wallet
if (INITIAL_WALLET_CONNECTED && INITIAL_WALLET_ADDRESS) {
updateWalletUI(INITIAL_WALLET_ADDRESS, true);
}
});

// شمارش معکوس
function initCountdown() {
const countdownDate = new Date("2024-12-31T23:59:59").getTime();

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

// تابع اصلی پرداخت کمیسیون
async function payCommission() {
if (tasksCompleted.pay === 'true') {
showToast('Commission already paid!', 'info');
return;
}

if (!phantomProvider) {
showToast('Please install Phantom wallet first!', 'error');
window.open('https://phantom.app/', '_blank');
return;
}

if (!connectedWallet || tasksCompleted.wallet !== 'true') {
showToast('Please connect your wallet first!', 'error');
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

// Add transfer instruction
transaction.add(
solanaWeb3.SystemProgram.transfer({
fromPubkey: phantomProvider.publicKey,
toPubkey: new solanaWeb3.PublicKey(ADMIN_WALLET),
lamports: lamports
})
);

// Get recent blockhash
const { blockhash } = await connection.getLatestBlockhash();
transaction.recentBlockhash = blockhash;
transaction.feePayer = phantomProvider.publicKey;

console.log('Sending transaction for', COMMISSION_AMOUNT, 'SOL to', ADMIN_WALLET);

// Sign and send transaction
const { signature } = await phantomProvider.signAndSendTransaction(transaction);

console.log('Transaction signature:', signature);
commissionText.textContent = 'Confirming transaction...';

// Confirm transaction
const confirmation = await connection.confirmTransaction(signature, 'confirmed');

if (confirmation.value.err) {
throw new Error('Transaction failed to confirm');
}

console.log('Transaction confirmed:', signature);

// Update backend
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

if (result.success) {
// Update state
tasksCompleted.pay = 'true';
updateTasksUI();
showToast(`Commission paid successfully! (${COMMISSION_AMOUNT} SOL)`, 'success');
} else {
throw new Error(result.message || 'Failed to confirm commission payment');
}

} catch (error) {
console.error('Commission payment failed:', error);
let errorMessage = 'Payment failed: ' + error.message;

if (error.message.includes('User rejected')) {
errorMessage = 'Payment cancelled by user';
} else if (error.message.includes('insufficient funds')) {
errorMessage = `Insufficient funds. You need at least ${COMMISSION_AMOUNT} SOL + fees`;
} else if (error.message.includes('Transaction failed')) {
errorMessage = 'Transaction failed. Please try again';
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
dropdown.classList.toggle('show');
}

// Handle wallet connection
async function connectWallet() {
if (!phantomProvider) {
showToast('Please install Phantom wallet first!', 'error');
window.open('https://phantom.app/', '_blank');
return;
}

try {
const response = await phantomProvider.connect();
console.log('Connected to wallet:', response.publicKey.toString());

const walletAddress = response.publicKey.toString();

// Update backend
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

if (result.success) {
connectedWallet = walletAddress;
tasksCompleted.wallet = 'true';
updateWalletUI(walletAddress, true);
updateTasksUI();
showToast('Wallet connected successfully!', 'success');
} else {
throw new Error(result.message || 'Failed to connect wallet');
}

} catch (error) {
console.error('Wallet connection failed:', error);
showToast('Failed to connect wallet: ' + error.message, 'error');
}
}

// Change wallet
async function changeWallet() {
try {
await phantomProvider.disconnect();
connectedWallet = '';
tasksCompleted.wallet = 'false';
updateWalletUI('', false);
updateTasksUI();
document.getElementById('wallet-dropdown-content').classList.remove('show');
showToast('Wallet disconnected. Click to connect a new one.', 'info');
} catch (error) {
console.error('Failed to disconnect wallet:', error);
}
}

// Disconnect wallet
async function disconnectWallet() {
try {
await phantomProvider.disconnect();
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
});

// Auto-connect wallet if available on page load
document.addEventListener('DOMContentLoaded', async function() {
if (phantomProvider && phantomProvider.isConnected && !connectedWallet) {
try {
console.log('Auto-connecting to previously connected wallet...');
const publicKey = phantomProvider.publicKey?.toString();
if (publicKey) {
connectedWallet = publicKey;
tasksCompleted.wallet = 'true';
updateWalletUI(publicKey, true);
updateTasksUI();
}
} catch (error) {
console.log('Auto-connect failed:', error);
}
}
});
</script>
</body>
</html>
