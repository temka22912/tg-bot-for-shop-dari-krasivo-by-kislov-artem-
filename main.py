import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.error import BadRequest
from datetime import datetime

# === НАСТРОЙКИ ===
BOT_TOKEN = ""
ADMIN_PASSWORD = ""
ADMIN_CHAT_ID = 
PAYMENT_PHONE = ""
STORE_ADDRESS = ""
VK_LINK = ""

# === ХРАНИЛИЩЕ ===
catalog = {
    "strawberry": {},
    "banana": {},
    "dubai": {},
    "combo": {},
    "bouquet": {}
}
flowers_stock = {}
user_states = {}
active_orders = {}
order_counter = 0  # Счетчик заказов

# Эмодзи и названия
CAT_MAP = {
    "strawberry": ("🍓", "Клубника в шоколаде"),
    "banana": ("🍌", "Бананы в шоколаде"),
    "dubai": ("🍫", "Дубайский шоколад"),
    "combo": ("🎁", "Комбо / Сеты"),
    "bouquet": ("💐", "Готовые букеты"),
    "flower": ("🌼", "Цветы для сборки")
}

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# === ВСПОМОГАТЕЛЬНОЕ ===
def next_id(category: str) -> int:
    items = catalog[category]
    if not items:
        return 1
    return max(items.keys(), default=0) + 1


def safe_edit_message(query, text: str, parse_mode="Markdown", reply_markup=None):
    """Безопасное редактирование сообщения (игнорирует 'not modified')"""
    try:
        return query.message.edit_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except BadRequest as e:
        if "message is not modified" not in str(e):
            raise
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение: {e}")
    return None


# === СТИЛИЗОВАННЫЕ ПОДСКАЗКИ ===
def make_help_card() -> str:
    return (
        "🔐 *Админ-панель «Дари красиво»*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✨ *Как добавить товар?*\n"
        "1️⃣ Нажмите на категорию ниже\n"
        "2️⃣ Отправьте *фото*\n"
        "3️⃣ В *подписи* — описание и цену\n"
        "4️⃣ Готово! Товар сразу в каталоге.\n\n"
        "💡 *Совет:* Используйте шаблоны — они в подсказках!\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )


ADD_TEMPLATES = {
    "strawberry": (
        "🍓 *Клубника в шоколаде*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📎 *Как оформить подпись:*\n"
        "`Название. Состав. Количество — Цена`\n\n"
        "✅ *Пример идеальной подписи:*\n"
        "```\n"
        "Клубника «Нежность»\n"
        "Белый шоколад, кокосовая стружка\n"
        "3 шт — 590₽\n"
        "```\n\n"
        "📤 *Отправьте фото клубники прямо сейчас*"
    ),
    "banana": (
        "🍌 *Бананы в шоколаде*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📎 *Формат подписи:*\n"
        "`Название. Покрытие, начинка. Количество — Цена`\n\n"
        "✅ *Пример:*\n"
        "```\n"
        "Банан «Премиум»\n"
        "Тёмный шоколад, фисташки, золото\n"
        "2 шт — 490₽\n"
        "```\n\n"
        "📤 *Жду ваше фото бананов!*"
    ),
    "dubai": (
        "🍫 *Дубайский шоколад*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📎 *Подпись должна содержать:*\n"
        "`Название. Вес, состав — Цена`\n\n"
        "✅ *Пример:*\n"
        "```\n"
        "Дубай «Роскошь»\n"
        "200 г, малина, сулугуни, золото\n"
        "— 890₽\n"
        "```\n\n"
        "📤 *Отправьте фото упаковки*"
    ),
    "combo": (
        "🎁 *Комбо / Сеты*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📎 *Структура подписи:*\n"
        "`Название. Что входит — Цена`\n\n"
        "✅ *Пример:*\n"
        "```\n"
        "Сет «Любимому»\n"
        "5 клубник, 2 банана, коробка, лента\n"
        "— 1490₽\n"
        "```\n\n"
        "📤 *Жду фото сета!*"
    ),
    "bouquet": (
        "💐 *Готовые букеты*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📎 *Описание в подписи:*\n"
        "`Название. Состав, упаковка — Цена`\n\n"
        "✅ *Пример:*\n"
        "```\n"
        "Букет «Счастье»\n"
        "21 роза, крафт, атласная лента, записка\n"
        "— 3490₽\n"
        "```\n\n"
        "📤 *Отправьте фото букета*"
    ),
    "flower": (
        "🌼 *Цветы для индивидуальной сборки*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📎 *Формат подписи к фото:*\n"
        "`Полное название — Цена`\n\n"
        "✅ *Правильные примеры:*\n"
        "```\n"
        "Роза кенийская 100 см — 120\n"
        "Пион Сара Бернар — 200\n"
        "Эустома крупноцветковая белая — 80\n"
        "```\n\n"
        "❗ *Важно:*\n"
        "— Цена только цифрами, без ₽\n"
        "— Название — максимально подробно\n\n"
        "📤 *Отправьте фото цветка*"
    )
}


# === КОМАНДЫ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states.pop(user_id, None)
    buttons = []
    for cat, (emoji, name) in CAT_MAP.items():
        if cat == "flower":
            continue
        count = len(catalog[cat])
        if count > 0:
            buttons.append([InlineKeyboardButton(f"{emoji} {name} ({count})", callback_data=f"show_{cat}")])
    if catalog["bouquet"]:
        buttons.append([InlineKeyboardButton("💐 Готовые букеты", callback_data="show_bouquet")])
    buttons.append([InlineKeyboardButton("🎨 Собрать букет", callback_data="build_bouquet")])
    if not buttons:
        await update.message.reply_text("временно ничего нет в наличии 😊")
        return
    await update.message.reply_text(
        "Здравствуйте! 🌸\nВыберите категорию:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Здравствуйте, наш магазин называется "Дари красиво". Работаем с 2022 года. '
        'В наличии: букеты, клубника и бананы в шоколаде. '
        f'Отзывы: {VK_LINK} | Адрес: {STORE_ADDRESS}'
    )


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = {"state": "awaiting_password"}
    await update.message.reply_text("🔒 Введите пароль:")


async def exit_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states.pop(user_id, None)
    await update.message.reply_text("✅ Вы вышли из админ-меню.")


async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_states.get(user_id, {}).get("state") != "admin":
        return

    text = make_help_card()
    buttons = [
        [InlineKeyboardButton("🍓 Клубника", callback_data="add_strawberry"),
         InlineKeyboardButton("🍌 Бананы", callback_data="add_banana")],
        [InlineKeyboardButton("🍫 Дубай", callback_data="add_dubai"),
         InlineKeyboardButton("🎁 Комбо", callback_data="add_combo")],
        [InlineKeyboardButton("💐 Букеты", callback_data="add_bouquet"),
         InlineKeyboardButton("🌼 Цветы", callback_data="add_flower")],
        [InlineKeyboardButton("🗂️ Просмотр", callback_data="list_menu"),
         InlineKeyboardButton("📭 Заказы", callback_data="show_orders")],
    ]
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown",
                                                       reply_markup=InlineKeyboardMarkup(buttons))


