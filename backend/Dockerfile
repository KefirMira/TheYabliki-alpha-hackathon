FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHON_DOTENV_DISABLED=1
WORKDIR /app
COPY requirements.txt requirements-db.txt ./
RUN pip install --no-cache-dir -r requirements.txt && pip check
RUN useradd --create-home --uid 10001 backend
COPY main.py settings.py analysis_admin.py news_matching_admin.py auth_demo.py integration_demo.py ./
COPY api ./api
COPY db ./db
COPY repositories ./repositories
COPY schemas ./schemas
COPY services ./services
COPY company_import ./company_import
COPY fixtures/gateway_macro_v1.json ./fixtures/gateway_macro_v1.json
COPY fixtures/integration_demo.sql ./fixtures/integration_demo.sql
USER backend
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
