FROM node:20-slim

# Install Python only — Baileys doesn't need Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Node.js deps (Baileys — no browser needed)
COPY whatsapp-bridge/package.json ./whatsapp-bridge/
RUN cd whatsapp-bridge && npm install --production

# Install Python dependencies
COPY requirements.txt .
RUN python3 -m venv /app/venv && /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Start both processes — Node auto-restarts on crash
RUN printf '#!/bin/bash\n\n# Clear stale signal session keys on startup to prevent "Waiting for this message"\necho "Clearing stale session keys..."\nrm -f ${WA_SESSION_PATH:-./auth_session}/session-*.json ${WA_SESSION_PATH:-./auth_session}/pre-key-*.json ${WA_SESSION_PATH:-./auth_session}/sender-key-*.json 2>/dev/null\necho "Session keys cleared."\n\n# Auto-restart Node bridge on crash\nstart_bridge() {\n    while true; do\n        echo "Starting WhatsApp bridge (Baileys)..."\n        node /app/whatsapp-bridge/index.js\n        EXIT_CODE=$?\n        echo "Bridge exited with code $EXIT_CODE. Restarting in 5s..."\n        sleep 5\n    done\n}\nstart_bridge &\n\necho "Starting Python server..."\nexec /app/venv/bin/uvicorn src.webhook:app --host 0.0.0.0 --port 8000\n' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 8000

CMD ["/app/start.sh"]
