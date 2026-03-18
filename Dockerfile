FROM node:20-slim

# Install Python and Chromium for whatsapp-web.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    chromium libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

WORKDIR /app

# Install Node.js dependencies
COPY whatsapp-bridge/package.json whatsapp-bridge/package-lock.json ./whatsapp-bridge/
RUN cd whatsapp-bridge && npm ci --production

# Install Python dependencies
COPY requirements.txt .
RUN python3 -m venv /app/venv && /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Start script that runs both processes
RUN echo '#!/bin/bash\nnode /app/whatsapp-bridge/index.js &\nexec /app/venv/bin/uvicorn src.webhook:app --host 0.0.0.0 --port 8000' > /app/start.sh && chmod +x /app/start.sh

EXPOSE 8000

CMD ["/app/start.sh"]