async def admin_help_helper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вспомогательная функция для возврата в меню помощи"""
    user_id = update.effective_user.id
    if user_states.get(user_id, {}).get("state") != "admin":
        return

    text = make_help_card()
    buttons = [
        [InlineKeyboardButton("🍓 Клубника", callback_data="add_strawberry"),
         InlineKeyboardButton("🍌 Бананы", callback_data="add_banana")],
        [InlineKeyboardButton("🍫 Дубай", callback_data="add_dubai"),
         InlineKeyboardButton("🎁 Комбо", callback_data="add_combo")],
        [InlineKeyboardButton("💐 Букеты", callback_data="add_bouquet"),
         InlineKeyboardButton("🌼 Цветы", callback_data="add_flower")],
        [InlineKeyboardButton("🗂️ Просмотр", callback_data="list_menu"),
         InlineKeyboardButton("📭 Заказы", callback_data="show_orders")],
    ]
    await safe_edit_message(
        update.callback_query,
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# === КНОПКИ АДМИНКИ ===
async def add_item_start(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_states.get(user_id, {}).get("state") != "admin":
        return
    user_states[user_id] = {"state": f"awaiting_{category}_photo"}
    await safe_edit_message(
        query,
        ADD_TEMPLATES[category],
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 В меню", callback_data="back_to_help")]])
    )


async def back_to_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await admin_help_helper(update, context)


# === ДОБАВЛЕНИЕ (ТОЛЬКО ДЛЯ ФОТО) ===
async def handle_admin_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фото для добавления товаров админом"""
    if not update.message or not update.message.photo:
        return

    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get("state")
    if not state:
        return

    # Проверяем, что это не фото чека
    if state.startswith("awaiting_receipt_"):
        # Это фото чека, передаём обработку в handle_message
        await handle_message(update, context)
        return

    if not state.startswith("awaiting_"):
        return

    category = state.split("_")[1]

    # Проверяем, что это допустимая категория для добавления
    if category not in ["strawberry", "banana", "dubai", "combo", "bouquet", "flower"]:
        return

    user_states[user_id]["state"] = "admin"  # сразу возвращаем в админ-режим

    if category == "flower":
        caption = update.message.caption or ""
        photo_file_id = update.message.photo[-1].file_id

        if "—" not in caption:
            await update.message.reply_text(
                "❌ Ошибка формата.\n"
                "Нужно: `Название — Цена`\n"
                "Пример: `Роза кенийская 100 см — 120`",
                parse_mode="Markdown"
            )
            return

        try:
            parts = caption.split("—", 1)
            name = parts[0].strip()
            price = int(parts[1].strip())
            if price <= 0 or not name:
                raise ValueError
        except:
            await update.message.reply_text(
                "❌ Некорректная цена или название.\n"
                "✅ Пример: `Пион Сара Бернар — 200`"
            )
            return

        flowers_stock[name] = {"price": price, "stock": 0, "photo": photo_file_id}
        await update.message.reply_text(
            f"✅ *Цветок добавлен!*\n"
            f"🌼 **{name}** — {price}₽/шт\n"
            f"📦 Остаток: 0 шт (обновите через `/stock`)\n\n"
            f"🏠 Вы в админ-панели. Продолжайте работу!\n"
            f"→ `/help` — подсказка",
            parse_mode="Markdown"
        )
        return

    # Готовые товары
    caption = update.message.caption or "Без описания"
    fid = update.message.photo[-1].file_id
    pid = next_id(category)
    catalog[category][pid] = {"photo": fid, "text": caption}

    short_name = caption.split("\n")[0][:40].strip()
    emoji, cat_name = CAT_MAP[category]

    await update.message.reply_text(
        f"✅ *{cat_name} добавлена!*\n"
        f"{emoji} ID: `{pid}`\n"
        f"📝 «{short_name}…»\n\n"
        f"🏠 Вы в админ-панели. Продолжайте работу!\n"
        f"→ `/help` — подсказка",
        parse_mode="Markdown"
    )


