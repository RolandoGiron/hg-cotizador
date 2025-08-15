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

# Nuevos términos por defecto (con placeholder para working_days)
DEFAULT_TERMS = [
    "La oferta incluye materiales y mano de obra",
    "Se solicita el 50% de anticipo",
    "El trabajo se realizará en {working_days} días hábiles",
    "Costo de mano de obra no incluye IVA en caso solicite documento fiscal",
    "La oferta incluye desalojo del ripio",
    "Garantía de 6 meses en mano de obra",
    "Vigencia de la cotización: 30 días",
]

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
    ASK_WORKING_DAYS,
    ASK_USE_DEFAULT_TERMS,
    REVIEW_TERM_ACTION,
    MODIFY_TERM,
    ASK_ADD_EXTRA_TERM,
    ADD_EXTRA_TERM,
    REVIEW_SUMMARY,
    SELECT_EDIT_ITEM,
    CHOOSE_EDIT_FIELD,
    EDIT_ITEM_DESCRIPTION,
    EDIT_ITEM_PRICE,
) = range(23)

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
    # Deserializar listas almacenadas como JSON
    for key in ("jobs", "materials", "terms"):
        if key in data:
            try:
                data[key] = json.loads(data[key])
            except Exception:
                data[key] = [] if key != "terms" else []
        else:
            if key != "terms":
                data[key] = []
            else:
                data[key] = []
    # Números
    for key in ("total_jobs_price", "total_materials_price"):
        if key in data:
            try:
                data[key] = float(data[key])
            except ValueError:
                data[key] = 0.0
    if "working_days" in data:
        try:
            data["working_days"] = int(float(data["working_days"]))
        except ValueError:
            data["working_days"] = 0
    return data


def set_user_data(user_id, key, value):
    """Guarda datos del usuario en Redis."""
    if isinstance(value, (dict, list)):
        value = json.dumps(value)
    r.hset(f"user:{user_id}", key, value)


def _parse_yes_no(text: str) -> bool:
    t = text.strip().lower()
    return t in ("si", "sí", "s", "yes", "y")


