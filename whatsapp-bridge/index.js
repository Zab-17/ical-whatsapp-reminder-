const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const QRCode = require('qrcode');

const app = express();
app.use(express.json());

const PORT = process.env.BRIDGE_PORT || 3001;
const PYTHON_WEBHOOK_URL = process.env.PYTHON_WEBHOOK_URL || 'http://localhost:8000/webhook/whatsapp';

let qrCode = null;
let isConnected = false;

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: process.env.WA_SESSION_PATH || './auth_session' }),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
    },
});

client.on('qr', (qr) => {
    qrCode = qr;
    console.log('QR code received. Visit /qr to scan.');
});

client.on('ready', () => {
    isConnected = true;
    qrCode = null;
    console.log('WhatsApp connected!');
});

client.on('disconnected', () => {
    isConnected = false;
    console.log('WhatsApp disconnected. Restarting...');
    client.initialize();
});

client.on('message', async (msg) => {
    if (msg.fromMe) return;

    const from = msg.from.replace('@c.us', '');
    const text = msg.body;

    if (!text) return;
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
});

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
            <p style="color:#888;margin-top:16px">WhatsApp → Linked Devices → Link a Device</p>
            <script>setTimeout(() => location.reload(), 15000)</script>
        </body></html>
    `);
});

app.post('/send', async (req, res) => {
    if (!isConnected) return res.status(503).json({ error: 'WhatsApp not connected' });

    const { to, message } = req.body;
    if (!to || !message) return res.status(400).json({ error: 'Missing to or message' });

    const chatId = to.includes('@') ? to : `${to}@c.us`;

    try {
        const result = await client.sendMessage(chatId, message);
        res.json({ success: true, id: result.id.id });
    } catch (err) {
        console.error('Send error:', err);
        res.status(500).json({ error: err.message });
    }
});

app.listen(PORT, () => {
    console.log(`WhatsApp bridge running on port ${PORT}`);
    client.initialize();
});
