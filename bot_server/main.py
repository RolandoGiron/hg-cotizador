import os
import configparser
import redis
import requests
import json
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Estados de la conversación
(
    CLIENT_NAME,
    ASK_ADD_JOB_PRICES,
    ASK_NUM_JOBS,
    COLLECT_JOB_DESCRIPTIONS,
    COLLECT_JOB_PRICE,
    ASK_TOTAL_JOB_PRICE,
    ASK_ADD_MATERIAL_PRICES,
    ASK_NUM_MATERIALS,
    COLLECT_MATERIAL_DESCRIPTIONS,
    COLLECT_MATERIAL_PRICE,
    ASK_TOTAL_MATERIAL_PRICE,
    ASK_FOR_VAT,
) = range(12)

# Configuración
config = configparser.ConfigParser()
config.read("../config.ini")
TOKEN = os.getenv("TELEGRAM_TOKEN")
PDF_SERVICE_URL = config["pdf_service"]["url"]

# Redis
r = redis.Redis(decode_responses=True)


def get_user_data(user_id):
    """Obtiene los datos del usuario de Redis."""
    data = r.hgetall(f"user:{user_id}")
    if "jobs" in data:
        data["jobs"] = json.loads(data["jobs"])
    else:
        data["jobs"] = []
    if "materials" in data:
        data["materials"] = json.loads(data["materials"])
    else:
        data["materials"] = []
    if "total_jobs_price" in data:
        try:
            data["total_jobs_price"] = float(data["total_jobs_price"])
        except ValueError:
            data["total_jobs_price"] = 0.0
    if "total_materials_price" in data:
        try:
            data["total_materials_price"] = float(data["total_materials_price"])
        except ValueError:
            data["total_materials_price"] = 0.0
    return data


def set_user_data(user_id, key, value):
    """Guarda datos del usuario en Redis."""
    if isinstance(value, (dict, list)):
        value = json.dumps(value)
    r.hset(f"user:{user_id}", key, value)


def _parse_yes_no(text: str) -> bool:
    t = text.strip().lower()
    return t in ("si", "sí", "s", "yes", "y")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia la conversación y pide el nombre del cliente."""
    user_id = update.message.from_user.id
    r.delete(f"user:{user_id}")  # Limpiar datos de conversaciones anteriores
    await update.message.reply_text(
        "¡Hola! Vamos a crear una cotización. Por favor, dime el nombre del cliente."
    )
    return CLIENT_NAME


async def client_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el nombre del cliente y pregunta si desea precio por cada trabajo."""
    user_id = update.message.from_user.id
    set_user_data(user_id, "client_name", update.message.text.strip())
    await update.message.reply_text(
        "¿Deseas ingresar precio por cada trabajo? (Si/No)"
    )
    return ASK_ADD_JOB_PRICES


async def ask_add_job_prices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda preferencia de precios por trabajo y pide número de trabajos."""
    user_id = update.message.from_user.id
    per_item = _parse_yes_no(update.message.text)
    set_user_data(user_id, "per_job_prices", "true" if per_item else "false")
    await update.message.reply_text("Perfecto. ¿Cuántos trabajos se van a realizar?")
    return ASK_NUM_JOBS


async def ask_num_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el número de trabajos y pide la descripción del primer trabajo."""
    user_id = update.message.from_user.id
    try:
        num = int(update.message.text)
        if num <= 0:
            await update.message.reply_text("Por favor, introduce un número válido y positivo.")
            return ASK_NUM_JOBS
        set_user_data(user_id, "num_jobs", num)
        set_user_data(user_id, "jobs", [])  # Inicializa lista de trabajos
        set_user_data(user_id, "jobs_done", 0)
        await update.message.reply_text(
            f"Entendido, {num} trabajos. Ahora, por favor, introduce la descripción del trabajo 1."
        )
        return COLLECT_JOB_DESCRIPTIONS
    except ValueError:
        await update.message.reply_text("Eso no parece un número. Por favor, introduce un número válido.")
        return ASK_NUM_JOBS


