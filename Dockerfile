FROM python:3.9-slim

# Instalar dependências do sistema (mantenho as suas e acrescento o Chrome)
RUN apt-get update && apt-get install -y \
    wget curl unzip gnupg \
    chromium chromium-driver \
    libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

# Variáveis de ambiente para o Selenium encontrar o Chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

# Diretório de trabalho
WORKDIR /app

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o resto do código
COPY . .

# Expor porta do Dash
EXPOSE 8050

# Rodar a aplicação
CMD ["python", "dashboard.py"]
