# The sandbox image: Python and the fixed stack (decision 0002), nothing else.
# Build once: docker build -t w2-sandbox runtime/sandbox
FROM python:3.12-slim
# Same versions as uv.lock, so code behaves the same inside and outside the sandbox.
RUN pip install --no-cache-dir fastapi==0.143.3 uvicorn==0.54.0 sqlmodel==0.0.48 httpx==0.28.1 pytest==9.1.1
# An ordinary user with no special rights; the code never runs as the administrator (root).
RUN useradd --uid 1000 --no-create-home sandbox
USER sandbox
WORKDIR /app