async def collect_job_descriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda la descripción de un trabajo y pide precio si aplica o el siguiente trabajo."""
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)

    description = update.message.text.strip()
    jobs = user_data.get("jobs", [])
    jobs.append({"description": description, "price": 0.0})
    set_user_data(user_id, "jobs", jobs)

    per_item = user_data.get("per_job_prices") == "true"
    num_jobs_total = int(user_data["num_jobs"]) if "num_jobs" in user_data else len(jobs)

    if per_item:
        # Pedir el precio para este trabajo
        job_index = len(jobs)
        await update.message.reply_text(
            f"Introduce el precio del trabajo {job_index}:"
        )
        return COLLECT_JOB_PRICE
    else:
        # Marcar trabajo como completado
        jobs_done = int(user_data.get("jobs_done", 0)) + 1
        set_user_data(user_id, "jobs_done", jobs_done)
        if jobs_done < num_jobs_total:
            await update.message.reply_text(
                f"Trabajo {jobs_done} guardado. Ahora introduce la descripción del trabajo {jobs_done + 1}."
            )
            return COLLECT_JOB_DESCRIPTIONS
        else:
            await update.message.reply_text(
                "Todas las descripciones de los trabajos han sido guardadas. Ahora, por favor, introduce el precio TOTAL de todos los trabajos."
            )
            return ASK_TOTAL_JOB_PRICE


async def collect_job_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el precio del último trabajo ingresado y continúa el flujo."""
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)
    try:
        price = float(update.message.text.replace("$", "").strip())
    except ValueError:
        await update.message.reply_text("Eso no parece un precio válido. Por favor, introduce un número.")
        return COLLECT_JOB_PRICE

    jobs = user_data.get("jobs", [])
    if not jobs:
        await update.message.reply_text("Primero introduce la descripción del trabajo.")
        return COLLECT_JOB_DESCRIPTIONS

    # Actualiza el precio del último trabajo
    jobs[-1]["price"] = price
    set_user_data(user_id, "jobs", jobs)

    # Incrementa trabajos completados
    jobs_done = int(user_data.get("jobs_done", 0)) + 1
    set_user_data(user_id, "jobs_done", jobs_done)

    num_jobs_total = int(user_data.get("num_jobs", len(jobs)))
    if jobs_done < num_jobs_total:
        await update.message.reply_text(
            f"Trabajo {jobs_done} guardado. Ahora introduce la descripción del trabajo {jobs_done + 1}."
        )
        return COLLECT_JOB_DESCRIPTIONS
    else:
        # Todos los trabajos listos: calcula total y pasa a preferencia de materiales
        total_jobs_price = sum(j.get("price", 0) for j in jobs)
        set_user_data(user_id, "total_jobs_price", total_jobs_price)
        await update.message.reply_text("¿Deseas ingresar precio por cada material? (Si/No)")
        return ASK_ADD_MATERIAL_PRICES


async def ask_total_job_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el precio total de los trabajos y pregunta preferencia para materiales."""
    user_id = update.message.from_user.id
    try:
        total_jobs_price = float(update.message.text.replace("$", "").strip())
        set_user_data(user_id, "total_jobs_price", total_jobs_price)
    except ValueError:
        await update.message.reply_text("Eso no parece un precio válido. Por favor, introduce un número.")
        return ASK_TOTAL_JOB_PRICE

    await update.message.reply_text("Perfecto. ¿Deseas ingresar precio por cada material? (Si/No)")
    return ASK_ADD_MATERIAL_PRICES


async def ask_add_material_prices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda preferencia de precios por material y pide número de materiales."""
    user_id = update.message.from_user.id
    per_item = _parse_yes_no(update.message.text)
    set_user_data(user_id, "per_material_prices", "true" if per_item else "false")
    await update.message.reply_text("¿Cuántos materiales se van a utilizar?")
    return ASK_NUM_MATERIALS


async def ask_num_materials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el número de materiales y pide la descripción del primer material."""
    user_id = update.message.from_user.id
    try:
        num = int(update.message.text)
        if num < 0:
            await update.message.reply_text("Por favor, introduce un número válido y positivo.")
            return ASK_NUM_MATERIALS
        if num == 0:
            set_user_data(user_id, "num_materials", 0)
            set_user_data(user_id, "total_materials_price", 0)
            await update.message.reply_text("No se agregarán materiales. Necesitas agregar el impuesto del IVA (Si/No)?")
            return ASK_FOR_VAT
        set_user_data(user_id, "num_materials", num)
        set_user_data(user_id, "materials", [])  # Inicializa lista de materiales
        set_user_data(user_id, "materials_done", 0)
        await update.message.reply_text(
            f"Entendido, {num} materiales. Ahora, por favor, introduce la descripción del material 1."
        )
        return COLLECT_MATERIAL_DESCRIPTIONS
    except ValueError:
        await update.message.reply_text("Eso no parece un número. Por favor, introduce un número válido.")
        return ASK_NUM_MATERIALS


async def collect_material_descriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda la descripción de un material y pide precio si aplica o el siguiente material."""
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)

    description = update.message.text.strip()
    materials = user_data.get("materials", [])
    materials.append({"description": description, "price": 0.0})
    set_user_data(user_id, "materials", materials)

    per_item = user_data.get("per_material_prices") == "true"
    num_materials_total = int(user_data["num_materials"]) if "num_materials" in user_data else len(materials)

    if per_item:
        material_index = len(materials)
        await update.message.reply_text(
            f"Introduce el precio del material {material_index}:"
        )
        return COLLECT_MATERIAL_PRICE
    else:
        materials_done = int(user_data.get("materials_done", 0)) + 1
        set_user_data(user_id, "materials_done", materials_done)
        if materials_done < num_materials_total:
            await update.message.reply_text(
                f"Material {materials_done} guardado. Ahora introduce la descripción del material {materials_done + 1}."
            )
            return COLLECT_MATERIAL_DESCRIPTIONS
        else:
            await update.message.reply_text(
                "Todas las descripciones de los materiales han sido guardadas. Ahora, por favor, introduce el precio TOTAL de todos los materiales."
            )
            return ASK_TOTAL_MATERIAL_PRICE


