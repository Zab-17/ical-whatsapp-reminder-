# Canvas Assignment Reminder

A WhatsApp bot that automatically checks your Canvas LMS for assignments, quizzes, announcements, and modules — then sends you reminders throughout the day.

Built for **AUC (American University in Cairo)** but works with any Canvas LMS instance.

## What It Does

- **Scheduled reminders** at 10 AM, 1 PM, 5 PM, and 9 PM (Cairo time) with upcoming assignments and due dates
- **Change detection** every 3 hours — alerts you when professors upload new assignments, quizzes, announcements, or modules
- **Interactive WhatsApp menu** — reply with numbered options to browse courses, assignments, quizzes, modules, and announcements

## Setup

### 1. Clone and install

```bash
git clone https://github.com/zeyadkhaled/canvas-reminder.git
cd canvas-reminder
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure `.env`

```bash
cp .env.example .env
```

Fill in your Canvas email/password and Twilio credentials. See `.env.example` for all options.

### 3. Login to Canvas (one-time, requires 2FA)

```bash
python -m src.auth_setup
```

A browser opens, you approve 2FA on your phone, and session cookies are cached locally.

### 4. Test it

```bash
python -m src.reminder    # Send a test reminder
python -m src.detector    # Run change detection
```

### 5. Deploy to Render (runs 24/7)

```bash
python -m src.export_cookies  # Get base64 cookies for cloud
```

Deploy as a Web Service on [Render](https://render.com) with `uvicorn src.webhook:app --host 0.0.0.0 --port $PORT`. Set `CANVAS_COOKIES_B64` and Twilio env vars.

When cookies expire, re-run `auth_setup` locally and update the env var.

## Twilio WhatsApp Setup

1. Create a free [Twilio](https://twilio.com) account
2. Go to **Messaging → Try it out → Send a WhatsApp message**
3. Send the sandbox join code from your WhatsApp
4. Copy your Account SID, Auth Token, and sandbox number to `.env`

## Tech Stack

Python · FastAPI · canvasapi · Twilio · Playwright · APScheduler
