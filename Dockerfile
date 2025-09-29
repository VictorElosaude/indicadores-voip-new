FROM python:3.9-slim

# Instalar dependências do sistema (incluindo Chrome/Chromedriver para Selenium)
RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg \
    chromium chromium-driver \
    libglib2.0-0 libnss3 libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

# Variáveis de ambiente para Selenium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

# Diretório de trabalho
WORKDIR /app

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo o código
COPY . .

# Expor a porta do Dash
EXPOSE 8050

# Comando para rodar a aplicação
CMD ["python", "src/dashboard.py"]
