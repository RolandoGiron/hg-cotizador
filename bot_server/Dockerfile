# Usar una imagen base oficial de Python
FROM python:3.11-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Crear un usuario no-root
RUN useradd --create-home appuser

# Copiar el archivo de dependencias e instalarlas como root
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de la aplicación y cambiar propietario
COPY --chown=appuser:appuser . .

# Cambiar al usuario no-root
USER appuser

# Comando para correr la aplicación
CMD ["python", "main.py"]
