"""Login web page for Canvas registration."""
from __future__ import annotations

import logging
import secrets
import threading

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.database import add_user

logger = logging.getLogger(__name__)
router = APIRouter()

_pending: dict[str, str] = {}
_completed: dict[str, bool] = {}
_errors: dict[str, str] = {}

LANDING_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Canvas Reminder — AUC</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --navy: #041631;
            --navy-light: #0a2249;
            --crimson: #c41230;
            --crimson-glow: #e8153a;
            --gold: #d4a843;
            --surface: #0c1e3d;
            --surface-2: #122952;
            --text: #e8edf5;
            --text-muted: #7b8fad;
            --text-dim: #4a5f80;
            --radius: 14px;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Outfit', sans-serif;
            background: var(--navy);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }

        /* Animated background */
        .bg {
            position: fixed; inset: 0; z-index: 0; overflow: hidden;
        }
        .bg .orb {
            position: absolute;
            border-radius: 50%;
            filter: blur(120px);
            opacity: 0.35;
            animation: drift 20s ease-in-out infinite alternate;
        }
        .bg .orb:nth-child(1) {
            width: 600px; height: 600px;
            background: var(--crimson);
            top: -200px; right: -150px;
            animation-duration: 25s;
        }
        .bg .orb:nth-child(2) {
            width: 500px; height: 500px;
            background: #1a3a7a;
            bottom: -200px; left: -100px;
            animation-duration: 30s;
            animation-delay: -5s;
        }
        .bg .orb:nth-child(3) {
            width: 300px; height: 300px;
            background: var(--gold);
            top: 50%; left: 50%;
            opacity: 0.12;
            animation-duration: 22s;
            animation-delay: -10s;
        }
        @keyframes drift {
            0% { transform: translate(0, 0) scale(1); }
            33% { transform: translate(40px, -30px) scale(1.05); }
            66% { transform: translate(-20px, 20px) scale(0.95); }
            100% { transform: translate(30px, -40px) scale(1.02); }
        }

        /* Noise overlay */
        .bg::after {
            content: '';
            position: absolute; inset: 0;
            background: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E");
            opacity: 0.4;
            pointer-events: none;
        }

        /* Grid lines */
        .grid-lines {
            position: fixed; inset: 0; z-index: 0;
            background-image:
                linear-gradient(rgba(196,18,48,0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(196,18,48,0.03) 1px, transparent 1px);
            background-size: 60px 60px;
            mask-image: radial-gradient(ellipse at center, black 30%, transparent 70%);
        }

        .container {
            position: relative; z-index: 1;
            width: 100%; max-width: 440px;
            padding: 20px;
            animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) both;
        }

        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Card */
        .card {
            background: linear-gradient(165deg, rgba(12,30,61,0.9), rgba(4,22,49,0.95));
            border: 1px solid rgba(196,18,48,0.15);
            border-radius: 24px;
            padding: 44px 36px;
            backdrop-filter: blur(40px);
            box-shadow:
                0 0 0 1px rgba(255,255,255,0.03),
                0 30px 60px -20px rgba(0,0,0,0.5),
                0 0 100px -40px rgba(196,18,48,0.2);
        }

        /* Brand header */
        .brand {
            text-align: center;
            margin-bottom: 36px;
        }
        .brand-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            background: rgba(196,18,48,0.1);
            border: 1px solid rgba(196,18,48,0.2);
            border-radius: 100px;
            font-size: 11px;
            font-weight: 500;
            color: var(--crimson-glow);
            letter-spacing: 1.5px;
            text-transform: uppercase;
            margin-bottom: 20px;
            animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both;
        }
        .brand-badge::before {
            content: '';
            width: 6px; height: 6px;
            background: var(--crimson-glow);
            border-radius: 50%;
            animation: pulse-dot 2s ease-in-out infinite;
        }
        @keyframes pulse-dot {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(0.8); }
        }
        .brand h1 {
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #fff 0%, var(--text-muted) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.15s both;
        }
        .brand p {
            color: var(--text-dim);
            font-size: 14px;
            margin-top: 6px;
            font-weight: 300;
            animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.2s both;
        }

        /* Steps */
        .step { display: none; }
        .step.active { display: block; animation: fadeUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) both; }

        /* Form elements */
        .field { margin-bottom: 18px; }
        .field label {
            display: block;
            font-size: 12px;
            font-weight: 500;
            color: var(--text-muted);
            margin-bottom: 8px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }
        .field input {
            width: 100%;
            padding: 14px 16px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: var(--radius);
            color: var(--text);
            font-family: 'JetBrains Mono', monospace;
            font-size: 15px;
            outline: none;
            transition: all 0.3s ease;
        }
        .field input::placeholder { color: var(--text-dim); font-family: 'Outfit', sans-serif; }
        .field input:focus {
            border-color: var(--crimson);
            background: rgba(196,18,48,0.04);
            box-shadow: 0 0 0 3px rgba(196,18,48,0.1);
        }

        .hint-box {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 12px 14px;
            background: rgba(212,168,67,0.06);
            border: 1px solid rgba(212,168,67,0.12);
            border-radius: 10px;
            margin-bottom: 24px;
        }
        .hint-box span { font-size: 14px; flex-shrink: 0; margin-top: 1px; }
        .hint-box p { font-size: 12px; color: var(--text-muted); line-height: 1.5; }

        /* Button */
        .btn {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            width: 100%;
            padding: 15px 20px;
            background: linear-gradient(135deg, var(--crimson) 0%, #a00e28 100%);
            color: #fff;
            border: none;
            border-radius: var(--radius);
            font-family: 'Outfit', sans-serif;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            letter-spacing: 0.3px;
        }
        .btn::before {
            content: '';
            position: absolute; inset: 0;
            background: linear-gradient(135deg, transparent 0%, rgba(255,255,255,0.1) 100%);
            opacity: 0;
            transition: opacity 0.3s;
        }
        .btn:hover::before { opacity: 1; }
        .btn:hover { transform: translateY(-1px); box-shadow: 0 8px 30px -8px rgba(196,18,48,0.5); }
        .btn:active { transform: translateY(0); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .btn svg { width: 18px; height: 18px; }

        /* Features */
        .features {
            margin-top: 28px;
            padding-top: 24px;
            border-top: 1px solid rgba(255,255,255,0.06);
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        .feature {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 12px;
            background: rgba(255,255,255,0.02);
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.04);
            transition: all 0.3s;
        }
        .feature:hover { background: rgba(255,255,255,0.04); border-color: rgba(255,255,255,0.08); }
        .feature-icon {
            width: 32px; height: 32px;
            display: flex; align-items: center; justify-content: center;
            background: rgba(196,18,48,0.1);
            border-radius: 8px;
            font-size: 14px;
            flex-shrink: 0;
        }
        .feature span { font-size: 12px; color: var(--text-muted); line-height: 1.3; }

        /* Loading state */
        .loader-ring {
            width: 56px; height: 56px;
            border: 3px solid rgba(255,255,255,0.06);
            border-top-color: var(--crimson-glow);
            border-radius: 50%;
            animation: spin 1s cubic-bezier(0.5, 0, 0.5, 1) infinite;
            margin: 0 auto 24px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .loading-text {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .loading-sub {
            color: var(--text-dim);
            font-size: 13px;
            font-weight: 300;
        }
        .loading-steps {
            margin-top: 28px;
            text-align: left;
        }
        .loading-step {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px 0;
            font-size: 13px;
            color: var(--text-dim);
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }
        .loading-step:last-child { border-bottom: none; }
        .loading-step .num {
            width: 24px; height: 24px;
            display: flex; align-items: center; justify-content: center;
            background: rgba(255,255,255,0.05);
            border-radius: 6px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            flex-shrink: 0;
        }
        .loading-step.active { color: var(--text); }
        .loading-step.active .num { background: rgba(196,18,48,0.2); color: var(--crimson-glow); }
        .loading-step.done { color: var(--text-muted); }
        .loading-step.done .num { background: rgba(34,197,94,0.15); color: #22c55e; }

        /* Success */
        .success-check {
            width: 72px; height: 72px;
            margin: 0 auto 24px;
            background: rgba(34,197,94,0.1);
            border: 2px solid rgba(34,197,94,0.3);
            border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            animation: pop 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        @keyframes pop {
            from { transform: scale(0); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
        }
        .success-check svg { width: 32px; height: 32px; color: #22c55e; }
        .success-title {
            font-size: 22px;
            font-weight: 700;
            margin-bottom: 8px;
            background: linear-gradient(135deg, #22c55e, #4ade80);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .success-msg { color: var(--text-muted); font-size: 14px; line-height: 1.6; font-weight: 300; }
        .success-card {
            margin-top: 24px;
            padding: 16px;
            background: rgba(34,197,94,0.06);
            border: 1px solid rgba(34,197,94,0.15);
            border-radius: 12px;
        }
        .success-card p { font-size: 13px; color: var(--text-muted); }
        .success-card strong { color: var(--text); font-weight: 500; }

        .error-msg {
            display: none;
            margin-top: 16px;
            padding: 12px 16px;
            background: rgba(248,113,113,0.08);
            border: 1px solid rgba(248,113,113,0.2);
            border-radius: 10px;
            color: #f87171;
            font-size: 13px;
        }

        /* Footer */
        .footer {
            text-align: center;
            margin-top: 20px;
            font-size: 11px;
            color: var(--text-dim);
            animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.4s both;
        }
        .footer a { color: var(--text-muted); text-decoration: none; }
    </style>
</head>
<body>
    <div class="bg">
        <div class="orb"></div>
        <div class="orb"></div>
        <div class="orb"></div>
    </div>
    <div class="grid-lines"></div>

    <div class="container">
        <div class="card">
            <div class="brand">
                <div class="brand-badge">AUC Canvas</div>
                <h1>Canvas Reminder</h1>
                <p>Never miss an assignment again</p>
            </div>

            <!-- Step 1 -->
            <div id="step1" class="step active">
                    <div class="field">
                        <label>Your Name</label>
                        <input type="text" id="name" placeholder="Zeyad" required autocomplete="given-name">
                    </div>
                    <div class="field">
                        <label>WhatsApp Number</label>
                        <input type="tel" id="phone" placeholder="201XXXXXXXXX" required inputmode="numeric" autocomplete="tel">
                    </div>
                    <div class="hint-box">
                        <span>💡</span>
                        <p>Enter with country code, no + or spaces.</p>
                    </div>
                    <button class="btn" onclick="goToStep2()">
                        Next
                        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6"/></svg>
                    </button>

                <div class="features">
                    <div class="feature">
                        <div class="feature-icon">📅</div>
                        <span>4x daily reminders</span>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">🔔</div>
                        <span>New upload alerts</span>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">📖</div>
                        <span>Browse courses</span>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">💬</div>
                        <span>WhatsApp chatbot</span>
                    </div>
                </div>
            </div>

            <!-- Step 2: Login to Canvas + Bookmarklet -->
            <div id="step2" class="step">
                <h2 style="font-size:18px;font-weight:600;margin-bottom:16px">Connect your Canvas</h2>
                <div class="hint-box">
                    <span>1️⃣</span>
                    <p>Click the button below to open Canvas. Log in normally with your AUC account.</p>
                </div>
                <a href="https://aucegypt.instructure.com" target="_blank" class="btn" style="margin-bottom:16px;text-decoration:none">
                    Open Canvas Login
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                </a>
                <div class="hint-box">
                    <span>2️⃣</span>
                    <p>Enter your AUC credentials below. They're used <strong>once</strong> to log in and <strong>never stored</strong>.</p>
                </div>
                <div class="field">
                    <label>AUC Email</label>
                    <input type="email" id="email" placeholder="you@aucegypt.edu" autocomplete="email">
                </div>
                <div class="field">
                    <label>Password</label>
                    <input type="password" id="password" placeholder="Your AUC password">
                </div>
                <div class="hint-box">
                    <span>📱</span>
                    <p>After clicking Connect, approve the <strong>2FA request</strong> on your Microsoft Authenticator app.</p>
                </div>
                <button class="btn" onclick="captureSession()" id="captureBtn" style="background:linear-gradient(135deg,#059669,#047857)">
                    Connect Canvas
                </button>
                <div id="captureError" style="display:none;margin-top:12px;padding:12px;background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.2);border-radius:10px;color:#f87171;font-size:13px"></div>
            </div>

            <!-- Step 3: Success -->
            <div id="step3" class="step" style="text-align:center">
                <div class="success-check" style="width:72px;height:72px;margin:0 auto 24px;background:rgba(34,197,94,0.1);border:2px solid rgba(34,197,94,0.3);border-radius:50%;display:flex;align-items:center;justify-content:center">
                    <span style="font-size:28px;color:#22c55e">✓</span>
                </div>
                <div style="font-size:22px;font-weight:700;background:linear-gradient(135deg,#22c55e,#4ade80);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px">You're all set!</div>
                <p style="color:var(--text-muted);font-size:14px;line-height:1.6">Send <strong style="color:#fff">hi</strong> on WhatsApp to start.<br>Reminders at 10am, 1pm, 5pm & 9pm.</p>
            </div>
        </div>
        <div class="footer">Built for AUC students</div>
    </div>
    <script>
        let userName = '', userPhone = '';

        function goToStep2() {
            userName = document.getElementById('name').value.trim();
            userPhone = document.getElementById('phone').value.replace(/[\s+\-]/g, '').trim();
            if (!userName) return alert('Please enter your name');
            if (!userPhone || userPhone.length < 10) return alert('Please enter a valid phone number');
            document.getElementById('step1').classList.remove('active');
            document.getElementById('step2').classList.add('active');
        }

        async function captureSession() {
            const btn = document.getElementById('captureBtn');
            const errDiv = document.getElementById('captureError');
            btn.textContent = 'Connecting...';
            btn.disabled = true;
            errDiv.style.display = 'none';

            try {
                // Open Canvas in a hidden iframe to check if user is logged in
                // Then use our server to capture cookies via Playwright
                const email = document.getElementById('email').value.trim();
                const password = document.getElementById('password').value;
                if (!email || !password) {
                    errDiv.textContent = 'Please enter your email and password.';
                    errDiv.style.display = 'block';
                    btn.textContent = 'Connect Canvas';
                    btn.disabled = false;
                    return;
                }
                btn.textContent = 'Waiting for 2FA approval...';
                const r = await fetch('/api/capture-session', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ phone: userPhone, name: userName, email, password }),
                });
                const data = await r.json();
                if (data.success) {
                    document.getElementById('step2').classList.remove('active');
                    document.getElementById('step3').classList.add('active');
                } else {
                    errDiv.textContent = data.error || 'Failed to connect. Make sure you are logged into Canvas first.';
                    errDiv.style.display = 'block';
                    btn.textContent = "I'm logged in — Connect Now";
                    btn.disabled = false;
                }
            } catch(e) {
                errDiv.textContent = 'Connection error. Try again.';
                errDiv.style.display = 'block';
                btn.textContent = "I'm logged in — Connect Now";
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>
"""

CALLBACK_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Connecting Canvas...</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --navy: #041631;
            --crimson: #c41230;
            --crimson-glow: #e8153a;
            --surface: #0c1e3d;
            --text: #e8edf5;
            --text-muted: #7b8fad;
            --text-dim: #4a5f80;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Outfit', sans-serif;
            background: var(--navy);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }
        .bg { position: fixed; inset: 0; z-index: 0; }
        .bg .orb {
            position: absolute; border-radius: 50%; filter: blur(120px); opacity: 0.35;
            animation: drift 20s ease-in-out infinite alternate;
        }
        .bg .orb:nth-child(1) { width: 600px; height: 600px; background: var(--crimson); top: -200px; right: -150px; }
        .bg .orb:nth-child(2) { width: 500px; height: 500px; background: #1a3a7a; bottom: -200px; left: -100px; animation-duration: 30s; }
        @keyframes drift {
            0% { transform: translate(0,0) scale(1); }
            50% { transform: translate(30px,-20px) scale(1.03); }
            100% { transform: translate(-20px,30px) scale(0.97); }
        }
        .container {
            position: relative; z-index: 1;
            width: 100%; max-width: 440px; padding: 20px;
            animation: fadeUp 0.6s cubic-bezier(0.16,1,0.3,1) both;
        }
        @keyframes fadeUp { from { opacity:0; transform:translateY(20px); } to { opacity:1; transform:translateY(0); } }
        .card {
            background: linear-gradient(165deg, rgba(12,30,61,0.9), rgba(4,22,49,0.95));
            border: 1px solid rgba(196,18,48,0.15);
            border-radius: 24px;
            padding: 44px 36px;
            backdrop-filter: blur(40px);
            box-shadow: 0 30px 60px -20px rgba(0,0,0,0.5);
            text-align: center;
        }
        .step { display: none; }
        .step.active { display: block; animation: fadeUp 0.5s cubic-bezier(0.16,1,0.3,1) both; }

        .loader-ring {
            width: 56px; height: 56px;
            border: 3px solid rgba(255,255,255,0.06);
            border-top-color: var(--crimson-glow);
            border-radius: 50%;
            animation: spin 1s cubic-bezier(0.5,0,0.5,1) infinite;
            margin: 0 auto 24px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        h2 { font-size: 20px; font-weight: 600; margin-bottom: 8px; }
        .sub { color: var(--text-dim); font-size: 13px; font-weight: 300; }

        .steps-list { margin-top: 28px; text-align: left; }
        .s-step {
            display: flex; align-items: center; gap: 12px;
            padding: 10px 0; font-size: 13px; color: var(--text-dim);
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }
        .s-step:last-child { border: none; }
        .s-step .dot {
            width: 8px; height: 8px; border-radius: 50%;
            background: rgba(255,255,255,0.1); flex-shrink: 0;
        }
        .s-step.active { color: var(--text); }
        .s-step.active .dot { background: var(--crimson-glow); box-shadow: 0 0 8px rgba(196,18,48,0.5); }
        .s-step.done { color: var(--text-muted); }
        .s-step.done .dot { background: #22c55e; }

        .success-check {
            width: 72px; height: 72px; margin: 0 auto 24px;
            background: rgba(34,197,94,0.1); border: 2px solid rgba(34,197,94,0.3);
            border-radius: 50%; display: flex; align-items: center; justify-content: center;
            animation: pop 0.5s cubic-bezier(0.16,1,0.3,1) both;
        }
        @keyframes pop { from { transform:scale(0); } to { transform:scale(1); } }
        .success-check::after { content: '✓'; font-size: 28px; color: #22c55e; }

        .success-title {
            font-size: 22px; font-weight: 700;
            background: linear-gradient(135deg, #22c55e, #4ade80);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .success-msg { color: var(--text-muted); font-size: 14px; margin-top: 8px; line-height: 1.6; font-weight: 300; }
        .success-box {
            margin-top: 24px; padding: 16px;
            background: rgba(34,197,94,0.06); border: 1px solid rgba(34,197,94,0.15);
            border-radius: 12px; font-size: 13px; color: var(--text-muted);
        }

        .error-box {
            display: none; margin-top: 20px; padding: 14px 16px;
            background: rgba(248,113,113,0.08); border: 1px solid rgba(248,113,113,0.2);
            border-radius: 12px; color: #f87171; font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="bg"><div class="orb"></div><div class="orb"></div></div>
    <div class="container">
        <div class="card">
            <!-- Loading -->
            <div id="loading" class="step active">
                <div class="loader-ring"></div>
                <h2>Connecting to Canvas</h2>
                <p class="sub">Complete the login in the browser window that opened</p>
                <div class="steps-list">
                    <div class="s-step active" id="s1"><div class="dot"></div>Login with your AUC email</div>
                    <div class="s-step" id="s2"><div class="dot"></div>Enter your password</div>
                    <div class="s-step" id="s3"><div class="dot"></div>Approve 2FA on your phone</div>
                    <div class="s-step" id="s4"><div class="dot"></div>Session captured</div>
                </div>
            </div>

            <!-- Success -->
            <div id="success" class="step">
                <div class="success-check"></div>
                <div class="success-title">You're all set!</div>
                <p class="success-msg">Your Canvas account is connected.<br>Assignment reminders are now active.</p>
                <div class="success-box">
                    Send <strong style="color:#fff">hi</strong> on WhatsApp to see the menu.<br>
                    Reminders at <strong style="color:#fff">10am, 1pm, 5pm & 9pm</strong>.
                </div>
            </div>

            <div id="error" class="error-box"></div>
        </div>
    </div>
    <script>
        let step = 1;
        function advanceStep() {
            if (step < 4) {
                document.getElementById('s'+step).classList.remove('active');
                document.getElementById('s'+step).classList.add('done');
                step++;
                document.getElementById('s'+step).classList.add('active');
            }
        }
        // Simulate step progression while waiting
        setTimeout(() => advanceStep(), 4000);
        setTimeout(() => advanceStep(), 10000);

        async function poll() {
            for (let i = 0; i < 60; i++) {
                try {
                    const r = await fetch('/api/complete-login?token=TOKEN_PLACEHOLDER');
                    const data = await r.json();
                    if (data.success) {
                        // Mark all steps done
                        for (let j = 1; j <= 4; j++) {
                            document.getElementById('s'+j).classList.remove('active');
                            document.getElementById('s'+j).classList.add('done');
                        }
                        await new Promise(r => setTimeout(r, 500));
                        document.getElementById('loading').classList.remove('active');
                        document.getElementById('success').classList.add('active');
                        return;
                    }
                    if (data.error && data.error !== 'still_processing') {
                        document.getElementById('loading').classList.remove('active');
                        document.getElementById('error').style.display = 'block';
                        document.getElementById('error').textContent = data.error;
                        return;
                    }
                } catch(e) {}
                await new Promise(r => setTimeout(r, 3000));
            }
            document.getElementById('loading').classList.remove('active');
            document.getElementById('error').style.display = 'block';
            document.getElementById('error').textContent = 'Timed out. Please try again.';
        }
        poll();
    </script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
@router.get("/login", response_class=HTMLResponse)
async def login_page():
    return LANDING_HTML


@router.post("/start-login")
async def start_login(request: Request):
    form = await request.form()
    phone = str(form.get("phone", "")).replace(" ", "").replace("+", "").replace("-", "").strip()
    name = str(form.get("name", "")).strip()
    email = str(form.get("email", "")).strip()
    password = str(form.get("password", ""))

    if not phone or len(phone) < 10:
        return HTMLResponse("<h1>Invalid phone number. <a href='/login'>Go back</a></h1>")
    if not name:
        return HTMLResponse("<h1>Please enter your name. <a href='/login'>Go back</a></h1>")
    if not email or not password:
        return HTMLResponse("<h1>Email and password are required. <a href='/login'>Go back</a></h1>")

    token = secrets.token_urlsafe(32)
    _pending[token] = {"phone": phone, "name": name}

    thread = threading.Thread(target=_do_login_sync, args=(token, phone, name, email, password), daemon=True)
    thread.start()

    callback_html = CALLBACK_HTML.replace("TOKEN_PLACEHOLDER", token)
    return HTMLResponse(callback_html)


@router.get("/api/complete-login")
async def complete_login(token: str = ""):
    if token in _errors:
        error = _errors.pop(token)
        _pending.pop(token, None)
        return {"success": False, "error": error}

    if token in _completed:
        _completed.pop(token)
        _pending.pop(token, None)
        return {"success": True}

    return {"success": False, "error": "still_processing"}


@router.post("/api/capture-session")
async def capture_session(request: Request):
    body = await request.json()
    phone = body.get("phone", "").replace(" ", "").replace("+", "").strip()
    name = body.get("name", "").strip()
    email = body.get("email", "").strip()
    password = body.get("password", "")

    if not phone or not email or not password:
        return {"success": False, "error": "All fields are required"}

    try:
        from src.auth import login_and_get_cookies
        cookies = login_and_get_cookies(email, password)
        add_user(phone, cookies, name=name)
        logger.info("User %s (%s) registered", phone, name)

        try:
            from src import whatsapp_service
            greeting = f"Hey {name}! " if name else ""
            whatsapp_service.send_text(
                f"✅ *{greeting}Canvas Reminder is set up!*\n\n"
                "You'll receive assignment reminders at 10am, 1pm, 5pm & 9pm.\n\n"
                "Send *hi* to see the menu.",
                to=phone,
            )
        except Exception as we:
            logger.warning("Failed to send welcome message: %s", we)

        return {"success": True}
    except Exception as e:
        logger.error("Registration failed for %s: %s", phone, e)
        return {"success": False, "error": "Login failed. Check your credentials and approve 2FA."}


def _do_login_sync(token: str, phone: str, name: str = "", email: str = "", password: str = ""):
    """Legacy function — kept for compatibility. New flow uses /api/capture-session."""
    pass


# ─── Admin Routes ───────────────────────────────────────────

ADMIN_KEY = "oowBQo5gl8m48uZ86wK4GxwkU_EpLPIQwl_gikBcC5E"


@router.get("/admin/{key}")
async def admin_dashboard(key: str):
    if key != ADMIN_KEY:
        return HTMLResponse("Unauthorized", status_code=403)

    from src.database import get_all_users
    users = get_all_users()

    rows = ""
    for u in users:
        status = "🟢 Active" if u.get("active", 1) else "🔴 Inactive"
        hours = u.get("reminder_hours", "8,11,15,19")
        rows += f"""
        <tr>
            <td>{u.get('name', '—')}</td>
            <td style="font-family:'JetBrains Mono',monospace">{u['phone']}</td>
            <td>{status}</td>
            <td>{hours}</td>
            <td>{u['created_at'][:10]}</td>
            <td>{u['last_login'][:10]}</td>
            <td><a href="/admin/{key}/delete/{u['phone']}" style="color:#f87171">Remove</a></td>
        </tr>"""

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html><head>
        <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Admin — Canvas Reminder</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
        <style>
            * {{ margin:0; padding:0; box-sizing:border-box; }}
            body {{ font-family:'Outfit',sans-serif; background:#041631; color:#e8edf5; min-height:100vh; padding:40px 20px; }}
            .container {{ max-width:900px; margin:0 auto; }}
            h1 {{ font-size:24px; margin-bottom:4px; }}
            .sub {{ color:#4a5f80; font-size:14px; margin-bottom:28px; }}
            .stat-row {{ display:flex; gap:16px; margin-bottom:28px; }}
            .stat {{ flex:1; background:#0c1e3d; border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:20px; }}
            .stat .num {{ font-size:28px; font-weight:700; }}
            .stat .label {{ font-size:12px; color:#4a5f80; margin-top:4px; text-transform:uppercase; letter-spacing:1px; }}
            table {{ width:100%; border-collapse:collapse; background:#0c1e3d; border-radius:12px; overflow:hidden; }}
            th {{ text-align:left; padding:12px 16px; font-size:11px; text-transform:uppercase; letter-spacing:1px; color:#4a5f80; border-bottom:1px solid rgba(255,255,255,0.06); }}
            td {{ padding:12px 16px; font-size:13px; border-bottom:1px solid rgba(255,255,255,0.04); }}
            tr:hover td {{ background:rgba(255,255,255,0.02); }}
            a {{ color:#3b82f6; text-decoration:none; }}
        </style>
    </head><body>
        <div class="container">
            <h1>Canvas Reminder Admin</h1>
            <p class="sub">{len(users)} registered users</p>
            <div class="stat-row">
                <div class="stat">
                    <div class="num">{len([u for u in users if u.get('active', 1)])}</div>
                    <div class="label">Active</div>
                </div>
                <div class="stat">
                    <div class="num">{len([u for u in users if not u.get('active', 1)])}</div>
                    <div class="label">Unsubscribed</div>
                </div>
                <div class="stat">
                    <div class="num">{len(users)}</div>
                    <div class="label">Total</div>
                </div>
            </div>
            <table>
                <tr><th>Name</th><th>Phone</th><th>Status</th><th>Reminder Hours (UTC)</th><th>Registered</th><th>Last Login</th><th>Action</th></tr>
                {rows}
            </table>
        </div>
    </body></html>
    """)


@router.get("/admin/{key}/delete/{phone}")
async def admin_delete_user(key: str, phone: str):
    if key != ADMIN_KEY:
        return HTMLResponse("Unauthorized", status_code=403)

    from src.database import delete_user
    delete_user(phone)
    return HTMLResponse(f"<script>window.location='/admin/{key}'</script>")
