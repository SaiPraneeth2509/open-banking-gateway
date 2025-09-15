FROM python:3.11-slim

WORKDIR /app

# Install system deps if needed later (psycopg2, etc.)
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy alembic.ini and the entire app tree (which includes app/db/alembic)
COPY alembic.ini ./alembic.ini
COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
