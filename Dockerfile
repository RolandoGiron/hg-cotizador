FROM python:3.11-slim as base

# Instalar dependencias de sistema para WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Crear directorios de trabajo
WORKDIR /app
RUN mkdir -p /app/bot_server /app/pdf_service

# Crear usuario no-root
RUN useradd --create-home appuser
RUN chown -R appuser:appuser /app

# Instalar dependencias del bot
COPY bot_server/requirements.txt /app/bot_server/
RUN pip install --no-cache-dir -r /app/bot_server/requirements.txt

# Instalar dependencias del PDF service
COPY pdf_service/requirements.txt /app/pdf_service/
RUN pip install --no-cache-dir -r /app/pdf_service/requirements.txt

# Copiar código fuente
COPY --chown=appuser:appuser bot_server/ /app/bot_server/
COPY --chown=appuser:appuser pdf_service/ /app/pdf_service/
COPY --chown=appuser:appuser config.ini /app/

# Crear configuración de supervisor
RUN echo '[supervisord]' > /etc/supervisor/conf.d/supervisord.conf && \
    echo 'nodaemon=true' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo 'user=root' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo '' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo '[program:pdf_service]' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo 'command=uvicorn main:app --host 0.0.0.0 --port 8000' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo 'directory=/app/pdf_service' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo 'user=appuser' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo 'autostart=true' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo 'autorestart=true' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo 'stdout_logfile=/var/log/pdf_service.log' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo 'stderr_logfile=/var/log/pdf_service_error.log' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo '' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo '[program:bot_server]' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo 'command=python main.py' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo 'directory=/app/bot_server' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo 'user=appuser' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo 'autostart=true' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo 'autorestart=true' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo 'stdout_logfile=/var/log/bot_server.log' >> /etc/supervisor/conf.d/supervisord.conf && \
    echo 'stderr_logfile=/var/log/bot_server_error.log' >> /etc/supervisor/conf.d/supervisord.conf

# Exponer puerto del PDF service
EXPOSE 8000

# Variables de entorno
ENV PDF_SERVICE_URL=http://localhost:8000/api/v1/generate-pdf
ENV REDIS_HOST=localhost
ENV REDIS_PORT=6379

# Comando para iniciar ambos servicios
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]