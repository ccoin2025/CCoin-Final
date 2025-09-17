<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Connect Phantom Wallet</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            text-align: center;
            padding: 50px 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 400px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.1);
            padding: 40px;
            border-radius: 20px;
        }
        .btn {
            background: linear-gradient(135deg, #AB9FF2, #7B68EE);
            color: white;
            border: none;
            padding: 20px 30px;
            border-radius: 25px;
            font-size: 18px;
            cursor: pointer;
            width: 100%;
            margin: 15px 0;
            text-decoration: none;
            display: inline-block;
            box-sizing: border-box;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        .btn:hover {
            background: linear-gradient(135deg, #9A8CF1, #6A5ACD);
            transform: translateY(-2px);
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .debug {
            background: rgba(0, 0, 0, 0.3);
            padding: 15px;
            border-radius: 10px;
            margin: 20px 0;
            font-size: 12px;
            text-align: left;
            max-height: 300px;
            overflow-y: auto;
            font-family: monospace;
        }
        .status {
            margin: 20px 0;
            padding: 15px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.1);
        }
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #ffffff30;
            border-radius: 50%;
            border-top-color: #fff;
            animation: spin 1s ease-in-out infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .instructions {
            background: rgba(255, 255, 255, 0.05);
            padding: 15px;
            border-radius: 10px;
            margin: 20px 0;
            font-size: 14px;
            line-height: 1.5;
        }
        .manual-input {
            background: rgba(255, 255, 255, 0.05);
            padding: 20px;
            border-radius: 15px;
            margin: 20px 0;
            display: none;
        }
        .manual-input.show {
            display: block;
        }
        .manual-input input {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.1);
            color: white;
            font-size: 14px;
            margin: 10px 0;
            font-family: monospace;
            box-sizing: border-box;
        }
        .manual-input input::placeholder {
            color: rgba(255, 255, 255, 0.6);
        }
        .manual-input input:focus {
            outline: none;
            background: rgba(255, 255, 255, 0.2);
        }
        .submit-btn {
            background: linear-gradient(135deg, #28a745, #20c997);
            color: white;
            border: none;
            padding: 15px 25px;
            border-radius: 15px;
            font-size: 16px;
            cursor: pointer;
            margin: 10px 5px;
            transition: all 0.3s ease;
        }
        .submit-btn:hover {
            background: linear-gradient(135deg, #218838, #1ea085);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🦄 Connect Phantom Wallet</h1>
        <p>Connect your Phantom app to participate in CCoin airdrop</p>
        
        <div id="status" class="status">
            <p>📱 Ready to connect to Phantom app</p>
        </div>
        
        <button class="btn" id="connectBtn" onclick="connectToPhantom()">
            🦄 Connect Phantom App
        </button>
        
        <button class="btn" id="manualBtn" onclick="showManualInput()" style="background: linear-gradient(135deg, #17a2b8, #138496);">
            ✋ Enter Wallet Address Manually
        </button>
        
        <div id="manualInput" class="manual-input">
            <h3>📝 Enter Your Phantom Wallet Address</h3>
            <p>Copy your wallet address from Phantom app and paste it here:</p>
            <input type="text" id="walletAddress" placeholder="Enter your Solana wallet address (starts with numbers/letters)" />
            <br>
            <button class="submit-btn" onclick="submitManualAddress()">✅ Connect Wallet</button>
            <button class="submit-btn" onclick="hideManualInput()" style="background: linear-gradient(135deg, #6c757d, #5a6268);">❌ Cancel</button>
        </div>
        
        <div class="instructions">
            <strong>Two ways to connect:</strong><br>
            1. <strong>Auto Connect:</strong> Click "Connect Phantom App" (opens Phantom app)<br>
            2. <strong>Manual:</strong> Click "Enter Manually" and paste your wallet address
        </div>
        
        <div id="debug" class="debug" style="display: none;"></div>
    </div>

    <script>
        var telegramId = '';
        var isConnecting = false;
        
        function log(msg) {
            console.log(msg);
            var debug = document.getElementById('debug');
            if (debug) {
                debug.style.display = 'block';
                debug.innerHTML += '[' + new Date().toLocaleTimeString() + '] ' + msg + '<br>';
                debug.scrollTop = debug.scrollHeight;
            }
        }
        
        function updateStatus(msg, loading = false) {
            var status = document.getElementById('status');
            if (status) {
                var content = loading ? '<div class="loading"></div> ' + msg : msg;
                status.innerHTML = '<p>' + content + '</p>';
            }
        }
        
        function connectToPhantom() {
            if (isConnecting) return;
            
            var connectBtn = document.getElementById('connectBtn');
            if (!connectBtn) return;
            
            isConnecting = true;
            connectBtn.disabled = true;
            connectBtn.textContent = '🔄 Opening Phantom...';
            
            log('🚀 Starting Phantom app connection...');
            updateStatus('📱 Opening Phantom app...', true);
            
            try {
                // استفاده از deep link مستقیم Phantom
                var phantomDeepLink = 'phantom://connect?app=' + encodeURIComponent(window.location.origin) + 
                    '&callback=' + encodeURIComponent(window.location.origin + '/wallet/callback?telegram_id=' + telegramId);
                
                log('🔗 Phantom Deep Link: ' + phantomDeepLink);
                
                // تلاش برای باز کردن deep link
                window.location.href = phantomDeepLink;
                
                // fallback به صورت manual input بعد از 3 ثانیه
                setTimeout(function() {
                    if (isConnecting) {
                        log('⚠️ Deep link timeout, showing manual input');
                        updateStatus('📱 Having trouble opening Phantom? Try manual input below');
                        resetConnection();
                        showManualInput();
                    }
                }, 3000);
                
            } catch (error) {
                log('❌ Deep link error: ' + error.message);
                updateStatus('❌ Error opening Phantom app. Please try manual input.');
                resetConnection();
                showManualInput();
            }
        }
        
        function showManualInput() {
            var manualInput = document.getElementById('manualInput');
            var connectBtn = document.getElementById('connectBtn');
            var manualBtn = document.getElementById('manualBtn');
            
            if (manualInput) {
                manualInput.classList.add('show');
            }
            if (connectBtn) {
                connectBtn.style.display = 'none';
            }
            if (manualBtn) {
                manualBtn.style.display = 'none';
            }
            
            updateStatus('📝 Enter your Phantom wallet address below');
            
            // focus روی input
            setTimeout(function() {
                var walletInput = document.getElementById('walletAddress');
                if (walletInput) {
                    walletInput.focus();
                }
            }, 200);
        }
        
        function hideManualInput() {
            var manualInput = document.getElementById('manualInput');
            var connectBtn = document.getElementById('connectBtn');
            var manualBtn = document.getElementById('manualBtn');
            
            if (manualInput) {
                manualInput.classList.remove('show');
            }
            if (connectBtn) {
                connectBtn.style.display = 'block';
            }
            if (manualBtn) {
                manualBtn.style.display = 'block';
            }
            
            // پاک کردن input
            var walletInput = document.getElementById('walletAddress');
            if (walletInput) {
                walletInput.value = '';
            }
            
            updateStatus('📱 Ready to connect to Phantom app');
        }
        
        async function submitManualAddress() {
            var walletInput = document.getElementById('walletAddress');
            if (!walletInput) return;
            
            var address = walletInput.value.trim();
            
            if (!address) {
                updateStatus('❌ Please enter a wallet address');
                return;
            }
            
            // بررسی فرمت ساده
            if (address.length < 32 || address.length > 44) {
                updateStatus('❌ Invalid wallet address length. Please check your address.');
                return;
            }
            
            log('📝 Manual address submitted: ' + address);
            updateStatus('💾 Saving wallet address...', true);
            
            try {
                await saveWalletAddress(address);
            } catch (error) {
                log('❌ Manual submit error: ' + error.message);
                updateStatus('❌ Error saving address: ' + error.message);
            }
        }
        
        async function saveWalletAddress(publicKey) {
            try {
                log('💾 Saving wallet address to server...');
                
                const response = await fetch('/api/wallet/connect', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        telegram_id: telegramId,
                        wallet_address: publicKey
                    })
                });
                
                const data = await response.json();
                
                if (response.ok && data.success) {
                    log('✅ Wallet saved successfully');
                    
                    updateStatus('✅ Wallet connected successfully!<br><div style="background: rgba(0,0,0,0.3); padding: 10px; border-radius: 5px; margin-top: 10px; word-break: break-all; font-family: monospace; font-size: 12px;">' + publicKey + '</div>');
                    
                    setTimeout(function() {
                        window.location.href = '/airdrop?telegram_id=' + telegramId;
                    }, 2000);
                } else {
                    throw new Error(data.error || 'Server error');
                }
                
            } catch (error) {
                log('❌ Failed to save wallet: ' + error.message);
                updateStatus('❌ Failed to save wallet: ' + error.message);
                
                // نمایش manual input اگر مخفی بود
                if (!document.getElementById('manualInput').classList.contains('show')) {
                    showManualInput();
                }
            }
        }
        
        function resetConnection() {
            isConnecting = false;
            var connectBtn = document.getElementById('connectBtn');
            if (connectBtn) {
                connectBtn.disabled = false;
                connectBtn.textContent = '🦄 Connect Phantom App';
            }
        }
        
        function checkExistingConnection() {
            fetch('/api/wallet/status?telegram_id=' + telegramId)
                .then(function(response) {
                    if (!response.ok) {
                        return;
                    }
                    return response.json();
                })
                .then(function(data) {
                    if (data && data.connected && data.address) {
                        updateStatus('✅ Wallet already connected!<br><div style="background: rgba(0,0,0,0.3); padding: 10px; border-radius: 5px; margin-top: 10px; word-break: break-all; font-family: monospace; font-size: 12px;">' + data.address + '</div>');
                        var connectBtn = document.getElementById('connectBtn');
                        var manualBtn = document.getElementById('manualBtn');
                        if (connectBtn) {
                            connectBtn.textContent = '🔄 Change Wallet';
                        }
                        if (manualBtn) {
                            manualBtn.textContent = '✏️ Change Address';
                        }
                    }
                })
                .catch(function(error) {
                    log('Error checking wallet status: ' + error.message);
                });
        }
        
        function init() {
            var params = new URLSearchParams(window.location.search);
            telegramId = params.get('telegram_id') || '';
            
            if (!telegramId) {
                updateStatus('❌ Error: No telegram ID found');
                log('❌ No telegram_id parameter in URL');
                return;
            }
            
            log('✅ Telegram ID: ' + telegramId);
            updateStatus('📱 Ready to connect to Phantom app');
            
            checkExistingConnection();
            
            // Enter key listener برای manual input
            document.addEventListener('keydown', function(event) {
                if (event.key === 'Enter' && document.getElementById('manualInput').classList.contains('show')) {
                    submitManualAddress();
                }
            });
        }
        
        // Safe initialization
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
        } else {
            init();
        }
        
        log('🔍 Page loaded');
    </script>
</body>
</html>
