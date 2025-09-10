# Usa a imagem oficial do Selenium com o Chrome pré-instalado
FROM selenium/standalone-chrome

# Define o diretório de trabalho no contêiner
WORKDIR /app

# Instala o Python 3 e o gerenciador de pacotes pip.
# A imagem do Selenium não vem com Python por padrão,
# então precisamos instalá-lo manualmente.
USER root
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Volta para o usuário padrão do Selenium para segurança
USER seluser

# Copia os arquivos de código para o contêiner
# A melhor prática é copiar o requirements.txt primeiro para otimizar o cache
COPY requirements.txt .

# Instala as dependências do projeto
RUN pip3 install --no-cache-dir -r requirements.txt

# Copia o restante do código do seu projeto
# O . significa que ele vai copiar tudo do diretório de onde o Dockerfile está
COPY . .

# Cria o diretório de logs
RUN mkdir -p logs

# Comando para rodar o script principal
# Certifique-se de que o caminho 'src/dashboard.py' está correto
CMD ["python3", "src/dashboard.py"]