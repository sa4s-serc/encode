FROM python:3.11-slim

WORKDIR /app

# Install WattWise ML backend dependencies
RUN pip install --no-cache-dir \
    numpy \
    pandas \
    scikit-learn \
    xgboost \
    joblib \
    pyyaml \
    requests

# Copy the WattWise python backend (models + scripts)
COPY python/ /app/python/

# Copy the bot source
COPY wattwise-bot/src/ /app/src/

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "/app/src/main.py"]
