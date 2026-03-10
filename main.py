import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import datetime
import uuid

# ============================================
# ДАННЫЕ
# ============================================
BOT_TOKEN = "8548246370:AAEYqEVTSdslgQNQPAqo6xh_PEcbnRajt6M"
ADMIN_IDS = [6979197416]

# ============================================
# КАТЕГОРИИ ОБРАЩЕНИЙ (КРАСИВЫЙ КАТАЛОГ)
# ============================================
CATEGORIES = {
    "1": {
        "name": "👤 Жалоба на игрока",
        "emoji": "👤",
        "desc": "Нарушение правил, оскорбления, гриферство"
    },
    "2": {
        "name": "📦 Возврат ресурсов",
        "emoji": "📦",
        "desc": "Откат инвентаря, потеря вещей (кроме PvP)"
    },
    "3": {
        "name": "❓ Вопрос по правилам",
        "emoji": "❓",
        "desc": "Уточнение правил сервера"
    },
    "4": {
        "name": "🛠 Связь с админом",
        "emoji": "🛠",
        "desc": "Срочные вопросы к администрации"
    },
    "5": {
        "name": "🐞 Баг / Ошибка",
        "emoji": "🐞",
        "desc": "Сообщить о баге или ошибке"
    },
    "6": {
        "name": "💡 Предложение",
        "emoji": "💡",
        "desc": "Идеи по улучшению сервера"
    }
}

# ============================================
# ХРАНИЛИЩЕ
# ============================================
users_db = {}
tickets_db = {}
ticket_counter = 0

# ============================================
# ЛОГИРОВАНИЕ
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def get_main_keyboard(user_id):
    """Главное меню"""
    keyboard = [
        [InlineKeyboardButton("📝 Создать обращение", callback_data="menu_new")],
        [InlineKeyboardButton("📋 Мои обращения", callback_data="menu_list")],
        [InlineKeyboardButton("ℹ️ О боте", callback_data="menu_about")]
    ]
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_main")])
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard(back_to):
    """Кнопка назад"""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("◀️ Назад", callback_data=f"back_{back_to}")
    ]])

# ============================================
# СТАРТ
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Сохраняем пользователя
    users_db[user.id] = {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'registered_at': datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
    }
    
    welcome = f"👋 Привет, {user.first_name}!\n\nЯ бот поддержки **LAST STAND**. Выбери действие:"
    await update.message.reply_text(welcome, reply_markup=get_main_keyboard(user.id), parse_mode='Markdown')

