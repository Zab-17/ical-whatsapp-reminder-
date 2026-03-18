"""Login web page for Canvas SSO registration."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from src.database import add_user

logger = logging.getLogger(__name__)

router = APIRouter()

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Canvas Reminder - Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, sans-serif; background: #0a0a0a; color: #fff; min-height: 100vh; display: flex; justify-content: center; align-items: center; }
        .container { max-width: 420px; width: 90%; padding: 40px; background: #1a1a1a; border-radius: 16px; }
        h1 { font-size: 24px; margin-bottom: 8px; }
        p { color: #888; margin-bottom: 24px; font-size: 14px; }
        label { display: block; font-size: 14px; margin-bottom: 6px; color: #ccc; }
        input { width: 100%; padding: 12px; border: 1px solid #333; border-radius: 8px; background: #111; color: #fff; font-size: 16px; margin-bottom: 16px; }
        button { width: 100%; padding: 14px; background: #2563eb; color: #fff; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; }
        button:hover { background: #1d4ed8; }
        .step { display: none; }
        .step.active { display: block; }
        .success { color: #22c55e; text-align: center; }
        .error { color: #ef4444; font-size: 13px; margin-bottom: 12px; }
        .info { background: #1e293b; padding: 12px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; color: #94a3b8; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Step 1: Enter phone number -->
        <div id="step1" class="step active">
            <h1>📚 Canvas Reminder</h1>
            <p>Get assignment reminders on WhatsApp</p>
            <label>WhatsApp Number (with country code)</label>
            <input type="tel" id="phone" placeholder="201154069714" value="">
            <div class="info">Enter your number without + or spaces. Example: 201154069714</div>
            <button onclick="goToStep2()">Next</button>
        </div>

        <!-- Step 2: Canvas Login -->
        <div id="step2" class="step">
            <h1>Login to Canvas</h1>
            <p>Enter your AUC credentials. They're sent directly to Canvas, we don't store them.</p>
            <label>AUC Email</label>
            <input type="email" id="email" placeholder="you@aucegypt.edu">
            <label>Password</label>
            <input type="password" id="password">
            <div id="loginError" class="error" style="display:none"></div>
            <div class="info">After clicking Login, approve the 2FA request on your Microsoft Authenticator app.</div>
            <button onclick="doLogin()" id="loginBtn">Login to Canvas</button>
        </div>

        <!-- Step 3: Success -->
        <div id="step3" class="step">
            <div class="success">
                <h1>✅ You're all set!</h1>
                <p style="color:#22c55e; margin-top:16px;">Send any message to the bot on WhatsApp to get started.</p>
                <p style="color:#666; margin-top:8px;">You'll receive assignment reminders at 10am, 1pm, 5pm, and 9pm.</p>
            </div>
        </div>
    </div>
    <script>
        let phone = '';

        function goToStep2() {
            phone = document.getElementById('phone').value.trim();
            if (!phone || phone.length < 10) {
                alert('Please enter a valid phone number');
                return;
            }
            document.getElementById('step1').classList.remove('active');
            document.getElementById('step2').classList.add('active');
        }

        async function doLogin() {
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const btn = document.getElementById('loginBtn');
            const errDiv = document.getElementById('loginError');

            if (!email || !password) {
                errDiv.textContent = 'Please fill in both fields';
                errDiv.style.display = 'block';
                return;
            }

            btn.textContent = 'Logging in... (approve 2FA on your phone)';
            btn.disabled = true;
            errDiv.style.display = 'none';

            try {
                const resp = await fetch('/api/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ phone, email, password }),
                });
                const data = await resp.json();

                if (data.success) {
                    document.getElementById('step2').classList.remove('active');
                    document.getElementById('step3').classList.add('active');
                } else {
                    errDiv.textContent = data.error || 'Login failed. Try again.';
                    errDiv.style.display = 'block';
                    btn.textContent = 'Login to Canvas';
                    btn.disabled = false;
                }
            } catch (e) {
                errDiv.textContent = 'Connection error. Try again.';
                errDiv.style.display = 'block';
                btn.textContent = 'Login to Canvas';
                btn.disabled = false;
            }
        }
    </script>
</body>
</html>
"""


@router.get("/login", response_class=HTMLResponse)
async def login_page():
    return LOGIN_HTML


@router.post("/api/register")
async def register_user(request: Request):
    """Handle Canvas SSO login via server-side Playwright."""
    body = await request.json()
    phone = body.get("phone", "").strip()
    email = body.get("email", "").strip()
    password = body.get("password", "")

    if not phone or not email or not password:
        return {"success": False, "error": "All fields are required"}

    try:
        from src.auth import login_and_get_cookies
        cookies = login_and_get_cookies(email, password)
        add_user(phone, cookies)
        logger.info("User %s registered successfully", phone)
        return {"success": True}
    except Exception as e:
        logger.error("Registration failed for %s: %s", phone, e)
        return {"success": False, "error": str(e)}
