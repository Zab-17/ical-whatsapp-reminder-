FROM node:20-slim

# Install Python and Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    chromium libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    libx11-xcb1 libxcb1 libxext6 libxfixes3 libxi6 libxtst6 \
    fonts-liberation libappindicator3-1 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Point Puppeteer to system Chromium
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV PUPPETEER_SKIP_DOWNLOAD=true
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true

WORKDIR /app

# Install Node.js dependencies (skip Chromium download)
COPY whatsapp-bridge/package.json whatsapp-bridge/package-lock.json ./whatsapp-bridge/
RUN cd whatsapp-bridge && PUPPETEER_SKIP_DOWNLOAD=true npm ci --production

# Install Python dependencies
COPY requirements.txt .
RUN python3 -m venv /app/venv && /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Start both processes
RUN printf '#!/bin/bash\necho "Starting WhatsApp bridge..."\nnode /app/whatsapp-bridge/index.js &\necho "Starting Python server..."\nexec /app/venv/bin/uvicorn src.webhook:app --host 0.0.0.0 --port 8000\n' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 8000

CMD ["/app/start.sh"]