# ============================================
# ОБРАБОТЧИК КНОПОК
# ============================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    
    # === НАЗАД ===
    if data.startswith("back_"):
        back_to = data.replace("back_", "")
        if back_to == "main":
            await query.edit_message_text(
                "👋 Главное меню. Выбери действие:",
                reply_markup=get_main_keyboard(user_id)
            )
        elif back_to == "admin":
            await show_admin_panel(update, context)
        elif back_to == "list":
            await show_user_tickets(update, context)
        return
    
    # === О БОТЕ ===
    if data == "menu_about":
        text = (
            "ℹ️ **О боте**\n\n"
            "• Бот поддержки LAST STAND\n"
            "• Версия: 2.0.0\n"
            "• Разработка: @melonchikpvp\n\n"
            "По вопросам: @Suppmelo_bot"
        )
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard("main"))
        return
    
    # === СОЗДАНИЕ ОБРАЩЕНИЯ - ВЫБОР КАТЕГОРИИ ===
    if data == "menu_new":
        text = "📋 **Выбери категорию обращения:**\n\n"
        keyboard = []
        for key, cat in CATEGORIES.items():
            text += f"{cat['emoji']} **{cat['name']}** — {cat['desc']}\n"
            keyboard.append([InlineKeyboardButton(f"{cat['emoji']} {cat['name']}", callback_data=f"new_cat_{key}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_main")])
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # === ВЫБРАНА КАТЕГОРИЯ ===
    if data.startswith("new_cat_"):
        cat_key = data.replace("new_cat_", "")
        context.user_data['ticket_cat_key'] = cat_key
        context.user_data['ticket_cat_name'] = CATEGORIES[cat_key]['name']
        context.user_data['state'] = 'wait_description'
        
        await query.edit_message_text(
            f"📝 **Категория:** {CATEGORIES[cat_key]['name']}\n\n"
            "Опиши ситуацию подробно:\n"
            "• Ник игрока (если жалоба)\n"
            "• Время и координаты\n"
            "• Что произошло\n\n"
            "_Отправь описание одним сообщением_",
            parse_mode='Markdown'
        )
        return
    
    # === МОИ ОБРАЩЕНИЯ ===
    if data == "menu_list":
        await show_user_tickets(update, context)
        return
    
    # === ПРОСМОТР ОБРАЩЕНИЯ ===
    if data.startswith("view_"):
        ticket_id = int(data.replace("view_", ""))
        await show_ticket_details(update, context, ticket_id, user_id)
        return
    
    # === АДМИН-ПАНЕЛЬ ===
    if data == "admin_main" and user_id in ADMIN_IDS:
        await show_admin_panel(update, context)
        return
    
    # === АДМИН - СПИСОК ОТКРЫТЫХ ===
    if data == "admin_open" and user_id in ADMIN_IDS:
        await show_open_tickets(update, context)
        return
    
    # === АДМИН - ПРОСМОТР ОБРАЩЕНИЯ ===
    if data.startswith("admin_view_") and user_id in ADMIN_IDS:
        ticket_id = int(data.replace("admin_view_", ""))
        await show_admin_ticket(update, context, ticket_id)
        return
    
    # === АДМИН - ВЗЯТЬ В РАБОТУ ===
    if data.startswith("admin_take_") and user_id in ADMIN_IDS:
        ticket_id = int(data.replace("admin_take_", ""))
        if ticket_id in tickets_db and tickets_db[ticket_id]['status'] == 'open':
            tickets_db[ticket_id]['status'] = 'in_progress'
            tickets_db[ticket_id]['assigned_to'] = user_id
            
            # Уведомляем пользователя
            user_id = tickets_db[ticket_id]['user_id']
            try:
                await context.bot.send_message(
                    user_id,
                    f"🟡 Ваше обращение #{tickets_db[ticket_id]['number']} взято в работу администратором."
                )
            except:
                pass
            
            await query.answer("✅ Обращение взято в работу!")
            
            # Обновляем отображение
            await show_admin_ticket(update, context, ticket_id)
        return
    
    # === АДМИН - ЗАКРЫТЬ ОБРАЩЕНИЕ ===
    if data.startswith("admin_close_") and user_id in ADMIN_IDS:
        ticket_id = int(data.replace("admin_close_", ""))
        if ticket_id in tickets_db and tickets_db[ticket_id]['status'] != 'closed':
            tickets_db[ticket_id]['status'] = 'closed'
            
            # Уведомляем пользователя
            user_id = tickets_db[ticket_id]['user_id']
            try:
                await context.bot.send_message(
                    user_id,
                    f"🔵 Ваше обращение #{tickets_db[ticket_id]['number']} закрыто.\nСпасибо за обращение!"
                )
            except:
                pass
            
            await query.answer("✅ Обращение закрыто!")
            
            # Обновляем отображение
            await show_admin_ticket(update, context, ticket_id)
        return

