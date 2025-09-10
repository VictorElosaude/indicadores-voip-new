# Começa a partir de uma imagem Python slim para uma pegada menor.
FROM python:3.11-slim

# Define o diretório de trabalho no contêiner.
WORKDIR /app

# Copia o ficheiro requirements.txt primeiro para tirar partido da cache de construção do Docker.
COPY requirements.txt .

# Instala as dependências do projeto.
RUN pip install --no-cache-dir -r requirements.txt

# Instala o Selenium e outras ferramentas necessárias.
# Isto pressupõe que está a usar um driver de navegador (ex: ChromeDriver)
# que pode ser instalado via pip.
# Esta é uma abordagem mais moderna do que usar uma imagem base específica do Selenium.
RUN pip install selenium

# Agora, copia o restante do código da sua aplicação.
COPY . .

# Comando para executar o script principal.
CMD ["python", "src/dashboard.py"]