# Usa uma imagem oficial do Python como base
FROM python:3.11-slim

# Define o diretório de trabalho no contêiner
WORKDIR /app

# Instala o navegador Chromium e outras dependências
# A flag --no-install-recommends mantém a imagem pequena
RUN apt-get update && apt-get install -y \
    chromium \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copia os arquivos de dependência primeiro para aproveitar a cache do Docker
COPY requirements.txt .

# Instala as dependências do projeto
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante dos arquivos do seu projeto
COPY . .

# Cria o diretório de logs
RUN mkdir -p logs

# Comando para rodar o script principal
CMD ["python", "novo.py"]