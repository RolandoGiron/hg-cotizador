# HG Cotizador Bot

El HG Cotizador Bot es una aplicación que permite a los usuarios generar cotizaciones en formato PDF a través de una interacción conversacional en Telegram. La solución está diseñada con una arquitectura modular, separando la lógica del bot de la generación del documento para mayor robustez y escalabilidad.

## Arquitectura

La aplicación se compone de tres servicios principales que trabajan de forma coordinada:

1.  **Bot de Telegram (Interfaz):** La interfaz directa con el usuario. Se configura a través de BotFather y utiliza la API de Telegram para la comunicación.

2.  **Servidor del Bot (Lógica de Negocio):** Un backend en Python que gestiona la conversación con el usuario, interpreta comandos, recopila datos y orquesta la generación del PDF.

3.  **Servicio de Generación de PDF (Microservicio):** Un microservicio especializado en la creación de documentos PDF a partir de plantillas HTML y datos JSON.

El flujo de trabajo general es el siguiente:

*   El usuario interactúa con el Bot de Telegram.
*   El Servidor del Bot gestiona la conversación, haciendo preguntas y recopilando la información necesaria para la cotización.
*   Una vez que se tienen todos los datos, el Servidor del Bot envía una solicitud al Servicio de Generación de PDF con los datos de la cotización.
*   El Servicio de Generación de PDF procesa los datos, rellena una plantilla HTML, la convierte a PDF y devuelve el archivo al Servidor del Bot.
*   Finalmente, el Servidor del Bot envía el PDF generado al usuario a través de Telegram.

## Características

*   Generación de cotizaciones en PDF mediante un bot de Telegram.
*   Interacción conversacional para la recopilación de datos.
*   Arquitectura modular y escalable.
*   Uso de plantillas HTML para un diseño flexible de las cotizaciones.

## Tecnologías Utilizadas

### Servidor del Bot

*   **Python**
*   `python-telegram-bot`: Para la interacción con la API de Telegram.
*   `requests`: Para realizar llamadas HTTP al servicio de PDF.
*   `redis`: (Opcional, pero recomendado) Para almacenar el estado de la conversación.

### Servicio de Generación de PDF

*   **Python**
*   `FastAPI`: Framework web para construir la API REST.
*   `uvicorn`: Servidor ASGI para ejecutar FastAPI.
*   `Jinja2`: Motor de plantillas para renderizar HTML.
*   `WeasyPrint`: Librería para convertir HTML y CSS a PDF.

## Configuración e Instalación

### Prerrequisitos

*   Python 3.8+
*   pip (gestor de paquetes de Python)
*   Redis (opcional, si se desea persistencia del estado de la conversación)

### Pasos de Instalación

1.  **Clonar el repositorio:**
    ```bash
    git clone https://github.com/your-repo/hg-cotizador.git
    cd hg-cotizador
    ```

2.  **Configurar `config.ini`:**
    Crea un archivo `config.ini` en la raíz del proyecto con la siguiente estructura. Reemplaza `YOUR_TELEGRAM_BOT_TOKEN` con el token obtenido de BotFather en Telegram.

    ```ini
    [telegram]
    token = YOUR_TELEGRAM_BOT_TOKEN

    [pdf_service]
    url = http://127.0.0.1:8000/api/v1/generate-pdf
    ```

3.  **Instalar dependencias del Servicio de PDF:**
    ```bash
    cd pdf_service
    pip install -r requirements.txt
    cd ..
    ```

4.  **Instalar dependencias del Servidor del Bot:**
    ```bash
    cd bot_server
    pip install -r requirements.txt
    cd ..
    ```

## Cómo Ejecutar

Para que la aplicación funcione correctamente, debes iniciar ambos servicios:

1.  **Iniciar el Servicio de Generación de PDF:**
    Abre una terminal, navega a la carpeta `pdf_service` y ejecuta:
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 8000
    ```
    Este servicio se ejecutará en `http://127.0.0.1:8000` por defecto.

2.  **Iniciar el Servidor del Bot:**
    Abre otra terminal, navega a la carpeta `bot_server` y ejecuta:
    ```bash
    python main.py
    ```
    Este servicio se conectará a la API de Telegram y comenzará a escuchar mensajes.

Una vez que ambos servicios estén corriendo, puedes interactuar con tu bot de Telegram. Envía el comando `/crearCotizacion` para iniciar el proceso de generación de una cotización.

## Estructura del Proyecto

```
hg-cotizador/
├───Conceptualizacion.md
├───config.ini
├───diagCompoCotizador.mmd
├───diagramaSeqCotizador.mmd
├───.git/...
├───bot_server/
│   ├───main.py
│   └───requirements.txt
└───pdf_service/
    ├───.gitignore
    ├───main.py
    ├───quote_template.bak.html
    ├───quote_template.html
    ├───requirements.txt
    ├───__pycache__/...
    └───static/
        └───logo.png
```