# === УДАЛЕНИЕ ЧЕРЕЗ КНОПКИ ===
async def list_categories_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    buttons = []
    for cat in ["strawberry", "banana", "dubai", "combo", "bouquet"]:
        emoji, name = CAT_MAP[cat]
        count = len(catalog[cat])
        buttons.append([InlineKeyboardButton(f"{emoji} {name} ({count})", callback_data=f"list_{cat}")])
    buttons.append([InlineKeyboardButton("🌼 Цветы", callback_data="list_flowers")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data="back_to_help")])
    await safe_edit_message(
        query,
        "🗂️ *Выберите категорию для просмотра и удаления:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def show_category_for_delete(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    query = update.callback_query
    await query.answer()
    items = catalog[category]
    if not items:
        await query.message.reply_text(f"📦 В категории *{CAT_MAP[category][1]}* нет товаров.", parse_mode="Markdown")
        return

    buttons = []
    for pid in sorted(items.keys()):
        name = items[pid]["text"].split("\n")[0][:25]
        buttons.append([InlineKeyboardButton(f"ID {pid}: {name}…", callback_data=f"del_{category}_{pid}")])
    buttons.append([InlineKeyboardButton("← Назад", callback_data="list_menu")])

    await safe_edit_message(
        query,
        f"🗑️ *Удаление из: {CAT_MAP[category][1]}*\nВыберите товар для удаления:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("del_"):
        return
    parts = data.split("_", 2)
    if len(parts) != 3:
        return
    category, pid_str = parts[1], parts[2]
    pid = int(pid_str)

    if pid in catalog[category]:
        name = catalog[category][pid]["text"].split("\n")[0][:30]
        del catalog[category][pid]
        emoji, cat_name = CAT_MAP[category]
        await query.message.reply_text(
            f"✅ *Удалено!*\n"
            f"{emoji} **{cat_name}**\n"
            f"ID: `{pid}` | «{name}…»\n\n"
            f"🏠 Вы в админ-панели. Продолжайте работу!\n"
            f"→ `/help` — подсказка",
            parse_mode="Markdown"
        )
    else:
        await query.message.reply_text("❌ Товар уже удалён.", parse_mode="Markdown")


# === ПРОСМОТР ЦВЕТОВ ===
async def list_flowers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not flowers_stock:
        await safe_edit_message(
            query,
            "🌼 Нет цветов в базе.\nДобавьте через «🌼 Цветы» в меню.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="list_menu")]])
        )
        return

    text = "🌼 *Цветы для сборки:*\n\n"
    for name, data in flowers_stock.items():
        text += f"• {name} — {data['price']}₽ ({data['stock']} шт)\n"
    text += "\n✏️ Обновить остаток: `/stock \"Название\" 10`"

    await safe_edit_message(
        query,
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="list_menu")]])
    )


