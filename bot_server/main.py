
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
    NUM_JOBS,
    JOB_DETAILS,
    MATERIALS_DETAILS,
) = range(4)

# Configuración
config = configparser.ConfigParser()
config.read("../config.ini")
TOKEN = config["telegram"]["token"]
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
    return NUM_JOBS


async def num_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el número de trabajos y pide los detalles del primer trabajo."""
    user_id = update.message.from_user.id
    try:
        num = int(update.message.text)
        if num <= 0:
            await update.message.reply_text("Por favor, introduce un número válido y positivo.")
            return NUM_JOBS
        set_user_data(user_id, "num_jobs", num)
        set_user_data(user_id, "jobs_done", 0)
        await update.message.reply_text(
            f"Entendido, {num} trabajos. Ahora, por favor, introduce la descripción y el precio del trabajo 1.\n"
            "Formato: Descripción del trabajo, $Precio"
        )
        return JOB_DETAILS
    except ValueError:
        await update.message.reply_text("Eso no parece un número. Por favor, introduce un número válido.")
        return NUM_JOBS


async def job_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda los detalles de un trabajo y pide el siguiente, o pasa a los materiales."""
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)

    try:
        description, price_str = update.message.text.split(",")
        price = float(price_str.replace("$", "").strip())
    except ValueError:
        await update.message.reply_text(
            "Formato incorrecto. Por favor, usa: Descripción, $Precio\n"
            "Ejemplo: Cambio de techo, $200"
        )
        return JOB_DETAILS

    jobs = user_data.get("jobs", [])
    jobs.append({"description": description.strip(), "price": price})
    set_user_data(user_id, "jobs", jobs)

    jobs_done = int(user_data.get("jobs_done", 0)) + 1
    set_user_data(user_id, "jobs_done", jobs_done)

    num_jobs_total = int(user_data["num_jobs"])
    if jobs_done < num_jobs_total:
        await update.message.reply_text(
            f"Trabajo {jobs_done} guardado. Ahora introduce los detalles del trabajo {jobs_done + 1}.\n"
            "Formato: Descripción del trabajo, $Precio"
        )
        return JOB_DETAILS
    else:
        await update.message.reply_text(
            "Todos los trabajos han sido guardados. Ahora, por favor, introduce la lista de materiales.\n"
            "Un material por línea, con formato: Material, $Precio\n"
            "Ejemplo:\n100 tejas, $150\nLámina duralita, $200"
        )
        return MATERIALS_DETAILS


async def materials_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda los materiales, calcula totales y genera el PDF."""
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)
    
    materials = []
    total_materials = 0
    lines = update.message.text.strip().split('\n')
    for line in lines:
        try:
            description, price_str = line.split(",")
            price = float(price_str.replace("$", "").strip())
            materials.append({"description": description.strip(), "price": price})
            total_materials += price
        except ValueError:
            await update.message.reply_text(
                f"La línea '{line}' tiene un formato incorrecto. Por favor, usa: Material, $Precio\n"
                "Inténtalo de nuevo con la lista de materiales completa."
            )
            return MATERIALS_DETAILS

    total_jobs = sum(job["price"] for job in user_data["jobs"])
    grand_total = total_jobs + total_materials

    # Preparar datos para el PDF
    pdf_data = {
        "client_name": user_data["client_name"],
        "date": "30/06/2025",
        "jobs": user_data["jobs"],
        "materials": materials,
        "total_jobs": total_jobs,
        "total_materials": total_materials,
        "grand_total": grand_total,
    }

    # Llamar al servicio de PDF
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

    # Limpiar y finalizar
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
            NUM_JOBS: [MessageHandler(filters.TEXT & ~filters.COMMAND, num_jobs)],
            JOB_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, job_details)],
            MATERIALS_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, materials_details)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
