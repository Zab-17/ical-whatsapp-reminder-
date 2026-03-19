const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, makeCacheableSignalKeyStore, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const express = require('express');
const QRCode = require('qrcode');
const pino = require('pino');

const app = express();
app.use(express.json());

const PORT = process.env.BRIDGE_PORT || 3001;
const PYTHON_WEBHOOK_URL = process.env.PYTHON_WEBHOOK_URL || 'http://localhost:8000/webhook/whatsapp';
const AUTH_DIR = process.env.WA_SESSION_PATH || './auth_session';

const logger = pino({ level: 'warn' });

let sock = null;
let qrCode = null;
let isConnected = false;

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion();
    console.log('Using WA version:', version);

    sock = makeWASocket({
        version,
        auth: {
            creds: state.creds,
            keys: makeCacheableSignalKeyStore(state.keys, logger),
        },
        logger,
        syncFullHistory: false,
        markOnlineOnConnect: false,
    });

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            qrCode = qr;
            console.log('QR code received. Visit /qr to scan.');
        }

        if (connection === 'close') {
            isConnected = false;
            const statusCode = (lastDisconnect?.error)?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            console.log('Connection closed. Status:', statusCode, '| Reconnecting:', shouldReconnect);

            if (shouldReconnect) {
                console.log('Reconnecting in 5s...');
                setTimeout(connectToWhatsApp, 5000);
            } else {
                console.log('Logged out. Scan QR code again.');
                qrCode = null;
            }
        } else if (connection === 'open') {
            isConnected = true;
            qrCode = null;
            console.log('WhatsApp connected!');
        }
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('messages.upsert', async ({ messages, type }) => {
        if (type !== 'notify') return;

        for (const msg of messages) {
            if (msg.key.fromMe) continue;

            const text = msg.message?.conversation
                || msg.message?.extendedTextMessage?.text
                || '';
            if (!text) continue;

            // Extract phone number from JID (remove @s.whatsapp.net)
            const from = msg.key.remoteJid.replace('@s.whatsapp.net', '').replace('@lid', '');
            console.log(`Message from ${from}: ${text}`);

            try {
                await fetch(PYTHON_WEBHOOK_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ from, text }),
                });
            } catch (err) {
                console.error('Failed to forward to Python:', err.message);
            }
        }
    });
}

// REST API

app.get('/health', (req, res) => {
    res.json({ status: 'ok', connected: isConnected });
});

app.get('/qr', async (req, res) => {
    if (isConnected) return res.send('<h1>Already connected!</h1>');
    if (!qrCode) return res.send('<h1>Generating QR code... Refresh in a few seconds.</h1>');

    const qrImage = await QRCode.toDataURL(qrCode);
    res.send(`
        <html><body style="display:flex;justify-content:center;align-items:center;height:100vh;flex-direction:column;background:#111;color:#fff;font-family:sans-serif">
            <h2>Scan with WhatsApp</h2>
            <img src="${qrImage}" style="width:300px;height:300px;border-radius:12px"/>
            <p style="color:#888;margin-top:16px">WhatsApp > Linked Devices > Link a Device</p>
            <script>setTimeout(() => location.reload(), 15000)</script>
        </body></html>
    `);
});

app.post('/send', async (req, res) => {
    if (!isConnected || !sock) return res.status(503).json({ error: 'WhatsApp not connected' });

    const { to, message } = req.body;
    if (!to || !message) return res.status(400).json({ error: 'Missing to or message' });

    // Convert phone number to JID format
    // Strip any existing suffix first
    const phone = to.replace('@s.whatsapp.net', '').replace('@c.us', '').replace('@lid', '');
    const jid = `${phone}@s.whatsapp.net`;

    try {
        const result = await sock.sendMessage(jid, { text: message });
        res.json({ success: true, id: result?.key?.id || 'sent' });
    } catch (err) {
        console.error('Send error:', err.message);

        // If send fails, check if we're actually disconnected
        if (!isConnected) {
            return res.status(503).json({ error: 'WhatsApp disconnected during send' });
        }
        res.status(500).json({ error: err.message });
    }
});

// Endpoint to check if a number is on WhatsApp
app.post('/check-number', async (req, res) => {
    if (!isConnected || !sock) return res.status(503).json({ error: 'WhatsApp not connected' });

    const { phone } = req.body;
    if (!phone) return res.status(400).json({ error: 'Missing phone' });

    try {
        const [result] = await sock.onWhatsApp(phone);
        res.json({ exists: result?.exists || false, jid: result?.jid || null });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.listen(PORT, () => {
    console.log(`WhatsApp bridge (Baileys) running on port ${PORT}`);
    console.log(`Auth dir: ${AUTH_DIR}`);
    connectToWhatsApp().catch(err => {
        console.error('Failed to connect:', err.message);
        console.log('Retrying in 10s...');
        setTimeout(() => connectToWhatsApp().catch(e => console.error('Retry failed:', e.message)), 10000);
    });
});
