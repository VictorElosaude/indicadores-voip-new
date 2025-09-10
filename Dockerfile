# Usa uma imagem base Python slim
FROM python:3.9-slim

# Evita prompts interativos durante instalação
ENV DEBIAN_FRONTEND=noninteractive

# Instala dependências do sistema necessárias para o Chrome e o ChromeDriver, incluindo o jq
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libgtk-3-0 \
    libgbm-dev \
    curl \
    jq \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Instala o Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
       > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Instala o ChromeDriver compatível usando jq para encontrar o URL correto
RUN LATEST_CHROMEDRIVER_URL=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json" | jq -r '.versions[] | select(.version | contains(".")) | .downloads.chromedriver[] | select(.platform == "linux64") | .url') \
    && wget -O /tmp/chromedriver.zip "${LATEST_CHROMEDRIVER_URL}" \
    && tar -xvzf /tmp/chromedriver.zip -C /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm /tmp/chromedriver.zip

# Define o diretório de trabalho no container
WORKDIR /app

# Copia requirements e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código do projeto
COPY . .

# Expondo a porta
EXPOSE 8050

# Comando de inicialização
CMD ["python", "src/dashboard.py"]