async def on_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handler cuando expira la conversación por inactividad."""
    try:
        user_id = update.effective_user.id if update and update.effective_user else None
        chat_id = update.effective_chat.id if update and update.effective_chat else None
        if user_id:
            r.delete(f"user:{user_id}")
        if chat_id:
            await context.bot.send_message(
                chat_id=chat_id,
                text="La conversación expiró por inactividad. Escribe /start para comenzar de nuevo."
            )
    except Exception:
        pass
    return ConversationHandler.END


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    r.delete(f"user:{user_id}")
    await update.message.reply_text("¡Hola! Vamos a crear una cotización. Por favor, dime el nombre del cliente.")
    return CLIENT_NAME


async def client_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    set_user_data(user_id, "client_name", update.message.text.strip())
    await update.message.reply_text("¿Deseas ingresar precio por cada trabajo? (Si/No)")
    return ASK_ADD_JOB_PRICES


async def ask_add_job_prices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    per_item = _parse_yes_no(update.message.text)
    set_user_data(user_id, "per_job_prices", "true" if per_item else "false")
    await update.message.reply_text("Perfecto. ¿Cuántos trabajos se van a realizar?")
    return ASK_NUM_JOBS


async def ask_num_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    try:
        num = int(update.message.text)
        if num <= 0:
            await update.message.reply_text("Por favor, introduce un número válido y positivo.")
            return ASK_NUM_JOBS
        set_user_data(user_id, "num_jobs", num)
        set_user_data(user_id, "jobs", [])
        set_user_data(user_id, "jobs_done", 0)
        await update.message.reply_text(f"Entendido, {num} trabajos. Ahora, por favor, introduce la descripción del trabajo 1.")
        return COLLECT_JOB_DESCRIPTIONS
    except ValueError:
        await update.message.reply_text("Eso no parece un número. Por favor, introduce un número válido.")
        return ASK_NUM_JOBS


async def collect_job_descriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)
    description = update.message.text.strip()
    jobs = user_data.get("jobs", [])
    jobs.append({"description": description, "price": 0.0})
    set_user_data(user_id, "jobs", jobs)

    per_item = user_data.get("per_job_prices") == "true"
    num_jobs_total = int(user_data.get("num_jobs", len(jobs)))

    if per_item:
        await update.message.reply_text(f"Introduce el precio del trabajo {len(jobs)}:")
        return COLLECT_JOB_PRICE
    else:
        jobs_done = int(user_data.get("jobs_done", 0)) + 1
        set_user_data(user_id, "jobs_done", jobs_done)
        if jobs_done < num_jobs_total:
            await update.message.reply_text(f"Trabajo {jobs_done} guardado. Ahora introduce la descripción del trabajo {jobs_done + 1}.")
            return COLLECT_JOB_DESCRIPTIONS
        else:
            await update.message.reply_text("Todas las descripciones de los trabajos han sido guardadas. Ahora, por favor, introduce el precio TOTAL de todos los trabajos.")
            return ASK_TOTAL_JOB_PRICE


async def collect_job_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    jobs[-1]["price"] = price
    set_user_data(user_id, "jobs", jobs)

    jobs_done = int(user_data.get("jobs_done", 0)) + 1
    set_user_data(user_id, "jobs_done", jobs_done)

    num_jobs_total = int(user_data.get("num_jobs", len(jobs)))
    if jobs_done < num_jobs_total:
        await update.message.reply_text(f"Trabajo {jobs_done} guardado. Ahora introduce la descripción del trabajo {jobs_done + 1}.")
        return COLLECT_JOB_DESCRIPTIONS
    else:
        total_jobs_price = sum(j.get("price", 0) for j in jobs)
        set_user_data(user_id, "total_jobs_price", total_jobs_price)
        await update.message.reply_text("¿Deseas ingresar precio por cada material? (Si/No)")
        return ASK_ADD_MATERIAL_PRICES


async def ask_total_job_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    user_id = update.message.from_user.id
    per_item = _parse_yes_no(update.message.text)
    set_user_data(user_id, "per_material_prices", "true" if per_item else "false")
    await update.message.reply_text("¿Cuántos materiales se van a utilizar?")
    return ASK_NUM_MATERIALS


async def ask_num_materials(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        set_user_data(user_id, "materials", [])
        set_user_data(user_id, "materials_done", 0)
        await update.message.reply_text(f"Entendido, {num} materiales. Ahora, por favor, introduce la descripción del material 1.")
        return COLLECT_MATERIAL_DESCRIPTIONS
    except ValueError:
        await update.message.reply_text("Eso no parece un número. Por favor, introduce un número válido.")
        return ASK_NUM_MATERIALS


async def collect_material_descriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)
    description = update.message.text.strip()
    materials = user_data.get("materials", [])
    materials.append({"description": description, "price": 0.0})
    set_user_data(user_id, "materials", materials)

    per_item = user_data.get("per_material_prices") == "true"
    num_materials_total = int(user_data.get("num_materials", len(materials)))

    if per_item:
        await update.message.reply_text(f"Introduce el precio del material {len(materials)}:")
        return COLLECT_MATERIAL_PRICE
    else:
        materials_done = int(user_data.get("materials_done", 0)) + 1
        set_user_data(user_id, "materials_done", materials_done)
        if materials_done < num_materials_total:
            await update.message.reply_text(f"Material {materials_done} guardado. Ahora introduce la descripción del material {materials_done + 1}.")
            return COLLECT_MATERIAL_DESCRIPTIONS
        else:
            await update.message.reply_text("Todas las descripciones de los materiales han sido guardadas. Ahora, por favor, introduce el precio TOTAL de todos los materiales.")
            return ASK_TOTAL_MATERIAL_PRICE


async def collect_material_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        await update.message.reply_text(f"Material {materials_done} guardado. Ahora introduce la descripción del material {materials_done + 1}.")
        return COLLECT_MATERIAL_DESCRIPTIONS
    else:
        total_materials_price = sum(m.get("price", 0) for m in materials)
        set_user_data(user_id, "total_materials_price", total_materials_price)
        await update.message.reply_text("Necesitas agregar el impuesto del IVA (Si/No)?")
        return ASK_FOR_VAT


async def ask_total_material_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    user_id = update.message.from_user.id
    response = update.message.text.strip().lower()
    if response in ["si", "sí"]:
        set_user_data(user_id, "vat", "true")
    else:
        set_user_data(user_id, "vat", "false")
    await update.message.reply_text("¿Cuántos días hábiles tomará el trabajo?")
    return ASK_WORKING_DAYS


async def ask_working_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    try:
        days = int(float(update.message.text.replace(",", ".")))
        if days <= 0:
            await update.message.reply_text("Introduce un número positivo de días.")
            return ASK_WORKING_DAYS
        set_user_data(user_id, "working_days", days)
    except ValueError:
        await update.message.reply_text("Eso no parece un número válido. Por favor, introduce un número.")
        return ASK_WORKING_DAYS
    await update.message.reply_text("¿Deseas usar los términos y condiciones por defecto? (Si/No)")
    return ASK_USE_DEFAULT_TERMS


async def ask_use_default_terms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)
    use_default = _parse_yes_no(update.message.text)
    if use_default:
        working_days = user_data.get("working_days", 0)
        terms = [t.format(working_days=working_days) for t in DEFAULT_TERMS]
        set_user_data(user_id, "terms", terms)
        return await begin_review(update, context)
    # Iniciar proceso de revisión
    set_user_data(user_id, "terms", [])
    set_user_data(user_id, "term_index", 0)
    await update.message.reply_text(
        "Revisaremos cada término. Responde 'dejar', 'modificar' o 'eliminar'.\n" +
        f"Término 1: '{DEFAULT_TERMS[0]}'. ¿Qué deseas hacer?"
    )
    return REVIEW_TERM_ACTION


async def review_term_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)
    term_index = int(user_data.get("term_index", 0))
    action = update.message.text.strip().lower()

    if term_index >= len(DEFAULT_TERMS):
        await update.message.reply_text("¿Deseas agregar otro término adicional? (Si/No)")
        return ASK_ADD_EXTRA_TERM

    current_term = DEFAULT_TERMS[term_index]

    if action in ("dejar", "d", "keep"):
        working_days = user_data.get("working_days", 0)
        term_text = current_term.format(working_days=working_days)
        terms = user_data.get("terms", [])
        terms.append(term_text)
        set_user_data(user_id, "terms", terms)
    elif action in ("eliminar", "e", "delete"):
        pass
    elif action in ("modificar", "m", "edit"):
        set_user_data(user_id, "awaiting_modification", current_term)
        await update.message.reply_text("Escribe la nueva versión del término:")
        return MODIFY_TERM
    else:
        await update.message.reply_text("Respuesta no válida. Usa 'dejar', 'modificar' o 'eliminar'.")
        return REVIEW_TERM_ACTION

    term_index += 1
    set_user_data(user_id, "term_index", term_index)
    if term_index < len(DEFAULT_TERMS):
        await update.message.reply_text(
            f"Término {term_index + 1}: '{DEFAULT_TERMS[term_index]}'. ¿Qué deseas hacer? (dejar/modificar/eliminar)"
        )
        return REVIEW_TERM_ACTION
    else:
        await update.message.reply_text("¿Deseas agregar otro término adicional? (Si/No)")
        return ASK_ADD_EXTRA_TERM


async def modify_term(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)
    new_text = update.message.text.strip()
    terms = user_data.get("terms", [])
    terms.append(new_text)
    set_user_data(user_id, "terms", terms)
    term_index = int(user_data.get("term_index", 0)) + 1
    set_user_data(user_id, "term_index", term_index)
    if term_index < len(DEFAULT_TERMS):
        await update.message.reply_text(
            f"Término {term_index + 1}: '{DEFAULT_TERMS[term_index]}'. ¿Qué deseas hacer? (dejar/modificar/eliminar)"
        )
        return REVIEW_TERM_ACTION
    else:
        await update.message.reply_text("¿Deseas agregar otro término adicional? (Si/No)")
        return ASK_ADD_EXTRA_TERM


async def ask_add_extra_term(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    add_more = _parse_yes_no(update.message.text)
    if add_more:
        await update.message.reply_text("Escribe el nuevo término adicional:")
        return ADD_EXTRA_TERM
    # Ir a revisión final
    return await begin_review(update, context)


async def add_extra_term(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)
    terms = user_data.get("terms", [])
    terms.append(update.message.text.strip())
    set_user_data(user_id, "terms", terms)
    await update.message.reply_text("¿Deseas agregar otro término adicional? (Si/No)")
    return ASK_ADD_EXTRA_TERM


# ---------- Revisión final (resumen, edición y confirmación) ----------

def _format_money(value: float) -> str:
    try:
        return f"${value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"${value}"


async def begin_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Construye y envía el resumen y pregunta confirmación."""
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)

    jobs_list = user_data.get("jobs", [])
    materials_list = user_data.get("materials", [])
    per_job_prices = user_data.get("per_job_prices") == "true"
    per_material_prices = user_data.get("per_material_prices") == "true"

    total_jobs = sum(j.get("price", 0) for j in jobs_list) if per_job_prices else float(user_data.get("total_jobs_price", 0))
    total_materials = sum(m.get("price", 0) for m in materials_list) if per_material_prices else float(user_data.get("total_materials_price", 0))
    subtotal = total_jobs + total_materials

    vat_included = user_data.get("vat") == "true"
    vat = round(subtotal * 0.13, 2) if vat_included else 0
    grand_total = round(subtotal + vat, 2)

    lines = [
        "Resumen de la cotización:",
        "",
        "Trabajos:",
    ]
    if jobs_list:
        for i, j in enumerate(jobs_list, start=1):
            price_txt = _format_money(j.get("price", 0)) if per_job_prices else "-"
            lines.append(f"  {i}. {j.get('description','')} | Precio: {price_txt}")
        lines.append(f"  Total Mano de Obra: {_format_money(total_jobs)}")
    else:
        lines.append("  (sin trabajos)")

    lines.append("")
    lines.append("Materiales:")
    if materials_list:
        for i, m in enumerate(materials_list, start=1):
            price_txt = _format_money(m.get("price", 0)) if per_material_prices else "-"
            lines.append(f"  {i}. {m.get('description','')} | Precio: {price_txt}")
        lines.append(f"  Total Materiales: {_format_money(total_materials)}")
    else:
        lines.append("  (sin materiales)")

    lines.append("")
    lines.append(f"Subtotal: {_format_money(subtotal)}")
    if vat_included:
        lines.append(f"IVA (13%): {_format_money(vat)}")
    lines.append(f"Total General: {_format_money(grand_total)}")
    lines.append("")
    lines.append("¿Está bien así? (Si/No)")

    await update.message.reply_text("\n".join(lines))
    return REVIEW_SUMMARY


