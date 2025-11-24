/**
 * Phantom Deep Links Integration
 * Official Phantom v1 API Implementation
 * https://docs.phantom.app/developer-powertools/deeplinks-ios-and-android
 */

const PhantomDeepLinks = {
    /**
     * Generate ephemeral keypair for encryption
     */
    generateKeypair() {
        if (typeof nacl === 'undefined') {
            throw new Error('TweetNaCl library not loaded');
        }
        const keypair = nacl.box.keyPair();
        return {
            publicKey: keypair.publicKey,
            secretKey: keypair.secretKey
        };
    },

    /**
     * Create shared secret for encryption
     */
    createSharedSecret(phantomPublicKeyBase58, dappSecretKey) {
        const phantomPublicKey = bs58.decode(phantomPublicKeyBase58);
        return nacl.box.before(phantomPublicKey, dappSecretKey);
    },

    /**
     * Encrypt payload for Phantom
     */
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

    /**
     * Decrypt response from Phantom
     */
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

    /**
     * Build Phantom connect URL
     */
    buildConnectUrl(dappPublicKey, redirectUrl, cluster = 'mainnet-beta') {
        const params = new URLSearchParams({
            dapp_encryption_public_key: bs58.encode(dappPublicKey),
            cluster: cluster,
            app_url: window.location.origin,
            redirect_link: redirectUrl
        });

        return `https://phantom.app/ul/v1/connect?${params.toString()}`;
    },

    /**
     * Build Phantom signAndSendTransaction URL
     */
    buildSignAndSendUrl(dappPublicKey, transaction, redirectUrl, cluster = 'mainnet-beta') {
        const params = new URLSearchParams({
            dapp_encryption_public_key: bs58.encode(dappPublicKey),
            cluster: cluster,
            app_url: window.location.origin,
            redirect_link: redirectUrl,
            // Transaction will be encrypted and added separately
        });

        return `https://phantom.app/ul/v1/signAndSendTransaction?${params.toString()}`;
    },

    /**
     * Open URL with Telegram WebApp support
     */
    openUrl(url) {
        console.log('Opening URL:', url);
        
        // Try Telegram WebApp first
        if (window.Telegram?.WebApp?.openLink) {
            console.log('Using Telegram WebApp openLink');
            window.Telegram.WebApp.openLink(url);
        } else {
            console.log('Fallback to window.location');
            window.location.href = url;
        }
    },

    /**
     * Store keypair in localStorage
     */
    storeKeypair(publicKey, secretKey) {
        localStorage.setItem('phantom_dapp_public_key', bs58.encode(publicKey));
        localStorage.setItem('phantom_dapp_secret_key', bs58.encode(secretKey));
    },

    /**
     * Retrieve keypair from localStorage
     */
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

    /**
     * Store session data
     */
    storeSession(sessionId, data) {
        localStorage.setItem('phantom_session_id', sessionId);
        localStorage.setItem('phantom_session_data', JSON.stringify(data));
        localStorage.setItem('phantom_session_timestamp', Date.now().toString());
    },

    /**
     * Retrieve session data
     */
    retrieveSession() {
        const sessionId = localStorage.getItem('phantom_session_id');
        const dataStr = localStorage.getItem('phantom_session_data');
        const timestamp = localStorage.getItem('phantom_session_timestamp');
        
        if (!sessionId || !dataStr || !timestamp) {
            return null;
        }

        // Check if session expired (5 minutes)
        const now = Date.now();
        const sessionTime = parseInt(timestamp);
        if (now - sessionTime > 300000) {
            this.clearSession();
            return null;
        }
        
        return {
            sessionId,
            data: JSON.parse(dataStr),
            timestamp: parseInt(timestamp)
        };
    },

    /**
     * Clear session data
     */
    clearSession() {
        localStorage.removeItem('phantom_session_id');
        localStorage.removeItem('phantom_session_data');
        localStorage.removeItem('phantom_session_timestamp');
        localStorage.removeItem('phantom_dapp_public_key');
        localStorage.removeItem('phantom_dapp_secret_key');
        localStorage.removeItem('ccoin_payment_initiated');
    },

    /**
     * Parse URL parameters
     */
    parseUrlParams() {
        const params = new URLSearchParams(window.location.search);
        return {
            errorCode: params.get('errorCode'),
            errorMessage: params.get('errorMessage'),
            phantom_encryption_public_key: params.get('phantom_encryption_public_key'),
            nonce: params.get('nonce'),
            data: params.get('data')
        };
    }
};

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PhantomDeepLinks;
}
