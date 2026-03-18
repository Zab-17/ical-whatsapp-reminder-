FROM node:20-slim

# Install system deps for Chromium (Puppeteer downloads its own)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    libx11-xcb1 libxcb1 libxext6 libxfixes3 libxi6 libxtst6 \
    fonts-liberation xdg-utils ca-certificates wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Node.js deps — let Puppeteer download its own Chromium
COPY whatsapp-bridge/package.json ./whatsapp-bridge/
RUN cd whatsapp-bridge && npm install --production

# Install Python dependencies
COPY requirements.txt .
RUN python3 -m venv /app/venv && /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Start both processes
RUN printf '#!/bin/bash\necho "Starting WhatsApp bridge..."\nnode /app/whatsapp-bridge/index.js &\necho "Starting Python server..."\nexec /app/venv/bin/uvicorn src.webhook:app --host 0.0.0.0 --port 8000\n' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 8000

CMD ["/app/start.sh"]