# ============================================
# ПОКАЗ СПИСКА ОБРАЩЕНИЙ ПОЛЬЗОВАТЕЛЯ
# ============================================
async def show_user_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    
    user_tickets = [t for t in tickets_db.values() if t['user_id'] == user_id]
    
    if not user_tickets:
        await query.edit_message_text(
            "📭 У тебя пока нет обращений.",
            reply_markup=get_back_keyboard("main")
        )
        return
    
    # Сортируем по дате (сначала новые)
    user_tickets.sort(key=lambda x: x['created_at'], reverse=True)
    
    text = "📋 **Твои обращения:**\n\n"
    keyboard = []
    
    for ticket in user_tickets[:10]:
        status_emoji = {
            'open': '🟢',
            'in_progress': '🟡',
            'closed': '🔵',
            'rejected': '🔴'
        }.get(ticket['status'], '⚪')
        
        created = ticket['created_at'].split()[0]  # только дата
        text += f"{status_emoji} **#{ticket['number']}** — {ticket['category']} ({created})\n"
        keyboard.append([InlineKeyboardButton(
            f"{status_emoji} #{ticket['number']} — {ticket['category']}",
            callback_data=f"view_{ticket['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_main")])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# ПОКАЗ ДЕТАЛЕЙ ОБРАЩЕНИЯ
# ============================================
async def show_ticket_details(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id, user_id):
    query = update.callback_query
    
    if ticket_id not in tickets_db:
        await query.edit_message_text("❌ Обращение не найдено.", reply_markup=get_back_keyboard("list"))
        return
    
    ticket = tickets_db[ticket_id]
    
    # Проверка доступа
    if ticket['user_id'] != user_id and user_id not in ADMIN_IDS:
        await query.edit_message_text("⛔ Нет доступа.", reply_markup=get_back_keyboard("list"))
        return
    
    status_text = {
        'open': '🟢 Открыто',
        'in_progress': '🟡 В работе',
        'closed': '🔵 Закрыто',
        'rejected': '🔴 Отклонено'
    }.get(ticket['status'], '⚪ Неизвестно')
    
    text = (
        f"📋 **Обращение #{ticket['number']}**\n\n"
        f"📌 **Категория:** {ticket['category']}\n"
        f"📊 **Статус:** {status_text}\n"
        f"📅 **Создано:** {ticket['created_at']}\n\n"
        f"📝 **Описание:**\n{ticket['description']}\n"
    )
    
    if ticket['proof']:
        text += f"\n📎 **Доказательства:** {ticket['proof']}\n"
    
    if ticket.get('admin_reply'):
        text += f"\n💬 **Ответ:**\n{ticket['admin_reply']}\n"
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_back_keyboard("list"))

# ============================================
# АДМИН-ПАНЕЛЬ
# ============================================
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    total = len(tickets_db)
    open_tickets = len([t for t in tickets_db.values() if t['status'] == 'open'])
    progress = len([t for t in tickets_db.values() if t['status'] == 'in_progress'])
    closed = len([t for t in tickets_db.values() if t['status'] == 'closed'])
    
    text = (
        f"👑 **Админ-панель**\n\n"
        f"📊 **Статистика:**\n"
        f"• Всего: {total}\n"
        f"• 🟢 Открыто: {open_tickets}\n"
        f"• 🟡 В работе: {progress}\n"
        f"• 🔵 Закрыто: {closed}\n"
    )
    
    keyboard = [
        [InlineKeyboardButton("📋 Открытые обращения", callback_data="admin_open")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_main")]
    ]
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# АДМИН - СПИСОК ОТКРЫТЫХ ОБРАЩЕНИЙ
# ============================================
async def show_open_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    open_tickets = [t for t in tickets_db.values() if t['status'] in ['open', 'in_progress']]
    open_tickets.sort(key=lambda x: x['created_at'], reverse=True)
    
    if not open_tickets:
        await query.edit_message_text(
            "📭 Нет открытых обращений.",
            reply_markup=get_back_keyboard("admin")
        )
        return
    
    text = "📋 **Открытые обращения:**\n\n"
    keyboard = []
    
    for ticket in open_tickets[:10]:
        status_emoji = '🟡' if ticket['status'] == 'in_progress' else '🟢'
        user = users_db.get(ticket['user_id'], {})
        username = user.get('username', 'неизвестно')
        created = ticket['created_at'].split()[0]
        
        text += f"{status_emoji} **#{ticket['number']}** — @{username} ({created})\n"
        keyboard.append([InlineKeyboardButton(
            f"{status_emoji} #{ticket['number']} — @{username}",
            callback_data=f"admin_view_{ticket['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_admin")])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# АДМИН - ПРОСМОТР ОБРАЩЕНИЯ
# ============================================
async def show_admin_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id):
    query = update.callback_query
    
    if ticket_id not in tickets_db:
        await query.edit_message_text("❌ Обращение не найдено.", reply_markup=get_back_keyboard("admin"))
        return
    
    ticket = tickets_db[ticket_id]
    user = users_db.get(ticket['user_id'], {})
    
    status_text = {
        'open': '🟢 Открыто',
        'in_progress': '🟡 В работе',
        'closed': '🔵 Закрыто',
        'rejected': '🔴 Отклонено'
    }.get(ticket['status'], '⚪')
    
    text = (
        f"📋 **Обращение #{ticket['number']}**\n\n"
        f"👤 **Пользователь:** @{user.get('username', '?')}\n"
        f"📌 **Категория:** {ticket['category']}\n"
        f"📊 **Статус:** {status_text}\n"
        f"📅 **Создано:** {ticket['created_at']}\n\n"
        f"📝 **Описание:**\n{ticket['description']}\n"
    )
    
    if ticket['proof']:
        text += f"\n📎 **Доказательства:** {ticket['proof']}\n"
    
    # Кнопки действий
    keyboard = []
    
    if ticket['status'] == 'open':
        keyboard.append([InlineKeyboardButton("✅ Взять в работу", callback_data=f"admin_take_{ticket_id}")])
    
    if ticket['status'] in ['open', 'in_progress']:
        keyboard.append([InlineKeyboardButton("🔒 Закрыть обращение", callback_data=f"admin_close_{ticket_id}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_open")])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# ОБРАБОТЧИК ТЕКСТА (СОЗДАНИЕ ОБРАЩЕНИЯ)
