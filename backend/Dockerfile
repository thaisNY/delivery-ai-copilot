FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Na subida: cria o schema, roda o pipeline se o banco estiver vazio e inicia a API
CMD ["sh", "-c", "python -m pipeline.run_pipeline && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
