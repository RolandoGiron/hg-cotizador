
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
    ASK_NUM_JOBS,
    COLLECT_JOB_DESCRIPTIONS,
    ASK_TOTAL_JOB_PRICE,
    ASK_NUM_MATERIALS,
    COLLECT_MATERIAL_DESCRIPTIONS,
    ASK_TOTAL_MATERIAL_PRICE,
) = range(7)

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
        data["total_jobs_price"] = float(data["total_jobs_price"])
    if "total_materials_price" in data:
        data["total_materials_price"] = float(data["total_materials_price"])
    return data


def set_user_data(user_id, key, value):
    """Guarda datos del usuario en Redis."""
    if isinstance(value, (dict, list)):
        value = json.dumps(value)
    r.hset(f"user:{user_id}", key, value)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia la conversación y pide el nombre del cliente."""
    user_id = update.message.from_user.id
    r.delete(f"user:{user_id}")  # Limpiar datos de conversaciones anteriores
    await update.message.reply_text(
        "Hola! Vamos a crear una cotización. Por favor, dime el nombre del cliente."
    )
    return CLIENT_NAME


async def client_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el nombre del cliente y pide el número de trabajos."""
    user_id = update.message.from_user.id
    set_user_data(user_id, "client_name", update.message.text)
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
        set_user_data(user_id, "jobs", [])  # Initialize jobs list
        set_user_data(user_id, "jobs_done", 0)
        await update.message.reply_text(
            f"Entendido, {num} trabajos. Ahora, por favor, introduce la descripción del trabajo 1."
        )
        return COLLECT_JOB_DESCRIPTIONS
    except ValueError:
        await update.message.reply_text("Eso no parece un número. Por favor, introduce un número válido.")
        return ASK_NUM_JOBS


async def collect_job_descriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda la descripción de un trabajo y pide el siguiente, o el precio total de los trabajos."""
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)

    description = update.message.text.strip()
    jobs = user_data.get("jobs", [])
    jobs.append({"description": description, "price": 0})  # Price will be added later
    set_user_data(user_id, "jobs", jobs)

    jobs_done = int(user_data.get("jobs_done", 0)) + 1
    set_user_data(user_id, "jobs_done", jobs_done)

    num_jobs_total = int(user_data["num_jobs"])
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


async def ask_total_job_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el precio total de los trabajos y pide el número de materiales."""
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)

    try:
        total_jobs_price = float(update.message.text.replace("$", "").strip())
        set_user_data(user_id, "total_jobs_price", total_jobs_price)
    except ValueError:
        await update.message.reply_text("Eso no parece un precio válido. Por favor, introduce un número.")
        return ASK_TOTAL_JOB_PRICE

    await update.message.reply_text("Perfecto. ¿Cuántos materiales se van a utilizar?")
    return ASK_NUM_MATERIALS


async def ask_num_materials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el número de materiales y pide la descripción del primer material."""
    user_id = update.message.from_user.id
    try:
        num = int(update.message.text)
        if num <= 0:
            await update.message.reply_text("Por favor, introduce un número válido y positivo.")
            return ASK_NUM_MATERIALS
        set_user_data(user_id, "num_materials", num)
        set_user_data(user_id, "materials", [])  # Initialize materials list
        set_user_data(user_id, "materials_done", 0)
        await update.message.reply_text(
            f"Entendido, {num} materiales. Ahora, por favor, introduce la descripción del material 1."
        )
        return COLLECT_MATERIAL_DESCRIPTIONS
    except ValueError:
        await update.message.reply_text("Eso no parece un número. Por favor, introduce un número válido.")
        return ASK_NUM_MATERIALS


async def collect_material_descriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda la descripción de un material y pide el siguiente, o el precio total de los materiales."""
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)

    description = update.message.text.strip()
    materials = user_data.get("materials", [])
    materials.append({"description": description, "price": 0})  # Price will be added later
    set_user_data(user_id, "materials", materials)

    materials_done = int(user_data.get("materials_done", 0)) + 1
    set_user_data(user_id, "materials_done", materials_done)

    num_materials_total = int(user_data["num_materials"])
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


async def ask_total_material_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el precio total de los materiales, calcula totales y genera el PDF."""
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)

    try:
        total_materials_price = float(update.message.text.replace("$", "").strip())
        set_user_data(user_id, "total_materials_price", total_materials_price)
        user_data = get_user_data(user_id) # Re-fetch user_data to get the updated value
    except ValueError:
        await update.message.reply_text("Eso no parece un precio válido. Por favor, introduce un número.")
        return ASK_TOTAL_MATERIAL_PRICE

    # Calculate grand total
    total_jobs = user_data["total_jobs_price"]
    total_materials = user_data["total_materials_price"]
    grand_total = total_jobs + total_materials

    # Update job and material prices in the lists (they were initialized with 0)
    jobs_list = user_data["jobs"]
    # Distribute total job price evenly among jobs for display purposes, or keep 0 if not needed
    # For now, we'll just pass the total job price to the PDF, and individual job prices will remain 0
    # if the template expects individual prices, we'll need to adjust the template or this logic.
    # For now, let's assume the template will use total_jobs and total_materials directly.

    # Prepare data for PDF
    pdf_data = {
        "client_name": user_data["client_name"],
        "date": "30/06/2025",  # Consider dynamic date
        "jobs": jobs_list,
        "materials": user_data["materials"],
        "total_jobs": total_jobs,
        "total_materials": total_materials,
        "grand_total": grand_total,
    }

    # Call PDF service
    try:
        response = requests.post(PDF_SERVICE_URL, json=pdf_data)
        if response.status_code == 200:
            await update.message.reply_document(
                document=response.content,
                filename=f"cotizacion_{user_data['client_name']}.pdf",
                caption="¡Aquí está tu cotización!",
            )
        else:
            await update.message.reply_text(
                f"Hubo un error al generar el PDF (código: {response.status_code}). Por favor, inténtalo de nuevo."
            )
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"No se pudo conectar al servicio de PDF: {e}")

    # Clean up and end
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
            ASK_NUM_JOBS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_num_jobs)],
            COLLECT_JOB_DESCRIPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_job_descriptions)],
            ASK_TOTAL_JOB_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_total_job_price)],
            ASK_NUM_MATERIALS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_num_materials)],
            COLLECT_MATERIAL_DESCRIPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_material_descriptions)],
            ASK_TOTAL_MATERIAL_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_total_material_price)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
