# HG Cotizador Bot

El HG Cotizador Bot es una aplicación que permite a los usuarios generar cotizaciones en formato PDF a través de una interacción conversacional en Telegram. La solución está diseñada con una arquitectura modular, separando la lógica del bot de la generación del documento para mayor robustez y escalabilidad.

## Arquitectura

La aplicación se compone de cuatro componentes principales que trabajan de forma coordinada:

1.  **Bot de Telegram (Interfaz):** La interfaz directa con el usuario. Se configura a través de BotFather y utiliza la API de Telegram para la comunicación.

2.  **Servidor del Bot (Lógica de Negocio):** Un backend en Python que gestiona la conversación con el usuario, interpreta comandos, recopila datos, almacena el estado de la conversación en Redis y orquesta la generación del PDF.

3.  **Servicio de Generación de PDF (Microservicio):** Un microservicio especializado en la creación de documentos PDF a partir de plantillas HTML y datos JSON.

4.  **Base de Datos (Persistencia):** Una base de datos NoSQL (Google Firestore) para almacenar, consultar y gestionar las cotizaciones generadas.

## Características

*   Generación de cotizaciones en PDF mediante un bot de Telegram.
*   Interacción conversacional para la recopilación de datos.
*   Soporte para precios por ítem o totales.
*   Cálculo de IVA opcional.
*   Términos y condiciones personalizables.
*   Resumen de la cotización para revisión antes de generar el PDF.
*   Edición de ítems (trabajos y materiales) después del resumen.
*   Persistencia de cotizaciones en Google Firestore.
*   Comandos para listar, ver, actualizar y eliminar cotizaciones.
*   Arquitectura modular y escalable.

## Tecnologías Utilizadas

### Servidor del Bot
*   **Python**
*   `python-telegram-bot`: Para la interacción con la API de Telegram.
*   `requests`: Para realizar llamadas HTTP al servicio de PDF.
*   `redis`: Para almacenar el estado de la conversación.
*   `google-cloud-firestore`: Para la comunicación con la base de datos.

### Servicio de Generación de PDF
*   **Python**
*   `FastAPI`: Framework web para construir la API REST.
*   `uvicorn`: Servidor ASGI para ejecutar FastAPI.
*   `Jinja2`: Motor de plantillas para renderizar HTML.
*   `WeasyPrint`: Librería para convertir HTML y CSS a PDF.

### Base de Datos
*   **Google Firestore**: Base de datos NoSQL para persistencia de las cotizaciones.

## Diagrama de Estados del Bot (Actualizado)

