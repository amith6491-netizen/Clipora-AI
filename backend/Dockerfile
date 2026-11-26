FROM python:3.12-slim

WORKDIR /app

# Retry transient Debian mirror drops and avoid pulling unnecessary X11/Mesa/LLVM packages (libgl1)
RUN apt-get -o Acquire::Retries=5 -o Acquire::http::Pipeline-Depth=0 -o Acquire::ForceIPv4=true update \
    && apt-get -o Acquire::Retries=5 -o Acquire::http::Pipeline-Depth=0 -o Acquire::ForceIPv4=true install -y --no-install-recommends --fix-missing \
        ffmpeg \
        fontconfig \
        fonts-liberation \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated virtual environment inside container (avoids pip root-user warnings)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install CPU-only PyTorch first on Linux to avoid downloading ~2.5GB of unused CUDA packages
RUN pip install --no-cache-dir --retries 5 --timeout 60 \
    --index-url https://download.pytorch.org/whl/cpu torch

COPY requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 60 -r requirements.txt

COPY app ./app
COPY .env.example ./.env

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