# ============================================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ticket_counter
    user_id = update.effective_user.id
    
    # Проверяем состояние
    if context.user_data.get('state') != 'wait_description':
        await update.message.reply_text(
            "❓ Используй кнопки в меню.",
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    # Получаем описание
    description = update.message.text
    cat_key = context.user_data.get('ticket_cat_key', '6')
    cat_name = context.user_data.get('ticket_cat_name', '💡 Предложение')
    
    # Создаём обращение
    ticket_counter += 1
    date_str = datetime.datetime.now().strftime('%Y%m%d')
    ticket_number = f"LS-{date_str}-{ticket_counter:04d}"
    
    tickets_db[ticket_counter] = {
        'id': ticket_counter,
        'number': ticket_number,
        'user_id': user_id,
        'category': cat_name,
        'description': description,
        'proof': '',
        'status': 'open',
        'created_at': datetime.datetime.now().strftime('%d.%m.%Y %H:%M'),
        'admin_reply': None,
        'assigned_to': None
    }
    
    # Уведомляем админов
    user = update.effective_user
    for admin_id in ADMIN_IDS:
        try:
            keyboard = [[InlineKeyboardButton(
                "📋 Посмотреть", callback_data=f"admin_view_{ticket_counter}"
            )]]
            await context.bot.send_message(
                admin_id,
                f"🆕 **Новое обращение!**\n\n"
                f"📋 Номер: #{ticket_number}\n"
                f"👤 От: @{user.username}\n"
                f"📌 Категория: {cat_name}\n"
                f"📝 Описание: {description[:100]}...\n",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Ошибка отправки админу: {e}")
    
    # Очищаем состояние
    context.user_data.clear()
    
    # Отвечаем пользователю
    await update.message.reply_text(
        f"✅ **Обращение создано!**\n\n"
        f"Номер: #{ticket_number}\n"
        f"Категория: {cat_name}\n\n"
        f"Администратор ответит в ближайшее время.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ В меню", callback_data="back_main")
        ]])
    )

# ============================================
# ЗАПУСК
# ============================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    print("=" * 50)
    print("🚀 Бот поддержки LAST STAND запущен!")
    print(f"📊 ID администратора: {ADMIN_IDS[0]}")
    print("📡 Ожидание сообщений...")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
