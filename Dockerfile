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

# Start both processes
RUN printf '#!/bin/bash\necho "Starting WhatsApp bridge (Baileys)..."\nnode /app/whatsapp-bridge/index.js &\necho "Starting Python server..."\nexec /app/venv/bin/uvicorn src.webhook:app --host 0.0.0.0 --port 8000\n' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 8000

CMD ["/app/start.sh"]