async def collect_material_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el precio del último material ingresado y continúa el flujo."""
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)
    try:
        price = float(update.message.text.replace("$", "").strip())
    except ValueError:
        await update.message.reply_text("Eso no parece un precio válido. Por favor, introduce un número.")
        return COLLECT_MATERIAL_PRICE

    materials = user_data.get("materials", [])
    if not materials:
        await update.message.reply_text("Primero introduce la descripción del material.")
        return COLLECT_MATERIAL_DESCRIPTIONS

    materials[-1]["price"] = price
    set_user_data(user_id, "materials", materials)

    materials_done = int(user_data.get("materials_done", 0)) + 1
    set_user_data(user_id, "materials_done", materials_done)

    num_materials_total = int(user_data.get("num_materials", len(materials)))
    if materials_done < num_materials_total:
        await update.message.reply_text(
            f"Material {materials_done} guardado. Ahora introduce la descripción del material {materials_done + 1}."
        )
        return COLLECT_MATERIAL_DESCRIPTIONS
    else:
        total_materials_price = sum(m.get("price", 0) for m in materials)
        set_user_data(user_id, "total_materials_price", total_materials_price)
        await update.message.reply_text("Necesitas agregar el impuesto del IVA (Si/No)?")
        return ASK_FOR_VAT


async def ask_total_material_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el precio total de los materiales y pide el IVA."""
    user_id = update.message.from_user.id
    try:
        total_materials_price = float(update.message.text.replace("$", "").strip())
        set_user_data(user_id, "total_materials_price", total_materials_price)
    except ValueError:
        await update.message.reply_text("Eso no parece un precio válido. Por favor, introduce un número.")
        return ASK_TOTAL_MATERIAL_PRICE

    await update.message.reply_text("Necesitas agregar el impuesto del IVA (Si/No)?")
    return ASK_FOR_VAT


async def ask_for_vat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda la respuesta sobre el IVA y procesa el PDF."""
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)
    response = update.message.text.strip().lower()

    if response in ["si", "sí"]:
        set_user_data(user_id, "vat", "true")
    else:
        set_user_data(user_id, "vat", "false")

    return await generate_pdf(update, context)


async def generate_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Calcula totales y genera el PDF."""
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)

    jobs_list = user_data.get("jobs", [])
    materials_list = user_data.get("materials", [])

    per_job_prices = user_data.get("per_job_prices") == "true"
    per_material_prices = user_data.get("per_material_prices") == "true"

    # Calcular totales
    total_jobs = sum(j.get("price", 0) for j in jobs_list) if per_job_prices else float(user_data.get("total_jobs_price", 0))
    total_materials = sum(m.get("price", 0) for m in materials_list) if per_material_prices else float(user_data.get("total_materials_price", 0))
    subtotal = total_jobs + total_materials

    vat_included = user_data.get("vat") == "true"
    if vat_included:
        vat = round(subtotal * 0.13, 2)
        grand_total = round(subtotal + vat, 2)
    else:
        vat = 0
        grand_total = round(subtotal, 2)

    # Preparar datos para PDF
    from datetime import datetime
    pdf_data = {
        "client_name": user_data.get("client_name", ""),
        "date": datetime.now().strftime("%d/%m/%Y"),
        "jobs": jobs_list,
        "materials": materials_list,
        "total_jobs": total_jobs,
        "total_materials": total_materials,
        "subtotal": subtotal,
        "vat": vat,
        "grand_total": grand_total,
        "show_job_prices": per_job_prices,
        "show_material_prices": per_material_prices,
    }

    # Llamar servicio PDF
    try:
        response = requests.post(PDF_SERVICE_URL, json=pdf_data)
        if response.status_code == 200:
            await update.message.reply_document(
                document=response.content,
                filename=f"cotizacion_{user_data.get('client_name','cliente')}.pdf",
                caption="¡Aquí está tu cotización!",
            )
        else:
            await update.message.reply_text(
                f"Hubo un error al generar el PDF (código: {response.status_code}). Por favor, inténtalo de nuevo."
            )
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"No se pudo conectar al servicio de PDF: {e}")

    # Limpiar y terminar
    r.delete(f"user:{user_id}")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la conversación y limpia los datos."""
    user_id = update.message.from_user.id
    r.delete(f"user:{user_id}")
    await update.message.reply_text("Conversación cancelada.")
    return ConversationHandler.END


def main() -> None:
    """Inicia el bot."""
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CLIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_name)],
            ASK_ADD_JOB_PRICES: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_add_job_prices)],
            ASK_NUM_JOBS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_num_jobs)],
            COLLECT_JOB_DESCRIPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_job_descriptions)],
            COLLECT_JOB_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_job_price)],
            ASK_TOTAL_JOB_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_total_job_price)],
            ASK_ADD_MATERIAL_PRICES: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_add_material_prices)],
            ASK_NUM_MATERIALS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_num_materials)],
            COLLECT_MATERIAL_DESCRIPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_material_descriptions)],
            COLLECT_MATERIAL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_material_price)],
            ASK_TOTAL_MATERIAL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_total_material_price)],
            ASK_FOR_VAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_for_vat)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
