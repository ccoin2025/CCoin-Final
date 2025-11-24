// Phantom Deep Links Utility Functions
// Based on official Phantom documentation

const PhantomUtils = {
    // Generate ephemeral keypair for encryption
    generateKeypair() {
        const keypair = nacl.box.keyPair();
        return {
            publicKey: keypair.publicKey,
            secretKey: keypair.secretKey
        };
    },

    // Encrypt payload for Phantom
    encryptPayload(payload, sharedSecret) {
        const nonce = nacl.randomBytes(24);
        const message = JSON.stringify(payload);
        const messageBytes = new TextEncoder().encode(message);
        
        const encrypted = nacl.box.after(messageBytes, nonce, sharedSecret);
        
        return {
            nonce: bs58.encode(nonce),
            encryptedPayload: bs58.encode(encrypted)
        };
    },

    // Decrypt payload from Phantom
    decryptPayload(encryptedData, nonce, sharedSecret) {
        const decryptedData = nacl.box.open.after(
            bs58.decode(encryptedData),
            bs58.decode(nonce),
            sharedSecret
        );
        
        if (!decryptedData) {
            throw new Error('Failed to decrypt payload');
        }
        
        const message = new TextDecoder().decode(decryptedData);
        return JSON.parse(message);
    },

    // Create shared secret
    createSharedSecret(phantomPublicKey, dappSecretKey) {
        return nacl.box.before(
            bs58.decode(phantomPublicKey),
            dappSecretKey
        );
    },

    // Build Phantom connect URL
    buildConnectUrl(dappPublicKey, redirectUrl, cluster = 'mainnet-beta') {
        const params = new URLSearchParams({
            dapp_encryption_public_key: bs58.encode(dappPublicKey),
            cluster: cluster,
            app_url: window.location.origin,
            redirect_link: redirectUrl
        });

        return `https://phantom.app/ul/v1/connect?${params.toString()}`;
    },

    // Build Phantom signAndSendTransaction URL
    buildSignAndSendUrl(dappPublicKey, payload, nonce, redirectUrl) {
        const params = new URLSearchParams({
            dapp_encryption_public_key: bs58.encode(dappPublicKey),
            nonce: nonce,
            redirect_link: redirectUrl,
            payload: payload
        });

        return `https://phantom.app/ul/v1/signAndSendTransaction?${params.toString()}`;
    },

    // Open URL with Telegram support
    openUrl(url) {
        if (window.Telegram?.WebApp?.openLink) {
            window.Telegram.WebApp.openLink(url);
        } else {
            window.location.href = url;
        }
    },

    // Store keypair in localStorage
    storeKeypair(publicKey, secretKey) {
        localStorage.setItem('phantom_dapp_public_key', bs58.encode(publicKey));
        localStorage.setItem('phantom_dapp_secret_key', bs58.encode(secretKey));
    },

    // Retrieve keypair from localStorage
    retrieveKeypair() {
        const publicKey = localStorage.getItem('phantom_dapp_public_key');
        const secretKey = localStorage.getItem('phantom_dapp_secret_key');
        
        if (!publicKey || !secretKey) {
            return null;
        }
        
        return {
            publicKey: bs58.decode(publicKey),
            secretKey: bs58.decode(secretKey)
        };
    },

    // Store session
    storeSession(session, phantomPublicKey, walletPublicKey) {
        localStorage.setItem('phantom_session', session);
        localStorage.setItem('phantom_public_key', phantomPublicKey);
        localStorage.setItem('phantom_wallet_address', walletPublicKey);
    },

    // Retrieve session
    retrieveSession() {
        return {
            session: localStorage.getItem('phantom_session'),
            phantomPublicKey: localStorage.getItem('phantom_public_key'),
            walletAddress: localStorage.getItem('phantom_wallet_address')
        };
    },

    // Clear session
    clearSession() {
        localStorage.removeItem('phantom_session');
        localStorage.removeItem('phantom_public_key');
        localStorage.removeItem('phantom_wallet_address');
        localStorage.removeItem('phantom_dapp_public_key');
        localStorage.removeItem('phantom_dapp_secret_key');
    }
};

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PhantomUtils;
}
