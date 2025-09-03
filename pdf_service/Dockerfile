# Usar una imagen base oficial de Python
FROM python:3.11-slim

# Instalar dependencias de sistema para WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends     libpango-1.0-0     libpangoft2-1.0-0     libharfbuzz-subset0     && rm -rf /var/lib/apt/lists/*

# Establecer el directorio de trabajo
WORKDIR /app

# Crear un usuario no-root
RUN useradd --create-home appuser
RUN chown -R appuser:appuser /app

# Copiar el archivo de dependencias e instalarlas
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de la aplicación
COPY --chown=appuser:appuser . .

# Cambiar al usuario no-root
USER appuser

# Exponer el puerto en el que corre la aplicación
EXPOSE 8000

# Comando para correr la aplicación
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]