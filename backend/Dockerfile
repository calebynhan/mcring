# Build from the repo root (the shared codecs live outside backend/):
#   docker build -f backend/Dockerfile -t mcring-backend .
FROM python:3.12-slim
COPY python/mcring_core /srv/python/mcring_core
# requirements.txt installs the shared codecs with `-e ../python/mcring_core`; pip resolves that
# path against the current directory, so the install runs from /srv/backend.
WORKDIR /srv/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
