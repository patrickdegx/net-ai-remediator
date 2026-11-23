# Imagem base enxuta com Python 3.11.
FROM python:3.11-slim

# Define /app como diretório de trabalho dentro do container.
WORKDIR /app

# Instala utilitários de compilação e git, removendo cache do apt em seguida.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements.txt primeiro para aproveitar cache de camadas no build.
COPY requirements.txt .

# Atualiza o pip e instala as dependências Python declaradas no projeto.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia o restante do código-fonte do projeto para /app.
COPY . .

# Executa o fluxo principal da aplicação por padrão ao iniciar o container.
CMD ["python", "main.py"]