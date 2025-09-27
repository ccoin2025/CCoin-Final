<script>
        // Global variables
        let walletConnected = {{ 'true' if wallet_connected else 'false' }};
        let currentWalletAddress = "{{ user_wallet_address if user_wallet_address else '' }}";

        // Countdown timer
        function updateCountdown() {
            const endDate = new Date('2025-12-31T23:59:59').getTime();
            const now = new Date().getTime();
            const timeLeft = endDate - now;

            const days = Math.floor(timeLeft / (1000 * 60 * 60 * 24));
            const hours = Math.floor((timeLeft % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);

            document.getElementById('days').textContent = days.toString().padStart(2, '0');
            document.getElementById('hours').textContent = hours.toString().padStart(2, '0');
            document.getElementById('minutes').textContent = minutes.toString().padStart(2, '0');
            document.getElementById('seconds').textContent = seconds.toString().padStart(2, '0');

            if (timeLeft < 0) {
                document.querySelector('.countdown').innerHTML = "Airdrop Ended";
            }
        }

        // Initialize countdown
        updateCountdown();
        setInterval(updateCountdown, 1000);

        // Toast notification function
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

        // Wallet dropdown functionality
        document.addEventListener('DOMContentLoaded', function() {
            // تابع برای toggle کردن dropdown
            function toggleWalletDropdown() {
                const dropdown = document.querySelector('.wallet-dropdown-content');
                if (dropdown) {
                    dropdown.classList.toggle('show');
                }
            }

            // اضافه کردن event listener به دکمه connect wallet
            const walletButton = document.querySelector('#connect-wallet .task-button');
            if (walletButton) {
                walletButton.addEventListener('click', function(e) {
                    // اگر wallet متصل است، dropdown را نمایش دهیم
                    if (walletButton.classList.contains('wallet-connected')) {
                        e.preventDefault();
                        toggleWalletDropdown();
                    } else {
                        // اگر wallet متصل نیست، عملیات connect را انجام دهیم
                        handleWalletConnection();
                    }
                });
            }

            // بستن dropdown وقتی خارج از آن کلیک می‌شود
            document.addEventListener('click', function(e) {
                const dropdown = document.querySelector('.wallet-dropdown-content');
                const walletBox = document.querySelector('#connect-wallet');
                
                if (dropdown && walletBox && !walletBox.contains(e.target)) {
                    dropdown.classList.remove('show');
                }
            });

            // Event listeners برای دکمه‌های Change و Disconnect
            document.addEventListener('click', function(e) {
                if (e.target.classList.contains('change-wallet-btn')) {
                    // تغییر wallet
                    handleWalletConnection();
                    document.querySelector('.wallet-dropdown-content')?.classList.remove('show');
                } else if (e.target.classList.contains('disconnect-btn')) {
                    // قطع اتصال wallet
                    disconnectWallet();
                    document.querySelector('.wallet-dropdown-content')?.classList.remove('show');
                }
            });
        });

        // Wallet connection functions
        async function handleWalletConnection() {
            if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
                // در Telegram Mini App
                const telegramId = window.Telegram.WebApp.initDataUnsafe?.user?.id;
                if (telegramId) {
                    const walletUrl = `/wallet/browser/connect?telegram_id=${telegramId}`;
                    window.Telegram.WebApp.openLink(walletUrl);
                }
            } else {
                // در مرورگر عادی - نمایش modal
                showPhantomModal();
            }
        }

        function showPhantomModal() {
            const modal = document.getElementById('phantom-modal');
            if (modal) {
                modal.classList.add('show');
            }
        }

        function hidePhantomModal() {
            const modal = document.getElementById('phantom-modal');
            if (modal) {
                modal.classList.remove('show');
            }
        }

        async function connectPhantomWallet() {
            try {
                if (!window.solana || !window.solana.isPhantom) {
                    showToast('Phantom wallet not detected. Please install Phantom wallet.', 'error');
                    return;
                }

                const response = await window.solana.connect();
                const walletAddress = response.publicKey.toString();
                
                // ارسال آدرس wallet به سرور
                const connectResponse = await fetch('/airdrop/connect_wallet', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        wallet: walletAddress
                    })
                });

                if (connectResponse.ok) {
                    // بروزرسانی UI
                    updateWalletUI(walletAddress, true);
                    showToast('Wallet connected successfully!', 'success');
                    hidePhantomModal();
                } else {
                    showToast('Failed to connect wallet. Please try again.', 'error');
                }
            } catch (error) {
                console.error('Error connecting wallet:', error);
                showToast('Failed to connect wallet. Please try again.', 'error');
            }
        }

        async function disconnectWallet() {
            try {
                const response = await fetch('/airdrop/connect_wallet', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        wallet: null // null برای disconnect
                    })
                });

                if (response.ok) {
                    // بروزرسانی UI
                    updateWalletUI('', false);
                    showToast('Wallet disconnected successfully', 'success');
                    
                    // Disconnect from Phantom if available
                    if (window.solana && window.solana.isConnected) {
                        await window.solana.disconnect();
                    }
                } else {
                    showToast('Failed to disconnect wallet', 'error');
                }
            } catch (error) {
                console.error('Error disconnecting wallet:', error);
                showToast('Failed to disconnect wallet', 'error');
            }
        }

        function updateWalletUI(address, connected) {
            const walletButton = document.querySelector('#connect-wallet .task-button');
            const walletText = document.querySelector('#wallet-button-text');
            const walletIcon = document.querySelector('#wallet-icon');
            const walletIndicator = document.querySelector('.wallet-status-indicator');
            
            if (walletButton && walletText && walletIcon) {
                if (connected && address) {
                    walletButton.classList.add('wallet-connected');
                    walletText.textContent = `${address.slice(0, 8)}...${address.slice(-4)}`;
                    walletIcon.className = 'fas fa-check right-icon';
                    if (walletIndicator) walletIndicator.classList.add('connected');
                    
                    // Add dropdown content if not exists
                    if (!document.querySelector('.wallet-dropdown-content')) {
                        const dropdown = document.createElement('div');
                        dropdown.className = 'wallet-dropdown-content';
                        dropdown.innerHTML = `
                            <div class="wallet-info-dropdown">
                                <div class="wallet-actions-dropdown">
                                    <button class="wallet-action-btn change-wallet-btn">
                                        <i class="fas fa-exchange-alt"></i>
                                        Change
                                    </button>
                                    <button class="wallet-action-btn disconnect-btn">
                                        <i class="fas fa-sign-out-alt"></i>
                                        Disconnect
                                    </button>
                                </div>
                            </div>
                        `;
                        document.querySelector('.wallet-dropdown').appendChild(dropdown);
                    }
                } else {
                    walletButton.classList.remove('wallet-connected');
                    walletText.textContent = 'Connect Wallet';
                    walletIcon.className = 'fas fa-chevron-right right-icon';
                    if (walletIndicator) walletIndicator.classList.remove('connected');
                    
                    // Remove dropdown content
                    const dropdown = document.querySelector('.wallet-dropdown-content');
                    if (dropdown) {
                        dropdown.remove();
                    }
                }
            }
            
            walletConnected = connected;
            currentWalletAddress = address;
        }

        // Task completion handler
        async function handleTaskCompletion() {
            try {
                window.location.href = '/earn';
            } catch (error) {
                console.error('Error navigating to tasks:', error);
                showToast('Failed to navigate to tasks page', 'error');
            }
        }

        // Invite check handler
        async function handleInviteCheck() {
            try {
                window.location.href = '/friends';
            } catch (error) {
                console.error('Error navigating to friends:', error);
                showToast('Failed to navigate to friends page', 'error');
            }
        }

        // Commission payment handler
        async function handleCommissionPayment() {
            if (!walletConnected) {
                showToast('Please connect your wallet first', 'error');
                return;
            }
            showCommissionModal();
        }

        function showCommissionModal() {
            const modal = document.getElementById('commission-modal');
            if (modal) {
                modal.classList.add('show');
            }
        }

        function closeCommissionModal() {
            const modal = document.getElementById('commission-modal');
            if (modal) {
                modal.classList.remove('show');
            }
        }

        async function payCommission() {
            try {
                if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
                    // در Telegram Mini App
                    const telegramId = window.Telegram.WebApp.initDataUnsafe?.user?.id;
                    if (telegramId) {
                        const commissionUrl = `/commission/browser/pay?telegram_id=${telegramId}`;
                        window.Telegram.WebApp.openLink(commissionUrl);
                    }
                } else {
                    // در مرورگر عادی - استفاده از Phantom
                    await payCommissionWithPhantom();
                }
                closeCommissionModal();
            } catch (error) {
                console.error('Error paying commission:', error);
                showToast('Failed to pay commission', 'error');
            }
        }

        async function payCommissionWithPhantom() {
            try {
                if (!window.solana || !window.solana.isPhantom) {
                    showToast('Phantom wallet not detected', 'error');
                    return;
                }

                if (!window.solana.isConnected) {
                    await window.solana.connect();
                }

                // Create transaction for 0.1 SOL commission
                const { SystemProgram, Transaction, LAMPORTS_PER_SOL } = window.solanaWeb3;
                
                const adminWallet = new window.solanaWeb3.PublicKey("{{ config.ADMIN_WALLET }}");
                const userWallet = window.solana.publicKey;
                
                const transaction = new Transaction().add(
                    SystemProgram.transfer({
                        fromPubkey: userWallet,
                        toPubkey: adminWallet,
                        lamports: 0.1 * LAMPORTS_PER_SOL // 0.1 SOL
                    })
                );

                const signature = await window.solana.signAndSendTransaction(transaction);
                
                // Update backend
                const response = await fetch('/commission/confirm', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        signature: signature.signature
                    })
                });

                if (response.ok) {
                    showToast('Commission paid successfully!', 'success');
                    // Update UI
                    const commissionButton = document.querySelector('#pay-commission .task-button');
                    const commissionIcon = document.querySelector('#commission-icon');
                    if (commissionButton && commissionIcon) {
                        commissionButton.classList.add('commission-paid');
                        commissionIcon.className = 'fas fa-check right-icon';
                    }
                } else {
                    showToast('Failed to confirm commission payment', 'error');
                }
            } catch (error) {
                console.error('Error paying commission:', error);
                showToast('Failed to pay commission', 'error');
            }
        }

        // Close modals when clicking outside
        document.addEventListener('click', function(e) {
            if (e.target.classList.contains('phantom-modal')) {
                hidePhantomModal();
            }
            if (e.target.classList.contains('commission-modal')) {
                closeCommissionModal();
            }
        });

        // Initialize Telegram WebApp
        if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
            window.Telegram.WebApp.ready();
            window.Telegram.WebApp.expand();
        }

        // Check wallet status on page load
        document.addEventListener('DOMContentLoaded', async function() {
            if (walletConnected && currentWalletAddress) {
                updateWalletUI(currentWalletAddress, true);
            }
        });

                function updateWalletUI(address, connected) {
            const walletButton = document.querySelector('#connect-wallet .task-button');
            const walletText = document.querySelector('#wallet-button-text');
            const walletIcon = document.querySelector('#wallet-icon');
            const walletIndicator = document.querySelector('.wallet-status-indicator');
            
            if (walletButton && walletText && walletIcon) {
                if (connected && address) {
                    walletButton.classList.add('wallet-connected');
                    walletText.textContent = `${address.slice(0, 8)}...${address.slice(-4)}`;
                    walletIcon.className = 'fas fa-check right-icon';
                    if (walletIndicator) walletIndicator.classList.add('connected');
                    
                    // Add dropdown content if not exists
                    if (!document.querySelector('.wallet-dropdown-content')) {
                        const dropdown = document.createElement('div');
                        dropdown.className = 'wallet-dropdown-content';
                        dropdown.innerHTML = `
                            <div class="wallet-info-dropdown">
                                <div class="wallet-actions-dropdown">
                                    <button class="wallet-action-btn change-wallet-btn">
                                        <i class="fas fa-exchange-alt"></i>
                                        Change
                                    </button>
                                    <button class="wallet-action-btn disconnect-btn">
                                        <i class="fas fa-sign-out-alt"></i>
                                        Disconnect
                                    </button>
                                </div>
                            </div>
                        `;
                        document.querySelector('.wallet-dropdown').appendChild(dropdown);
                    }
                } else {
                    walletButton.classList.remove('wallet-connected');
                    walletText.textContent = 'Connect Wallet';
                    walletIcon.className = 'fas fa-chevron-right right-icon';
                    if (walletIndicator) walletIndicator.classList.remove('connected');
                    
                    // Remove dropdown content
                    const dropdown = document.querySelector('.wallet-dropdown-content');
                    if (dropdown) {
                        dropdown.remove();
                    }
                }
            }
        }

        // Task completion handler
        async function handleTaskCompletion() {
            window.location.href = '/earn';
        }

        // Invite friends handler
        async function handleInviteCheck() {
            window.location.href = '/friends';
        }

        // Commission payment handler
        async function handleCommissionPayment() {
            const button = document.querySelector('#pay-commission .task-button');
            
            if (button.classList.contains('commission-paid')) {
                showToast('Commission already paid!', 'success');
                return;
            }

            if (!walletConnected) {
                showToast('Please connect your wallet first', 'error');
                return;
            }

            showCommissionModal();
        }

        function showCommissionModal() {
            const modal = document.getElementById('commission-modal');
            if (modal) {
                modal.classList.add('show');
            }
        }

        function closeCommissionModal() {
            const modal = document.getElementById('commission-modal');
            if (modal) {
                modal.classList.remove('show');
            }
        }

        async function payCommission() {
            try {
                if (!window.solana || !window.solana.isConnected) {
                    showToast('Please connect your Phantom wallet first', 'error');
                    return;
                }

                const button = document.querySelector('#pay-commission .task-button');
                button.classList.add('loading');

                // Create transaction for 0.1 SOL payment
                const connection = new solanaWeb3.Connection(
                    solanaWeb3.clusterApiUrl('devnet'),
                    'confirmed'
                );

                const fromPubkey = window.solana.publicKey;
                const toPubkey = new solanaWeb3.PublicKey('{{ config.ADMIN_WALLET }}');
                const lamports = 0.1 * solanaWeb3.LAMPORTS_PER_SOL; // 0.1 SOL

                const transaction = new solanaWeb3.Transaction().add(
                    solanaWeb3.SystemProgram.transfer({
                        fromPubkey,
                        toPubkey,
                        lamports
                    })
                );

                const { blockhash } = await connection.getRecentBlockhash();
                transaction.recentBlockhash = blockhash;
                transaction.feePayer = fromPubkey;

                // Sign and send transaction
                const signedTransaction = await window.solana.signTransaction(transaction);
                const txid = await connection.sendRawTransaction(signedTransaction.serialize());
                
                // Wait for confirmation
                await connection.confirmTransaction(txid);

                // Send transaction hash to server
                const response = await fetch('/airdrop/pay/commission', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        transaction_hash: txid
                    })
                });

                if (response.ok) {
                    button.classList.remove('loading');
                    button.classList.add('commission-paid');
                    const icon = document.querySelector('#commission-icon');
                    if (icon) {
                        icon.className = 'fas fa-check right-icon';
                    }
                    
                    showToast('Commission paid successfully!', 'success');
                    closeCommissionModal();
                    
                    // Check if all requirements are met
                    checkAllRequirements();
                } else {
                    throw new Error('Server error');
                }
            } catch (error) {
                console.error('Payment error:', error);
                showToast('Payment failed. Please try again.', 'error');
                document.querySelector('#pay-commission .task-button').classList.remove('loading');
            }
        }

        // Check all requirements
        async function checkAllRequirements() {
            try {
                const response = await fetch('/airdrop/check_all_status');
                if (response.ok) {
                    const data = await response.json();
                    
                    if (data.eligible) {
                        // Show congratulations message if not already shown
                        if (!document.querySelector('.congratulations-message')) {
                            const criteriaDiv = document.querySelector('.airdrop-criteria');
                            const congratsDiv = document.createElement('div');
                            congratsDiv.className = 'congratulations-message';
                            congratsDiv.innerHTML = `
                                <h3>🎉 Congratulations!</h3>
                                <p>You have completed all requirements for the CCoin airdrop. You will receive your tokens soon!</p>
                            `;
                            criteriaDiv.appendChild(congratsDiv);
                        }
                    }
                }
            } catch (error) {
                console.error('Error checking requirements:', error);
            }
        }

        // Initialize page
        document.addEventListener('DOMContentLoaded', function() {
            // Check requirements on page load
            checkAllRequirements();
        });

        // Close modals when clicking outside
        document.addEventListener('click', function(e) {
            if (e.target.classList.contains('phantom-modal')) {
                hidePhantomModal();
            }
            if (e.target.classList.contains('commission-modal')) {
                closeCommissionModal();
            }
        });

        // Initialize Telegram WebApp
        if (window.Telegram?.WebApp) {
            window.Telegram.WebApp.ready();
            window.Telegram.WebApp.expand();
        }
    </script>
