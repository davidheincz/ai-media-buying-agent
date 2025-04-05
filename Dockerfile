FROM python:3.9-slim

WORKDIR /app

# Copy requirements files
COPY web_application/requirements.txt /app/web_application_requirements.txt
COPY document_processor/requirements.txt /app/document_processor_requirements.txt
COPY facebook_ads_manager/requirements.txt /app/facebook_ads_manager_requirements.txt
COPY deepseek_integration/requirements.txt /app/deepseek_integration_requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r /app/web_application_requirements.txt \
    && pip install --no-cache-dir -r /app/document_processor_requirements.txt \
    && pip install --no-cache-dir -r /app/facebook_ads_manager_requirements.txt \
    && pip install --no-cache-dir -r /app/deepseek_integration_requirements.txt \
    && pip install --no-cache-dir gunicorn

# Copy application code
COPY . /app/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run the application
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 web_application.app:app