```mermaid
stateDiagram-v2
    [*] --> CLIENT_NAME
    CLIENT_NAME --> ASK_ADD_JOB_PRICES
    ASK_ADD_JOB_PRICES --> ASK_NUM_JOBS
    ASK_NUM_JOBS --> COLLECT_JOB_DESCRIPTIONS
    COLLECT_JOB_DESCRIPTIONS --> COLLECT_JOB_PRICE : per_job_prices = true
    COLLECT_JOB_DESCRIPTIONS --> COLLECT_JOB_DESCRIPTIONS : more jobs
    COLLECT_JOB_DESCRIPTIONS --> ASK_TOTAL_JOB_PRICE : per_job_prices = false
    COLLECT_JOB_PRICE --> COLLECT_JOB_DESCRIPTIONS : more jobs
    COLLECT_JOB_PRICE --> ASK_ADD_MATERIAL_PRICES : all jobs done
    ASK_TOTAL_JOB_PRICE --> ASK_ADD_MATERIAL_PRICES
    ASK_ADD_MATERIAL_PRICES --> ASK_NUM_MATERIALS
    ASK_NUM_MATERIALS --> COLLECT_MATERIAL_DESCRIPTIONS
    ASK_NUM_MATERIALS --> ASK_FOR_VAT : num_materials = 0
    COLLECT_MATERIAL_DESCRIPTIONS --> COLLECT_MATERIAL_PRICE : per_material_prices = true
    COLLECT_MATERIAL_DESCRIPTIONS --> COLLECT_MATERIAL_DESCRIPTIONS : more materials
    COLLECT_MATERIAL_DESCRIPTIONS --> ASK_TOTAL_MATERIAL_PRICE : per_material_prices = false
    COLLECT_MATERIAL_PRICE --> COLLECT_MATERIAL_DESCRIPTIONS : more materials
    COLLECT_MATERIAL_PRICE --> ASK_FOR_VAT : all materials done
    ASK_TOTAL_MATERIAL_PRICE --> ASK_FOR_VAT
    ASK_FOR_VAT --> ASK_WORKING_DAYS
    ASK_WORKING_DAYS --> ASK_USE_DEFAULT_TERMS
    ASK_USE_DEFAULT_TERMS --> REVIEW_SUMMARY : use_default = true
    ASK_USE_DEFAULT_TERMS --> REVIEW_TERM_ACTION : use_default = false
    REVIEW_TERM_ACTION --> MODIFY_TERM : action = 'modificar'
    REVIEW_TERM_ACTION --> REVIEW_TERM_ACTION : more terms
    MODIFY_TERM --> REVIEW_TERM_ACTION
    REVIEW_TERM_ACTION --> ASK_ADD_EXTRA_TERM : all terms reviewed
    ASK_ADD_EXTRA_TERM --> ADD_EXTRA_TERM : add_more = true
    ASK_ADD_EXTRA_TERM --> REVIEW_SUMMARY : add_more = false
    ADD_EXTRA_TERM --> ASK_ADD_EXTRA_TERM
    REVIEW_SUMMARY --> SELECT_EDIT_ITEM : answer = 'no'
    REVIEW_SUMMARY --> generate_pdf : answer = 'si'
    SELECT_EDIT_ITEM --> CHOOSE_EDIT_FIELD
    CHOOSE_EDIT_FIELD --> EDIT_ITEM_DESCRIPTION
    CHOOSE_EDIT_FIELD --> EDIT_ITEM_PRICE
    EDIT_ITEM_DESCRIPTION --> EDIT_ITEM_PRICE : edit_next = 'price'
    EDIT_ITEM_DESCRIPTION --> REVIEW_SUMMARY
    EDIT_ITEM_PRICE --> REVIEW_SUMMARY
    generate_pdf --> ASK_SAVE_QUOTE
    ASK_SAVE_QUOTE --> [*]
```

## TODO

### ✅ Completado

*   **Core:** Flujo conversacional para crear cotizaciones.
*   **Core:** Generación de PDF con `pdf-service`.
*   **Feature:** Soporte para precios por ítem o precios totales.
*   **Feature:** Cálculo de IVA.
*   **Feature:** Personalización de términos y condiciones.
*   **Feature:** Resumen y edición de la cotización antes de la creación del PDF.
*   **Persistence:** Guardar, listar, ver, actualizar y eliminar cotizaciones en Firestore.
*   **Infra:** Configuración mediante `config.ini` y variables de entorno.
*   **Infra:** Almacenamiento de estado de sesión en Redis.
*   **Feature:** Añadido un comando `/help` con la lista de comandos disponibles y su descripción.
*   **Feature:** Definidos los estados de la cotización (`Inicial`, `Enviada`, `Aceptada`, `Rechazada`). El estado por defecto al guardar es `Inicial`.

### ⏳ En Proceso

*   **Feature:** En el handler de /actualizar_cotizacion , se requiere que se cambie,  a /actualizar_cotizacion <ID_cotizacion>, que vaya recorriendo cada uno de los items de los trabajos y de los materiales, y pregunte si se quiere modificar la descripcion o el precio.
 

### Backlog

*   **Feature:** Agregar soporte para múltiples usuarios concurrentes con datos aislados.
*   **Refactor:** Separar la lógica del `ConversationHandler` en módulos más pequeños.
*   **Testing:** Añadir pruebas unitarias y de integración.
*   **Feature:** Mejorar el manejo de errores y la validación de entradas en la conversación.