# === ЗАКАЗЫ ===
async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not active_orders:
        await safe_edit_message(
            query,
            "📭 *Активных заказов нет.*\nКак только клиент оформит — появится здесь.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back_to_help")]])
        )
        return

    text = "📭 *Активные заказы:*\n\n"
    for oid, order in active_orders.items():
        typ = order["type"]
        cat_name = CAT_MAP.get(typ, ("", typ))[1] if typ != "custom" else "🎨 Индивидуальный"
        user = f"@{order['username']}" if order.get('username') else f"ID {order['user_id']}"
        ts = order["timestamp"].strftime("%H:%M")
        text += f"• #{oid} | {cat_name} | {user} | {ts}\n"

    await safe_edit_message(
        query,
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back_to_help")]])
    )


async def send_order_to_admin(context: ContextTypes.DEFAULT_TYPE, order_id: int, order_data: dict):
    """Отправляет уведомление о заказе админу С ФОТО ТОВАРА"""
    try:
        typ = order_data["type"]
        user_id = order_data["user_id"]
        username = order_data.get("username", "—")
        photo_file_id = order_data.get("photo_file_id")

        if typ == "custom":
            # Индивидуальный букет
            description = order_data["data"]["description"]
            text = (
                f"🆕 *ИНДИВИДУАЛЬНЫЙ ЗАКАЗ #{order_id}*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 Покупатель: @{username} (ID: {user_id})\n"
                f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"💐 *Описание букета:*\n"
                f"`{description}`\n\n"
                f"📞 Связаться: [Написать](tg://user?id={user_id})"
            )

            contact_btn = InlineKeyboardButton("📞 Связаться", url=f"tg://user?id={user_id}")
            reply_markup = InlineKeyboardMarkup([[contact_btn]])

            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        else:
            # Товар из каталога
            cat_name = CAT_MAP.get(typ, ("", "Товар"))[1]
            item_id = order_data["data"].get("item_id", "?")

            # Получаем информацию о товаре
            item_info = ""
            caption = ""
            if typ in catalog and item_id in catalog[typ]:
                item = catalog[typ][item_id]
                caption = item["text"]
                item_info = item["text"].split("\n")[0][:50]

            # Если есть фото товара - отправляем фото с подписью
            if photo_file_id:
                contact_btn = InlineKeyboardButton("📞 Связаться", url=f"tg://user?id={user_id}")
                reply_markup = InlineKeyboardMarkup([[contact_btn]])

                await context.bot.send_photo(
                    chat_id=ADMIN_CHAT_ID,
                    photo=photo_file_id,
                    caption=(
                        f"🆕 *НОВЫЙ ЗАКАЗ #{order_id}*\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📦 Категория: {cat_name}\n"
                        f"👤 Покупатель: @{username} (ID: {user_id})\n"
                        f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                        f"🆔 ID товара: {item_id}\n\n"
                        f"{caption}\n\n"
                        f"💳 *Оплата:*\n"
                        f"Сбербанк: `{PAYMENT_PHONE}`\n\n"
                        f"📞 Связаться: [Написать](tg://user?id={user_id})"
                    ),
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
            else:
                # Если фото нет, отправляем просто текст
                contact_btn = InlineKeyboardButton("📞 Связаться", url=f"tg://user?id={user_id}")
                reply_markup = InlineKeyboardMarkup([[contact_btn]])

                text = (
                    f"🆕 *НОВЫЙ ЗАКАЗ #{order_id}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📦 Категория: {cat_name}\n"
                    f"👤 Покупатель: @{username} (ID: {user_id})\n"
                    f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                    f"🆔 ID товара: {item_id}\n\n"
                    f"📝 *Товар:*\n"
                    f"`{item_info}`\n\n"
                    f"💳 *Оплата:*\n"
                    f"Сбербанк: `{PAYMENT_PHONE}`\n\n"
                    f"📞 Связаться: [Написать](tg://user?id={user_id})"
                )

                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=text,
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )

        logger.info(f"Заказ #{order_id} отправлен админу")

    except Exception as e:
        logger.error(f"Ошибка отправки заказа админу: {e}")


