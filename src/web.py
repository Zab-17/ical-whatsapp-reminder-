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
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <title>Canvas Reminder — AUC</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,600&family=DM+Mono:wght@300;400&display=swap" rel="stylesheet">
    <style>
        :root{--navy:#041631;--surface:rgba(6,20,42,0.65);--crimson:#c41230;--gold:#d4a843;--text:#dfe6f0;--mid:#6e83a3;--dim:#34506e}
        *{margin:0;padding:0;box-sizing:border-box}
        html,body{height:100%;overflow:hidden}
        body{font-family:'Cormorant Garamond',serif;background:var(--navy);color:var(--text);display:flex;align-items:center;justify-content:center}

        /* === LIVING BACKGROUND — slow morphing aurora + drifting motes === */
        canvas#bg{position:fixed;inset:0;z-index:0}
        .grain{position:fixed;inset:0;z-index:1;pointer-events:none;opacity:0.25;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E")}

        .wrap{position:relative;z-index:2;width:100%;max-width:420px;padding:16px}

        .card{background:var(--surface);border:1px solid rgba(255,255,255,0.04);border-radius:20px;padding:28px 28px 24px;backdrop-filter:blur(60px);-webkit-backdrop-filter:blur(60px);box-shadow:0 1px 0 rgba(255,255,255,0.03) inset,0 40px 80px -20px rgba(0,0,0,0.5);animation:appear 1s cubic-bezier(.16,1,.3,1) both}
        @keyframes appear{from{opacity:0;transform:translateY(30px) scale(.97)}to{opacity:1;transform:translateY(0) scale(1)}}

        .hdr{text-align:center;margin-bottom:20px}
        .badge{display:inline-block;padding:3px 14px;border:1px solid rgba(212,168,67,0.2);border-radius:100px;font-family:'DM Mono',monospace;font-size:9px;color:var(--gold);letter-spacing:3px;text-transform:uppercase;margin-bottom:14px;animation:appear 1s cubic-bezier(.16,1,.3,1) .1s both}
        .hdr h1{font-size:28px;font-weight:300;letter-spacing:-.5px;line-height:1.1;animation:appear 1s cubic-bezier(.16,1,.3,1) .15s both}
        .hdr h1 em{font-style:italic;font-weight:600;color:var(--crimson)}
        .hdr .sub{color:var(--mid);font-family:'DM Mono',monospace;font-size:11px;font-weight:300;margin-top:8px;letter-spacing:.5px;animation:appear 1s cubic-bezier(.16,1,.3,1) .2s both}

        .line{height:1px;margin:0 0 18px;background:linear-gradient(90deg,transparent,rgba(196,18,48,0.12),transparent)}

        .step{display:none}.step.active{display:block;animation:si .6s cubic-bezier(.16,1,.3,1) both}
        @keyframes si{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}

        .f{margin-bottom:12px}
        .f label{display:block;font-family:'DM Mono',monospace;font-size:9px;color:var(--dim);letter-spacing:2px;text-transform:uppercase;margin-bottom:6px}
        .f input{width:100%;padding:12px 14px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.05);border-radius:10px;color:var(--text);font-family:'DM Mono',monospace;font-size:13px;outline:none;transition:all .3s}
        .f input::placeholder{color:var(--dim);font-family:'Cormorant Garamond',serif;font-size:14px;font-weight:300;font-style:italic}
        .f input:focus{border-color:rgba(212,168,67,0.3);background:rgba(212,168,67,0.03);box-shadow:0 0 0 3px rgba(212,168,67,0.04)}
        .f input.invalid{border-color:rgba(196,18,48,0.4);box-shadow:0 0 0 3px rgba(196,18,48,0.05)}
        .f input.valid{border-color:rgba(34,197,94,0.3)}
        .fh{font-family:'DM Mono',monospace;font-size:9px;color:var(--dim);margin-top:5px;line-height:1.7;letter-spacing:.2px}
        .fh b{color:var(--gold);font-weight:400}
        .fh .ex{display:inline-block;margin-top:2px;padding:2px 8px;background:rgba(212,168,67,0.06);border:1px solid rgba(212,168,67,0.1);border-radius:5px;color:var(--text);font-weight:500;letter-spacing:1.5px}
        .pe{display:none;margin-top:5px;font-family:'DM Mono',monospace;font-size:9px;color:var(--crimson)}

        .btn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;padding:13px 24px;background:var(--crimson);color:#fff;border:none;border-radius:10px;font-family:'Cormorant Garamond',serif;font-size:15px;font-weight:600;letter-spacing:.5px;cursor:pointer;transition:all .4s cubic-bezier(.16,1,.3,1);position:relative;overflow:hidden}
        .btn::before{content:'';position:absolute;inset:0;background:linear-gradient(135deg,transparent 40%,rgba(255,255,255,0.08));opacity:0;transition:opacity .4s}
        .btn:hover::before{opacity:1}
        .btn:hover{transform:translateY(-1px);box-shadow:0 10px 30px -8px rgba(196,18,48,0.4)}
        .btn:active{transform:translateY(0)}
        .btn svg{width:14px;height:14px;stroke-width:2}

        .feats{margin-top:16px;padding-top:14px;border-top:1px solid rgba(255,255,255,0.03);display:grid;grid-template-columns:1fr 1fr;gap:2px}
        .ft{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;transition:background .3s}
        .ft:hover{background:rgba(255,255,255,0.03)}
        .ft .i{font-size:14px;flex-shrink:0}
        .ft span{font-family:'DM Mono',monospace;font-size:9px;color:var(--mid);letter-spacing:.2px}

        .s2t{font-size:22px;font-weight:300;margin-bottom:16px;letter-spacing:-.3px}
        .s2t em{font-weight:600;font-style:italic;color:var(--crimson)}
        .ins{display:flex;gap:12px;align-items:flex-start;padding:7px 0;font-family:'DM Mono',monospace;font-size:10px;color:var(--mid);border-bottom:1px solid rgba(255,255,255,0.03);letter-spacing:.2px}
        .ins:last-of-type{border:none}
        .ins .n{width:18px;height:18px;flex-shrink:0;display:flex;align-items:center;justify-content:center;border-radius:50%;background:rgba(196,18,48,0.08);font-size:9px;font-weight:500;color:var(--crimson)}
        .ins .n.ok{background:rgba(34,197,94,0.08);color:#22c55e}
        .ins b{color:var(--text);font-weight:500}

        .sec{display:flex;align-items:flex-start;gap:10px;margin-top:16px;padding:12px 14px;background:rgba(34,197,94,0.03);border:1px solid rgba(34,197,94,0.06);border-radius:10px}
        .sec p{font-family:'DM Mono',monospace;font-size:9px;color:var(--mid);line-height:1.6;letter-spacing:.2px}

        .foot{text-align:center;margin-top:16px;font-family:'DM Mono',monospace;font-size:8px;color:var(--dim);letter-spacing:3px;text-transform:uppercase}

        @media(max-height:700px){.card{padding:22px 24px 20px}.hdr{margin-bottom:14px}.hdr h1{font-size:24px}.badge{margin-bottom:10px}.feats{margin-top:12px;padding-top:10px}}
        @media(max-width:440px){.card{padding:24px 20px}.hdr h1{font-size:24px}.feats{grid-template-columns:1fr}}
    </style>
</head>
<body>
    <canvas id="bg"></canvas>
    <div class="grain"></div>

    <div class="wrap">
        <div class="card">
            <div class="hdr">
                <div class="badge">AUC Canvas</div>
                <h1>Never miss<br>an <em>assignment</em></h1>
                <p class="sub">WhatsApp reminders for your deadlines</p>
            </div>
            <div class="line"></div>

            <div id="step1" class="step active">
                <div class="f"><label>Name</label><input type="text" id="name" placeholder="Your first name" required autocomplete="given-name"></div>
                <div class="f">
                    <label>WhatsApp Number</label>
                    <input type="tel" id="phone" placeholder="201XXXXXXXXX" required inputmode="numeric" autocomplete="tel">
                    <div class="fh">Enter as <b>20</b> + number without leading 0<br><span class="ex">2010XXXXXXXX</span></div>
                    <div class="pe" id="phoneError"></div>
                </div>
                <button class="btn" onclick="goToStep2()">Get Started <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M17 8l4 4m0 0l-4 4m4-4H3"/></svg></button>
                <div class="feats">
                    <div class="ft"><span class="i">📅</span><span>4x daily reminders</span></div>
                    <div class="ft"><span class="i">🔔</span><span>New upload alerts</span></div>
                    <div class="ft"><span class="i">📖</span><span>Browse courses</span></div>
                    <div class="ft"><span class="i">💬</span><span>WhatsApp chatbot</span></div>
                </div>
            </div>

            <div id="step2" class="step">
                <div class="s2t">Connect <em>Canvas</em></div>
                <a href="/extension" class="btn" style="margin-bottom:18px;text-decoration:none">Download Extension <svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg></a>
                <div class="ins"><div class="n">1</div><span><b>Unzip</b> the downloaded file</span></div>
                <div class="ins"><div class="n">2</div><span>Chrome &rarr; <b>chrome://extensions</b></span></div>
                <div class="ins"><div class="n">3</div><span>Enable <b>Developer mode</b> (top right)</span></div>
                <div class="ins"><div class="n">4</div><span><b>Load unpacked</b> &rarr; select folder</span></div>
                <div class="ins"><div class="n">5</div><span>Puzzle icon &rarr; <b>Canvas Reminder</b></span></div>
                <div class="ins"><div class="n">6</div><span>Enter name &amp; number as <b>201XXXXXXXXX</b></span></div>
                <div class="ins"><div class="n">7</div><span><b>Open Canvas</b>, log in with AUC account</span></div>
                <div class="ins"><div class="n ok">8</div><span>Click <b>"I'm logged in"</b> &mdash; done</span></div>
                <div class="sec"><span style="font-size:13px;flex-shrink:0">🔒</span><p>We never see your password. The extension only reads your Canvas session cookie after you log in.</p></div>
            </div>
        </div>
        <div class="foot">Built for AUC students</div>
    </div>

    <!-- Animated background: aurora blobs + floating motes -->
    <script>
    const c=document.getElementById('bg'),x=c.getContext('2d');
    let W,H;
    function resize(){W=c.width=innerWidth;H=c.height=innerHeight}
    resize();addEventListener('resize',resize);

    // Aurora blobs
    const blobs=[
        {x:.8,y:.2,r:350,color:[196,18,48],speed:.0003,phase:0},
        {x:.15,y:.85,r:280,color:[10,58,138],speed:.00025,phase:2},
        {x:.5,y:.5,r:200,color:[212,168,67],speed:.0004,phase:4,alpha:.04}
    ];
    // Floating motes
    const motes=[];
    for(let i=0;i<25;i++){
        motes.push({
            x:Math.random()*1.2-.1,y:Math.random(),
            size:Math.random()*2+1,
            speed:.0001+Math.random()*.0003,
            dx:(Math.random()-.5)*.00015,
            alpha:0,maxAlpha:.15+Math.random()*.25,
            phase:Math.random()*Math.PI*2,
            color:Math.random()>.5?[212,168,67]:[196,18,48]
        });
    }

    let t=0;
    function draw(){
        t++;
        x.clearRect(0,0,W,H);
        x.fillStyle='#041631';
        x.fillRect(0,0,W,H);

        // Draw aurora
        for(const b of blobs){
            const ox=Math.sin(t*b.speed+b.phase)*60;
            const oy=Math.cos(t*b.speed*.7+b.phase)*40;
            const g=x.createRadialGradient(b.x*W+ox,b.y*H+oy,0,b.x*W+ox,b.y*H+oy,b.r);
            const a=b.alpha||.14;
            g.addColorStop(0,`rgba(${b.color},${a})`);
            g.addColorStop(1,'rgba(0,0,0,0)');
            x.fillStyle=g;
            x.fillRect(0,0,W,H);
        }

        // Draw motes
        for(const m of motes){
            m.x+=m.dx;
            m.y-=m.speed;
            m.phase+=.02;
            // Fade in/out based on y
            if(m.y>0.1&&m.y<0.9)m.alpha+=(m.maxAlpha-m.alpha)*.02;
            else m.alpha*=.98;
            if(m.y<-0.05){m.y=1.05;m.x=Math.random()*1.2-.1;m.alpha=0}

            const sx=m.x*W+Math.sin(m.phase)*20;
            const sy=m.y*H;
            x.beginPath();
            x.arc(sx,sy,m.size,0,Math.PI*2);
            x.fillStyle=`rgba(${m.color},${m.alpha})`;
            x.fill();
            // Glow
            const gg=x.createRadialGradient(sx,sy,0,sx,sy,m.size*4);
            gg.addColorStop(0,`rgba(${m.color},${m.alpha*.3})`);
            gg.addColorStop(1,'rgba(0,0,0,0)');
            x.fillStyle=gg;
            x.fillRect(sx-m.size*4,sy-m.size*4,m.size*8,m.size*8);
        }
        requestAnimationFrame(draw);
    }
    draw();
    </script>

    <script>
        function goToStep2() {
            const name = document.getElementById('name').value.trim();
            let phone = document.getElementById('phone').value.replace(/[\\s+\\-]/g, '').trim();
            const phoneInput = document.getElementById('phone');
            const phoneError = document.getElementById('phoneError');

            if (!name) return alert('Please enter your name');

            // Auto-fix: if starts with 0, prepend 20
            if (phone.startsWith('0')) phone = '20' + phone.substring(1);

            // Validate format: 20 + 10 digits
            if (!/^20\\d{10}$/.test(phone)) {
                phoneInput.classList.add('invalid');
                phoneInput.classList.remove('valid');
                phoneError.style.display = 'block';
                phoneError.textContent = 'Must be 201XXXXXXXXX (12 digits starting with 20)';
                return;
            }

            phoneInput.classList.remove('invalid');
            phoneInput.classList.add('valid');
            phoneError.style.display = 'none';

            document.getElementById('step1').classList.remove('active');
            document.getElementById('step2').classList.add('active');
        }

        // Live validation on phone input
        document.getElementById('phone').addEventListener('input', function() {
            const val = this.value.replace(/[^0-9]/g, '');
            const err = document.getElementById('phoneError');
            this.classList.remove('invalid','valid');
            err.style.display = 'none';
            if (val.length >= 4) {
                let check = val;
                if (check.startsWith('0')) check = '20' + check.substring(1);
                if (check.startsWith('20') && check.length <= 12) {
                    if (check.length === 12) this.classList.add('valid');
                } else if (!check.startsWith('20')) {
                    this.classList.add('invalid');
                    err.style.display = 'block';
                    err.textContent = 'Must start with 20 (Egypt code)';
                }
            }
        });
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


@router.get("/extension")
async def download_extension():
    """Serve the extension as a zip download."""
    import io
    import zipfile
    from fastapi.responses import StreamingResponse
    from pathlib import Path

    ext_dir = Path(__file__).parent.parent / "extension"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in ext_dir.iterdir():
            if f.is_file():
                zf.write(f, f"canvas-reminder-extension/{f.name}")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=canvas-reminder-extension.zip"},
    )


@router.post("/api/register-cookies")
async def register_cookies(request: Request):
    """Receive Canvas cookies from browser extension."""
    body = await request.json()
    phone = body.get("phone", "").replace(" ", "").replace("+", "").strip()
    name = body.get("name", "").strip()
    cookies = body.get("cookies", [])

    if not phone or not cookies:
        return {"success": False, "error": "Missing phone or cookies"}

    # Auto-fix Egyptian numbers starting with 0
    if phone.startswith("0"):
        phone = "20" + phone[1:]

    import re
    if not re.match(r"^20\d{10}$", phone):
        return {"success": False, "error": "Phone must be format 201XXXXXXXXX (country code 20 + number)"}

    add_user(phone, cookies, name=name)
    from src.canvas_service import invalidate_client
    invalidate_client(phone)
    logger.info("User %s (%s) registered via extension", phone, name)

    try:
        from src import whatsapp_service
        greeting = f"Hey {name}! " if name else ""
        whatsapp_service.send_text(
            f"✅ *{greeting}Canvas Reminder is set up!*\n\n"
            "You'll receive assignment reminders at 10am, 1pm, 5pm & 9pm.\n\n"
            "Send *hi* to see the menu.",
            to=phone,
        )
    except Exception as e:
        logger.warning("Failed to send welcome message: %s", e)

    return {"success": True}


# ─── Admin Routes ───────────────────────────────────────────

ADMIN_KEY = "oowBQo5gl8m48uZ86wK4GxwkU_EpLPIQwl_gikBcC5E"


@router.get("/admin/{key}")
async def admin_dashboard(key: str):
    if key != ADMIN_KEY:
        return HTMLResponse("Unauthorized", status_code=403)

    from src.database import get_all_users
    from src.canvas_service import check_cookies_valid
    users = get_all_users()

    rows = ""
    valid_count = 0
    for u in users:
        status = "🟢 Active" if u.get("active", 1) else "🔴 Inactive"
        hours = u.get("reminder_hours", "8,20")
        cookies_ok = check_cookies_valid(u["phone"])
        if cookies_ok:
            valid_count += 1
        cookies_badge = '🟢 Valid' if cookies_ok else '🔴 Expired'
        rows += f"""
        <tr>
            <td>{u.get('name', '—')}</td>
            <td style="font-family:'JetBrains Mono',monospace">{u['phone']}</td>
            <td>{status}</td>
            <td>{cookies_badge}</td>
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
                    <div class="num">{valid_count}/{len(users)}</div>
                    <div class="label">Valid Cookies</div>
                </div>
                <div class="stat">
                    <div class="num">{len(users)}</div>
                    <div class="label">Total</div>
                </div>
            </div>
            <table>
                <tr><th>Name</th><th>Phone</th><th>Status</th><th>Cookies</th><th>Reminder Hours (UTC)</th><th>Registered</th><th>Last Login</th><th>Action</th></tr>
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
