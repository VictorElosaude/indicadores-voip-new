# Usa uma imagem oficial do Python como base para um tamanho de imagem menor
FROM python:3.11-slim

# Define o diretório de trabalho no contêiner
WORKDIR /app

# Instala o navegador Chromium e outras dependências
RUN apt-get update && apt-get install -y \
    chromium \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo requirements.txt primeiro para otimizar a cache de construção
COPY requirements.txt .

# Instala as dependências do projeto
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código do projeto para o contêiner
COPY . .

# Cria o diretório de logs
RUN mkdir -p logs

# Adicione esta linha para expor a porta 8050
EXPOSE 8050

# Comando para rodar o script principal
CMD ["python", "src/dashboard.py"]