# Conceptualización y Arquitectura: HG Cotizador Bot

---

## Resumen de la Arquitectura

La solución se divide en cuatro componentes principales que trabajan juntos:

1.  **El Bot de Telegram (Interfaz):** La interfaz con la que el usuario interactúa. No requiere desarrollo, solo configuración.
2.  **El Servidor del Bot (Lógica de Negocio):** Un servicio de backend que escucha los mensajes de Telegram, gestiona la conversación (usando Redis para el estado de la sesión) y se comunica con los otros servicios.
3.  **El Servicio de Generación de PDF (Microservicio):** Un microservicio especializado cuya única responsabilidad es recibir datos, rellenar una plantilla y devolver un archivo PDF.
4.  **La Base de Datos (Persistencia):** Una base de datos NoSQL (Google Firestore) que almacena todas las cotizaciones generadas para su consulta y gestión futura.

Separar estos componentes hace que el sistema sea más robusto, escalable y fácil de mantener.

---

## Diagrama de Componentes (Arquitectura Actual)

Este diagrama muestra los componentes clave de la solución y cómo interactúan entre sí.

```mermaid
graph TD
    subgraph "User Interface"
        U[<font size=5>👤</font><br>Usuario en Telegram]
    end

    subgraph "Infraestructura Cloud"
        subgraph "Bot Server (Python)"
            direction LR
            BH[Bot Handler<br><i>python-telegram-bot</i>]
            CH[Conversation Logic<br><i>main.py</i>]
            FC[Firebase Client<br><i>firebase_client.py</i>]
            RC[Redis Client<br><i>redis-py</i>]
        end

        subgraph "PDF Service (FastAPI)"
            direction LR
            API[API Endpoint<br><i>/api/v1/generate-pdf</i>]
            JIN[Template Engine<br><i>Jinja2</i>]
            PDF[PDF Generator<br><i>WeasyPrint</i>]
        end

        subgraph "Databases"
            FS[<font size=5>🔥</font><br><b>Firestore</b><br><i>Base de Datos de Cotizaciones</i>]
            RD[(<font size=5>💾</font><br><b>Redis</b><br><i>Base de Datos de Sesiones</i>)]
        end
    end

    U -- HTTPS --> BH
    BH -- Interacts with --> CH
    CH -- Stores/Retrieves Session --> RC
    CH -- Calls --> FC
    CH -- HTTP Request --> API
    FC -- CRUD Operations --> FS
    RC -- Manages State --> RD
    API -- Uses --> JIN
    JIN -- Renders --> PDF
```

---

## Diagrama de Flujo de Alto Nivel (Actualizado)

Este diagrama de secuencia muestra el flujo de una conversación completa, desde el inicio hasta la generación del PDF y su almacenamiento en la base de datos.

```mermaid
sequenceDiagram
    participant Usuario
    participant Bot de Telegram
    participant Servidor del Bot
    participant Servicio PDF
    participant Firestore

    Usuario->>Bot de Telegram: /start
    Bot de Telegram->>Servidor del Bot: Notifica inicio de conversación
    Servidor del Bot->>Bot de Telegram: Pide nombre del cliente
    Bot de Telegram->>Usuario: Muestra pregunta

    Note right of Usuario: El usuario responde a todas las preguntas...

    Usuario->>Bot de Telegram: Envía última respuesta
    Bot de Telegram->>Servidor del Bot: Notifica respuesta
    Servidor del Bot->>Servidor del Bot: Construye el resumen de la cotización
    Servidor del Bot->>Bot de Telegram: Envía resumen para revisión
    Bot de Telegram->>Usuario: Muestra resumen

    Usuario->>Bot de Telegram: Confirma que el resumen es correcto ("Si")
    Bot de Telegram->>Servidor del Bot: Notifica confirmación
    
    Servidor del Bot->>Servicio PDF: POST /api/v1/generate-pdf con datos (JSON)
    Servicio PDF->>Servicio PDF: Rellena plantilla HTML y convierte a PDF
    Servicio PDF->>Servidor del Bot: Devuelve archivo PDF

    Servidor del Bot->>Bot de Telegram: Envía documento PDF
    Bot de Telegram->>Usuario: Entrega el PDF

    Servidor del Bot->>Bot de Telegram: Pregunta si desea guardar la cotización
    Bot de Telegram->>Usuario: Muestra pregunta

    Usuario->>Bot de Telegram: Confirma que desea guardar ("Si")
    Bot de Telegram->>Servidor del Bot: Notifica confirmación

    Servidor del Bot->>Firestore: Llama a save_quote() con los datos
    Firestore->>Firestore: Almacena la cotización
    Firestore->>Servidor del Bot: Devuelve ID de la cotización
    Servidor del Bot->>Bot de Telegram: Envía mensaje de éxito con ID
    Bot de Telegram->>Usuario: Muestra mensaje de éxito
```

---

## Flujo de Trabajo Detallado (Paso a Paso)

1.  **Configuración Inicial:**
    *   Registras tu bot en Telegram usando BotFather para obtener un `TOKEN_API`.
    *   Configuras un proyecto en Google Cloud con Firestore y obtienes las credenciales de servicio.
    *   Desarrollas el Servidor del Bot, el Servicio PDF y la plantilla HTML.

2.  **Inicio de la Conversación:**
    *   El usuario envía el comando `/start`.
    *   El `ConversationHandler` del Servidor del Bot se activa y pide el nombre del cliente.

3.  **Recopilación de Datos:**
    *   El bot guía al usuario a través de una serie de preguntas para recopilar los detalles de la cotización (trabajos, materiales, precios, etc.).
    *   El estado de la conversación se mantiene en **Redis** para no perder el hilo si el bot se reinicia.

4.  **Revisión y Edición:**
    *   Al final de las preguntas, el bot presenta un resumen completo.
    *   El usuario puede solicitar la edición de trabajos o materiales si encuentra un error.

5.  **Generación del PDF:**
    *   Una vez que el usuario aprueba el resumen, el Servidor del Bot envía los datos al Servicio PDF.
    *   El Servicio PDF renderiza la plantilla HTML con los datos y la convierte a un archivo PDF.
    *   El PDF se devuelve al Servidor del Bot.

6.  **Entrega y Almacenamiento:**
    *   El Servidor del Bot envía el PDF al usuario a través de Telegram.
    *   Se le pregunta al usuario si desea guardar la cotización.
    *   Si la respuesta es afirmativa, el Servidor del Bot invoca al cliente de **Firestore** para guardar una copia de la cotización en la base de datos, asignándole un ID único.
    *   El bot confirma que la cotización ha sido guardada.