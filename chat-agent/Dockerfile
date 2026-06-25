FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install torch from the CPU-only wheel index BEFORE the rest of requirements.
# sentence-transformers depends on torch; pinning the CPU wheel here means we
# skip ~4-5GB of nvidia/CUDA libs that we never use in production.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
    torch==2.4.1

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY evaluation ./evaluation
COPY gradio_tester.py ./
COPY README.md ./

EXPOSE 8010 7861

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
