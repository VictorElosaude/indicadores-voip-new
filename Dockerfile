# Usa uma imagem base Python slim para um tamanho menor
FROM python:3.9-slim

# Instala as dependências do sistema necessárias para o Chrome e o ChromeDriver
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    libnss3-dev \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libgtk-3-0 \
    --no-install-recommends

# Instala o Chrome Stable
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update && apt-get install -y google-chrome-stable

# Define o diretório de trabalho no container
WORKDIR /app

# Copia o arquivo de requisitos e instala as dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o seu projeto para o container
COPY . .

# Define a variável de ambiente para que o Selenium saiba onde encontrar o ChromeDriver
ENV PATH="/usr/bin/google-chrome:${PATH}"

# Define a porta que seu aplicativo irá expor
EXPOSE 8050

# Define o comando que será executado quando o container iniciar
CMD ["python", "src/dashboard.py"]