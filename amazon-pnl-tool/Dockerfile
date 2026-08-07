FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Railway: mount a persistent volume at /data and set DATA_DIR=/data so project
# months survive restarts and redeploys.
ENV DATA_DIR=/data

EXPOSE 8770
CMD ["python3", "app.py"]