async def review_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirma el resumen o inicia edición de un ítem."""
    user_id = update.message.from_user.id
    answer = update.message.text.strip().lower()
    if answer in ("si", "sí", "s", "yes", "y"):
        return await generate_pdf(update, context)
    await update.message.reply_text(
        "Indica qué deseas modificar. Ejemplos: 'trabajo 2', 'material 1'."
    )
    return SELECT_EDIT_ITEM


async def select_edit_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)
    text = update.message.text.strip().lower()

    edit_type = None
    index = None
    if text.startswith("trabajo"):
        edit_type = "job"
        parts = text.split()
        if len(parts) >= 2 and parts[1].isdigit():
            index = int(parts[1]) - 1
    elif text.startswith("material"):
        edit_type = "material"
        parts = text.split()
        if len(parts) >= 2 and parts[1].isdigit():
            index = int(parts[1]) - 1

    if edit_type is None or index is None:
        await update.message.reply_text("Entrada no válida. Usa 'trabajo N' o 'material M'.")
        return SELECT_EDIT_ITEM

    items = user_data.get("jobs", []) if edit_type == "job" else user_data.get("materials", [])
    if index < 0 or index >= len(items):
        await update.message.reply_text("Número fuera de rango. Intenta de nuevo.")
        return SELECT_EDIT_ITEM

    set_user_data(user_id, "edit_type", edit_type)
    set_user_data(user_id, "edit_index", index)

    per_item_prices = (user_data.get("per_job_prices") == "true") if edit_type == "job" else (user_data.get("per_material_prices") == "true")

    if per_item_prices:
        await update.message.reply_text("¿Qué deseas modificar? (descripcion/precio/ambos)")
    else:
        await update.message.reply_text("¿Qué deseas modificar? (descripcion) — los precios por ítem están desactivados")
    return CHOOSE_EDIT_FIELD


async def choose_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)
    choice = update.message.text.strip().lower()

    edit_type = user_data.get("edit_type")
    edit_index = int(user_data.get("edit_index", 0))

    per_item_prices = (user_data.get("per_job_prices") == "true") if edit_type == "job" else (user_data.get("per_material_prices") == "true")

    if choice in ("descripcion", "descripción"):
        set_user_data(user_id, "edit_next", "none")
        await update.message.reply_text("Escribe la nueva descripción:")
        return EDIT_ITEM_DESCRIPTION
    elif choice == "precio" and per_item_prices:
        set_user_data(user_id, "edit_next", "none")
        await update.message.reply_text("Escribe el nuevo precio:")
        return EDIT_ITEM_PRICE
    elif choice == "ambos" and per_item_prices:
        set_user_data(user_id, "edit_next", "price")
        await update.message.reply_text("Escribe la nueva descripción:")
        return EDIT_ITEM_DESCRIPTION
    else:
        await update.message.reply_text("Opción no válida. Responde con descripcion/precio/ambos.")
        return CHOOSE_EDIT_FIELD


async def edit_item_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)
    new_desc = update.message.text.strip()

    edit_type = user_data.get("edit_type")
    index = int(user_data.get("edit_index", 0))

    if edit_type == "job":
        items = user_data.get("jobs", [])
        items[index]["description"] = new_desc
        set_user_data(user_id, "jobs", items)
    else:
        items = user_data.get("materials", [])
        items[index]["description"] = new_desc
        set_user_data(user_id, "materials", items)

    if user_data.get("edit_next") == "price":
        await update.message.reply_text("Ahora escribe el nuevo precio:")
        return EDIT_ITEM_PRICE

    # Volver a resumen
    return await begin_review(update, context)


async def edit_item_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)
    try:
        new_price = float(update.message.text.replace("$", "").strip())
    except ValueError:
        await update.message.reply_text("Eso no parece un precio válido. Por favor, introduce un número.")
        return EDIT_ITEM_PRICE

    edit_type = user_data.get("edit_type")
    index = int(user_data.get("edit_index", 0))

    if edit_type == "job":
        items = user_data.get("jobs", [])
        items[index]["price"] = new_price
        set_user_data(user_id, "jobs", items)
        # Recalcular total de trabajos si aplica
        if user_data.get("per_job_prices") == "true":
            set_user_data(user_id, "total_jobs_price", sum(j.get("price", 0) for j in items))
    else:
        items = user_data.get("materials", [])
        items[index]["price"] = new_price
        set_user_data(user_id, "materials", items)
        if user_data.get("per_material_prices") == "true":
            set_user_data(user_id, "total_materials_price", sum(m.get("price", 0) for m in items))

    # Limpiar flags de edición opcional
    set_user_data(user_id, "edit_next", "none")

    # Volver a resumen
    return await begin_review(update, context)


async def generate_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_data = get_user_data(user_id)

    jobs_list = user_data.get("jobs", [])
    materials_list = user_data.get("materials", [])
    per_job_prices = user_data.get("per_job_prices") == "true"
    per_material_prices = user_data.get("per_material_prices") == "true"

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

    working_days = user_data.get("working_days", 0)
    terms = user_data.get("terms", [])
    if not terms:
        terms = [t.format(working_days=working_days) for t in DEFAULT_TERMS]

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
        "working_days": working_days,
        "terms": terms,
    }

    try:
        response = requests.post(PDF_SERVICE_URL, json=pdf_data)
        if response.status_code == 200:
            await update.message.reply_document(
                document=response.content,
                filename=f"cotizacion_{user_data.get('client_name','cliente')}.pdf",
                caption="¡Aquí está tu cotización!",
            )
        else:
            await update.message.reply_text(f"Hubo un error al generar el PDF (código: {response.status_code}). Por favor, inténtalo de nuevo.")
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"No se pudo conectar al servicio de PDF: {e}")

    r.delete(f"user:{user_id}")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    r.delete(f"user:{user_id}")
    await update.message.reply_text("Conversación cancelada.")
    return ConversationHandler.END


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Reinicia la conversación."""
    user_id = update.message.from_user.id
    r.delete(f"user:{user_id}")
    await update.message.reply_text(
        "Conversación reiniciada. ¡Vamos a crear una cotización! Por favor, dime el nombre del cliente."
    )
    return CLIENT_NAME


def main() -> None:
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
            ASK_WORKING_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_working_days)],
            ASK_USE_DEFAULT_TERMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_use_default_terms)],
            REVIEW_TERM_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, review_term_action)],
            MODIFY_TERM: [MessageHandler(filters.TEXT & ~filters.COMMAND, modify_term)],
            ASK_ADD_EXTRA_TERM: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_add_extra_term)],
            ADD_EXTRA_TERM: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_extra_term)],
            REVIEW_SUMMARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, review_summary)],
            SELECT_EDIT_ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_edit_item)],
            CHOOSE_EDIT_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_edit_field)],
            EDIT_ITEM_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_item_description)],
            EDIT_ITEM_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_item_price)],
            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, on_timeout)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("restart", restart)],
        conversation_timeout=900,
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