# === РАБОТА С ЗАКАЗАМИ ===
async def send_quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_states.get(user_id, {}).get("state") != "admin":
        return
    if len(context.args) != 2:
        await update.message.reply_text("Используйте: `/quote <user_id> <сумма>`")
        return
    try:
        client_id = int(context.args[0])
        amount = int(context.args[1])
        if amount <= 0:
            raise ValueError
    except:
        await update.message.reply_text("ID и сумма — положительные числа.")
        return

    try:
        await context.bot.send_message(
            chat_id=client_id,
            text=f"💐 Ваш заказ рассчитан!\n\n"
                 f"💰 Итого: **{amount}₽**\n\n"
                 f"💳 Оплатите на Сбер: `{PAYMENT_PHONE}`\n"
                 "После оплаты — скрин чека.",
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ Расчёт {amount}₽ отправлен клиенту {client_id}.")
    except Exception as e:
        await update.message.reply_text(f"❌ Не отправлено: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений и фото-чеков"""
    global order_counter  # Объявляем глобальную переменную в начале функции

    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get("state")

    # Обработка фото-чеков
    if update.message and update.message.photo:
        if state and state.startswith("awaiting_receipt_"):
            parts = state.split("_")
            if len(parts) >= 4:
                cat = parts[2]
                try:
                    pid = int(parts[3])

                    # Получаем photo_file_id из каталога
                    photo_file_id = None
                    if cat in catalog and pid in catalog[cat]:
                        photo_file_id = catalog[cat][pid]["photo"]

                    # Пересылаем чек админу
                    try:
                        await context.bot.forward_message(
                            chat_id=ADMIN_CHAT_ID,
                            from_chat_id=update.effective_chat.id,
                            message_id=update.message.message_id
                        )
                        logger.info(f"Чек переслан админу от пользователя {user_id}")
                    except Exception as e:
                        logger.error(f"Не удалось переслать чек: {e}")

                    # Создаём заказ
                    order_counter += 1
                    order_id = order_counter

                    order_data = {
                        "type": cat,
                        "user_id": user_id,
                        "username": update.effective_user.username,
                        "data": {"item_id": pid},
                        "timestamp": datetime.now(),
                        "photo_file_id": photo_file_id  # Добавляем фото товара
                    }

                    active_orders[order_id] = order_data

                    # Отправляем уведомление о заказе админу
                    await send_order_to_admin(context, order_id, order_data)

                    await update.message.reply_text(
                        "🌷 *Заказ принят! Начинаем сборку!*\n\n"
                        "📦 Ваш заказ передан на сборку.\n"
                        "⏱️ Готовность: 1-2 часа\n"
                        "📞 С вами свяжется администратор.",
                        parse_mode="Markdown"
                    )
                    user_states.pop(user_id, None)
                    return
                except (ValueError, IndexError) as e:
                    logger.error(f"Ошибка обработки состояния: {e}")
                    await update.message.reply_text("❌ Ошибка обработки заказа. Попробуйте снова.")
                    user_states.pop(user_id, None)
        return

    # 🔐 Пароль (только текст)
    text = update.message.text or ""

    if state == "awaiting_password":
        if text == ADMIN_PASSWORD:
            user_states[user_id] = {"state": "admin"}
            await admin_help(update, context)
        else:
            user_states.pop(user_id, None)
            await update.message.reply_text("❌ Неверный пароль.")
        return

    # 📝 Индивидуальный букет (только текст)
    if state == "awaiting_bouquet_description":
        description = text.strip()
        if not description:
            await update.message.reply_text("Опишите букет, пожалуйста.")
            return

        order_counter += 1
        order_id = order_counter

        order_data = {
            "type": "custom",
            "user_id": user_id,
            "username": update.effective_user.username,
            "data": {"description": description},
            "timestamp": datetime.now()
        }

        active_orders[order_id] = order_data

        # Отправляем админу
        await send_order_to_admin(context, order_id, order_data)

        await update.message.reply_text(
            "💐 Спасибо за заказ!\n\n"
            "📞 Админ свяжется с вами в течение часа."
        )
        user_states.pop(user_id, None)
        return


# === ОБРАБОТКА КНОПОК (ОСНОВНОЙ ИНТЕРФЕЙС) ===
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    # Админ-панель
    if data == "back_to_help":
        await back_to_help(update, context)
        return
    if data == "list_menu":
        await list_categories_menu(update, context)
        return
    if data == "show_orders":
        await show_orders(update, context)
        return

    # Добавление
    categories = ["strawberry", "banana", "dubai", "combo", "bouquet", "flower"]
    if data in [f"add_{c}" for c in categories]:
        cat = data.split("_")[1]
        await add_item_start(update, context, cat)
        return

    # Просмотр для удаления
    if data.startswith("list_"):
        cat = data.split("_", 1)[1]
        if cat == "flowers":
            await list_flowers(update, context)
        else:
            await show_category_for_delete(update, context, cat)
        return

    # Удаление
    if data.startswith("del_"):
        await confirm_delete(update, context)
        return

    # Основной интерфейс (клиент)
    if data.startswith("show_"):
        cat = data.split("_", 1)[1]
        if cat not in catalog:
            await query.message.reply_text(f"Категория не найдена.")
            return
        items = catalog[cat]
        if not items:
            await query.message.reply_text(f"временно нет {CAT_MAP.get(cat, ('', cat))[1].lower()} 😊")
            return
        for pid, item in items.items():
            btn = InlineKeyboardButton("📦 Заказать", callback_data=f"order_{cat}_{pid}")
            await query.message.reply_photo(
                photo=item["photo"],
                caption=item["text"],
                reply_markup=InlineKeyboardMarkup([[btn]])
            )
        return

    if data.startswith("order_"):
        parts = data.split("_", 2)
        if len(parts) != 3:
            await query.message.reply_text("Ошибка.")
            return
        cat, pid_str = parts[1], parts[2]
        try:
            pid = int(pid_str)
            if cat not in catalog or pid not in catalog[cat]:
                await query.message.reply_text("Товар удалён.")
                return

            # Сохраняем photo_file_id в состоянии для отправки админу
            photo_file_id = catalog[cat][pid]["photo"]
            user_states[user_id] = {
                "state": f"awaiting_receipt_{cat}_{pid}",
                "photo_file_id": photo_file_id  # Сохраняем photo_file_id
            }

            await query.message.reply_text(
                f"💳 *Оплатите на Сбер:* `{PAYMENT_PHONE}`\n\n"
                "📱 *Как оплатить:*\n"
                "1. Откройте Сбербанк Онлайн\n"
                "2. Переведите на указанный номер\n"
                "3. Сделайте скриншот оплаты\n"
                "4. Отправьте его сюда\n\n"
                "✅ *После оплаты отправьте скриншот чека*",
                parse_mode="Markdown"
            )
        except ValueError:
            await query.message.reply_text("Ошибка в данных.")
        return

    if data == "build_bouquet":
        available = [
            f"• {name} — {v['price']}₽ ({v['stock']} шт)"
            for name, v in flowers_stock.items()
            if v["stock"] > 0
        ]
        if not available:
            await query.message.reply_text("❌ Нет цветов в наличии.")
            return
        text = (
                "🎨 *Опишите, какой букет вы хотите.*\n\n"
                "Например:\n"
                "«Букет из 15 роз кенийских 100 см и 5 веток эвкалипта»\n\n"
                "🔹 *В наличии сейчас:*\n" + "\n".join(available) + "\n\n"
                                                                   "✏️ Пишите — мы подберём!"
        )
        user_states[user_id] = {"state": "awaiting_bouquet_description"}
        await query.message.reply_text(text, parse_mode="Markdown")
        return


# === ЗАПУСК ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Основные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("adminmenu", admin_menu))
    app.add_handler(CommandHandler("exit", exit_admin))
    app.add_handler(CommandHandler("help", admin_help))

    # Команды-совместимость
    for cat in ["strawberry", "banana", "dubai", "combo", "bouquet"]:
        app.add_handler(CommandHandler(f"add_{cat}",
                                       lambda u, c, cat=cat: add_item_start(u, c, cat)))

    app.add_handler(CommandHandler("add_flower",
                                   lambda u, c: add_item_start(u, c, "flower")))

    # Заказы
    app.add_handler(CommandHandler("quote", send_quote))

    # ⚠️ CALLBACK ДОЛЖЕН БЫТЬ ПЕРВЫМ!
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Обработка фото для админа (добавление товаров)
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_admin_photo))

    # Обработка текстовых сообщений (и фото-чеков через handle_message)
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_message))

    print("✅ Бот «Дари красиво» запущен!")
    print(f"👑 Админ: {ADMIN_CHAT_ID}")
    print("✨ Теперь заказы будут приходить админу С ФОТО ТОВАРА!")
    app.run_polling()


if __name__ == "__main__":
    main()
