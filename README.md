# Canvas Assignment Reminder

A WhatsApp bot that automatically checks your Canvas LMS for assignments, quizzes, announcements, and modules — then sends you reminders throughout the day.

Built for **AUC (American University in Cairo)** but works with any Canvas LMS instance.

## What It Does

- **Scheduled reminders** at 10 AM, 1 PM, 5 PM, and 9 PM (Cairo time) with upcoming assignments and due dates
- **Change detection** every 3 hours — alerts you when professors upload new assignments, quizzes, announcements, or modules
- **Interactive WhatsApp menu** — tap buttons to browse courses, assignments, quizzes, modules, and announcements

## Setup

### 1. Clone and install

```bash
git clone https://github.com/Zab-17/canvas-reminder.git
cd canvas-reminder
pip install -r requirements.txt
playwright install chromium
```

### 2. Set up WhatsApp (Meta Cloud API)

1. Go to [developers.facebook.com](https://developers.facebook.com) and create an app (Business type)
2. Add **WhatsApp** product to your app
3. In **WhatsApp → API Setup**, copy your **Phone Number ID** and **Access Token**
4. Send a test message to verify it works

### 3. Configure `.env`

```bash
cp .env.example .env
```

Fill in your Canvas email/password and Meta WhatsApp credentials.

### 4. Login to Canvas (one-time, requires 2FA)

```bash
python -m src.auth_setup
```

A browser opens, you approve 2FA on your phone, and session cookies are cached locally.

### 5. Test it

```bash
python -m src.reminder    # Send a test reminder
python -m src.detector    # Run change detection
```

### 6. Deploy to Render (runs 24/7)

```bash
python -m src.export_cookies  # Get base64 cookies for cloud
```

Deploy as a Web Service on [Render](https://render.com). Set `CANVAS_COOKIES_B64` and WhatsApp env vars.

Set your Render webhook URL in Meta's App Dashboard: `https://your-app.onrender.com/webhook/whatsapp`

When cookies expire, re-run `auth_setup` locally and update the env var.

## Tech Stack

Python · FastAPI · Meta WhatsApp Cloud API · Playwright · APScheduler
