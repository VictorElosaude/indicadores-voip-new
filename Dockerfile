# ETAPA DE BUILD
# Usa uma imagem base maior para instalar todas as dependências
FROM python:3.9 as builder

# Define o diretório de trabalho
WORKDIR /app

# Instala dependências do sistema.
# Isso inclui o Google Chrome e o ChromeDriver, o jq para baixar o ChromeDriver e as bibliotecas do sistema
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
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Instala o ChromeDriver compatível usando jq para encontrar o URL correto
RUN LATEST_CHROMEDRIVER_URL=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json" | jq -r '.versions[] | select(.version | contains(".")) | .downloads.chromedriver[] | select(.platform == "linux64") | .url') \
    && wget -O /tmp/chromedriver.zip "${LATEST_CHROMEDRIVER_URL}" \
    && tar -xvzf /tmp/chromedriver.zip -C /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm /tmp/chromedriver.zip

# Copia e instala as dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ETAPA FINAL
# Cria uma nova imagem limpa
FROM python:3.9-slim

# Define o diretório de trabalho no container
WORKDIR /app

# Copia as dependências do sistema da etapa de build
COPY --from=builder /usr/lib/x86_64-linux-gnu/libgbm.so.1 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libnss3.so /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libxss1.so.1 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libasound.so.2 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libatk1.0-0 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/x86_64-linux-gnu/libgtk-3-0 /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/bin/google-chrome-stable /usr/bin/
COPY --from=builder /usr/local/bin/chromedriver /usr/local/bin/

# Copia as dependências Python da etapa de build
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /app /app

# Expõe a porta
EXPOSE 8050

# Comando de inicialização
CMD ["python", "src/dashboard.py"]