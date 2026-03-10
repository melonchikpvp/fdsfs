import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ConversationHandler, ContextTypes
)
import datetime
import uuid

# ============================================
# ДАННЫЕ УЖЕ ВСТАВЛЕНЫ - НИЧЕГО НЕ МЕНЯЙ!
# ============================================

# Токен бота (уже твой)
BOT_TOKEN = "8548246370:AAEYqEVTSdslgQNQPAqo6xh_PEcbnRajt6M"

# Твой Telegram ID (уже вставлен)
ADMIN_IDS = [6979197416]  # Если нужно добавить ещё, напиши через запятую: [6979197416, 123456789]

# ============================================
# СОСТОЯНИЯ ДЛЯ ДИАЛОГОВ
# ============================================
CATEGORY, DESCRIPTION, PROOF = range(3)

# ============================================
# КАТЕГОРИИ ОБРАЩЕНИЙ
# ============================================
CATEGORIES = {
    "1": "👤 Жалоба на игрока",
    "2": "📦 Возврат ресурсов / Откат",
    "3": "❓ Вопрос по правилам",
    "4": "🛠 Связь с администрацией",
    "5": "🐞 Сообщить о баге",
    "6": "💡 Предложение / Идея"
}

# ============================================
# ВРЕМЕННОЕ ХРАНИЛИЩЕ (вместо базы данных)
# ============================================
users_db = {}
tickets_db = {}
ticket_counter = 0
ticket_messages = {}

# ============================================
# ЛОГИРОВАНИЕ
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# ОСНОВНЫЕ ФУНКЦИИ
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Сохраняем пользователя
    users_db[user.id] = {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'registered_at': datetime.datetime.now().isoformat()
    }
    
    # Создаём клавиатуру
    keyboard = [
        [InlineKeyboardButton("📝 Создать обращение", callback_data="new_ticket")],
        [InlineKeyboardButton("📋 Мои обращения", callback_data="my_tickets")],
        [InlineKeyboardButton("ℹ️ О боте", callback_data="about")]
    ]
    
    # Если пользователь админ, добавляем кнопку админ-панели
    if user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я бот поддержки сервера **LAST STAND**.\n"
        "Здесь ты можешь создать обращение, сообщить о проблеме или задать вопрос.\n\n"
        "Выбери действие:"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "new_ticket":
        # Показываем категории
        keyboard = []
        for key, value in CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(value, callback_data=f"cat_{key}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
        
        await query.edit_message_text(
            "📋 Выбери категорию обращения:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CATEGORY
        
    elif query.data == "my_tickets":
        await show_user_tickets(update, context)
        
    elif query.data == "about":
        await query.edit_message_text(
            "ℹ️ **О боте**\n\n"
            "Бот поддержки сервера LAST STAND\n"
            "Версия: 1.0.0\n"
            "Разработка: @melonchikpvp\n\n"
            "По всем вопросам: @Suppmelo_bot",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")
            ]])
        )
        
    elif query.data == "back_to_main":
        await back_to_main(update, context)
        
    elif query.data == "admin_panel":
        await admin_panel(update, context)
        
    elif query.data == "admin_list_open":
        await admin_list_open(update, context)
        
    elif query.data.startswith("cat_"):
        # Сохраняем выбранную категорию
        cat_key = query.data.replace("cat_", "")
        context.user_data['ticket_category'] = CATEGORIES[cat_key]
        
        await query.edit_message_text(
            f"📝 Выбрана категория: **{CATEGORIES[cat_key]}**\n\n"
            "Опиши подробно ситуацию. Укажи:\n"
            "• Ник игрока (если жалоба)\n"
            "• Время и координаты\n"
            "• Что произошло\n\n"
            "Отправь описание одним сообщением:",
            parse_mode='Markdown'
        )
        return DESCRIPTION
        
    elif query.data.startswith("ticket_"):
        # Просмотр конкретного обращения
        ticket_id = int(query.data.replace("ticket_", ""))
        await show_ticket_details(update, context, ticket_id)
        
    elif query.data.startswith("admin_ticket_"):
        ticket_id = int(query.data.replace("admin_ticket_", ""))
        await admin_ticket_detail(update, context, ticket_id)
        
    elif query.data.startswith("admin_take_"):
        ticket_id = int(query.data.replace("admin_take_", ""))
        await admin_take_ticket(update, context, ticket_id)
        
    elif query.data.startswith("admin_close_"):
        ticket_id = int(query.data.replace("admin_close_", ""))
        await admin_close_ticket(update, context, ticket_id)
        
    elif query.data.startswith("admin_reject_"):
        ticket_id = int(query.data.replace("admin_reject_", ""))
        await admin_reject_ticket(update, context, ticket_id)

async def show_user_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список обращений пользователя"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    user_tickets = [t for t in tickets_db.values() if t['user_id'] == user_id]
    
    if not user_tickets:
        await query.edit_message_text(
            "📭 У тебя пока нет обращений.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")
            ]])
        )
        return
    
    user_tickets.sort(key=lambda x: x['created_at'], reverse=True)
    text = "📋 **Твои обращения:**\n\n"
    
    keyboard = []
    for ticket in user_tickets[:5]:
        status_emoji = {
            'open': '🟢',
            'in_progress': '🟡',
            'closed': '🔵',
            'rejected': '🔴'
        }.get(ticket['status'], '⚪')
        
        text += f"{status_emoji} #{ticket['number']} - {ticket['category']}\n"
        keyboard.append([InlineKeyboardButton(
            f"#{ticket['number']} ({ticket['category']})", 
            callback_data=f"ticket_{ticket['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_ticket_details(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id):
    """Показывает детали обращения"""
    query = update.callback_query
    
    if ticket_id not in tickets_db:
        await query.edit_message_text("❌ Обращение не найдено.")
        return
    
    ticket = tickets_db[ticket_id]
    user = users_db.get(ticket['user_id'], {})
    
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
        text += f"\n💬 **Ответ администрации:**\n{ticket['admin_reply']}\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="my_tickets")]]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    keyboard = [
        [InlineKeyboardButton("📝 Создать обращение", callback_data="new_ticket")],
        [InlineKeyboardButton("📋 Мои обращения", callback_data="my_tickets")],
        [InlineKeyboardButton("ℹ️ О боте", callback_data="about")]
    ]
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
    
    await query.edit_message_text(
        "👋 Главное меню. Выбери действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает описание обращения"""
    description = update.message.text
    context.user_data['ticket_description'] = description
    
    await update.message.reply_text(
        "📎 Пришли ссылки на доказательства (скриншоты, видео) или напиши 'нет', если доказательств нет:"
    )
    return PROOF

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получает доказательства и создаёт обращение"""
    global ticket_counter
    
    proof = update.message.text
    if proof.lower() == 'нет':
        proof = ''
    
    user = update.effective_user
    
    # Создаём обращение
    ticket_counter += 1
    ticket_id = ticket_counter
    
    # Генерируем номер обращения
    date_str = datetime.datetime.now().strftime('%Y%m%d')
    ticket_number = f"LS-{date_str}-{ticket_id:04d}"
    
    tickets_db[ticket_id] = {
        'id': ticket_id,
        'number': ticket_number,
        'user_id': user.id,
        'category': context.user_data['ticket_category'],
        'description': context.user_data['ticket_description'],
        'proof': proof,
        'status': 'open',
        'created_at': datetime.datetime.now().strftime('%d.%m.%Y %H:%M'),
        'messages': []
    }
    
    # Отправляем уведомление админам
    for admin_id in ADMIN_IDS:
        try:
            keyboard = [[InlineKeyboardButton(
                "📋 Посмотреть обращение", 
                callback_data=f"admin_ticket_{ticket_id}"
            )]]
            
            await context.bot.send_message(
                admin_id,
                f"🆕 **Новое обращение!**\n\n"
                f"📋 Номер: #{ticket_number}\n"
                f"👤 От: {user.full_name} (@{user.username})\n"
                f"📌 Категория: {tickets_db[ticket_id]['category']}\n"
                f"📝 Описание: {tickets_db[ticket_id]['description'][:100]}...\n",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            pass
    
    # Очищаем временные данные
    context.user_data.clear()
    
    await update.message.reply_text(
        f"✅ **Обращение создано!**\n\n"
        f"Номер: #{ticket_number}\n"
        f"Категория: {tickets_db[ticket_id]['category']}\n\n"
        f"Администратор ответит в ближайшее время. Ты получишь уведомление.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_main")
        ]])
    )
    
    return ConversationHandler.END

# ============================================
# АДМИН-ФУНКЦИИ
# ============================================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-панель"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("⛔ У тебя нет доступа к админ-панели.")
        return
    
    # Статистика
    total_tickets = len(tickets_db)
    open_tickets = len([t for t in tickets_db.values() if t['status'] == 'open'])
    in_progress = len([t for t in tickets_db.values() if t['status'] == 'in_progress'])
    closed = len([t for t in tickets_db.values() if t['status'] == 'closed'])
    
    keyboard = [
        [InlineKeyboardButton("📋 Открытые обращения", callback_data="admin_list_open")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]
    
    text = (
        f"👑 **Админ-панель**\n\n"
        f"📊 **Статистика:**\n"
        f"• Всего обращений: {total_tickets}\n"
        f"• Открыто: {open_tickets}\n"
        f"• В работе: {in_progress}\n"
        f"• Закрыто: {closed}\n"
    )
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def admin_list_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список открытых обращений"""
    query = update.callback_query
    
    open_tickets = [t for t in tickets_db.values() if t['status'] in ['open', 'in_progress']]
    open_tickets.sort(key=lambda x: x['created_at'], reverse=True)
    
    if not open_tickets:
        await query.edit_message_text(
            "📭 Нет открытых обращений.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")
            ]])
        )
        return
    
    text = "📋 **Открытые обращения:**\n\n"
    keyboard = []
    
    for ticket in open_tickets[:10]:
        status_emoji = '🟡' if ticket['status'] == 'in_progress' else '🟢'
        user = users_db.get(ticket['user_id'], {})
        username = user.get('username', 'Неизвестно')
        text += f"{status_emoji} #{ticket['number']} - @{username}\n"
        keyboard.append([InlineKeyboardButton(
            f"#{ticket['number']} ({ticket['category']})", 
            callback_data=f"admin_ticket_{ticket['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def admin_ticket_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id):
    """Детали обращения для админа"""
    query = update.callback_query
    
    if ticket_id not in tickets_db:
        await query.edit_message_text("❌ Обращение не найдено.")
        return
    
    ticket = tickets_db[ticket_id]
    user = users_db.get(ticket['user_id'], {})
    
    status_text = {
        'open': '🟢 Открыто',
        'in_progress': '🟡 В работе',
        'closed': '🔵 Закрыто',
        'rejected': '🔴 Отклонено'
    }.get(ticket['status'], '⚪ Неизвестно')
    
    username = user.get('username', 'Неизвестно')
    first_name = user.get('first_name', '')
    
    text = (
        f"📋 **Обращение #{ticket['number']}**\n\n"
        f"👤 **Пользователь:** {first_name} (@{username})\n"
        f"📌 **Категория:** {ticket['category']}\n"
        f"📊 **Статус:** {status_text}\n"
        f"📅 **Создано:** {ticket['created_at']}\n\n"
        f"📝 **Описание:**\n{ticket['description']}\n"
    )
    
    if ticket['proof']:
        text += f"\n📎 **Доказательства:** {ticket['proof']}\n"
    
    if ticket.get('admin_reply'):
        text += f"\n💬 **Ваш ответ:**\n{ticket['admin_reply']}\n"
    
    keyboard = []
    
    if ticket['status'] == 'open':
        keyboard.append([InlineKeyboardButton("✅ Взять в работу", callback_data=f"admin_take_{ticket_id}")])
    
    keyboard.append([InlineKeyboardButton("💬 Ответить", callback_data=f"admin_reply_{ticket_id}")])
    
    if ticket['status'] != 'closed':
        keyboard.append([InlineKeyboardButton("🔒 Закрыть", callback_data=f"admin_close_{ticket_id}")])
        keyboard.append([InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_reject_{ticket_id}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_list_open")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def admin_take_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id):
    """Взять обращение в работу"""
    query = update.callback_query
    
    if ticket_id in tickets_db:
        tickets_db[ticket_id]['status'] = 'in_progress'
        
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
    await admin_ticket_detail(update, context, ticket_id)

async def admin_close_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id):
    """Закрыть обращение"""
    query = update.callback_query
    
    if ticket_id in tickets_db:
        tickets_db[ticket_id]['status'] = 'closed'
        
        # Уведомляем пользователя
        user_id = tickets_db[ticket_id]['user_id']
        try:
            await context.bot.send_message(
                user_id,
                f"🔵 Ваше обращение #{tickets_db[ticket_id]['number']} закрыто.\n"
                f"Спасибо за обращение!"
            )
        except:
            pass
    
    await query.answer("✅ Обращение закрыто!")
    await admin_ticket_detail(update, context, ticket_id)

async def admin_reject_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id):
    """Отклонить обращение"""
    query = update.callback_query
    
    if ticket_id in tickets_db:
        tickets_db[ticket_id]['status'] = 'rejected'
        
        # Уведомляем пользователя
        user_id = tickets_db[ticket_id]['user_id']
        try:
            await context.bot.send_message(
                user_id,
                f"🔴 Ваше обращение #{tickets_db[ticket_id]['number']} отклонено.\n"
                f"Причина: не соответствует правилам."
            )
        except:
            pass
    
    await query.answer("✅ Обращение отклонено!")
    await admin_ticket_detail(update, context, ticket_id)

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена действия"""
    await update.message.reply_text(
        "❌ Действие отменено.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_main")
        ]])
    )
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка. Попробуй позже или обратись к @Suppmelo_bot"
        )

# ============================================
# ЗАПУСК БОТА
# ============================================

def main():
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start))
    
    # Обработчик нажатий на кнопки (основной)
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # ConversationHandler для создания обращения
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^new_ticket$")],
        states={
            CATEGORY: [CallbackQueryHandler(button_callback, pattern="^cat_")],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)],
            PROOF: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_proof)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запуск бота
    print("🚀 Бот поддержки LAST STAND запущен!")
    print(f"📊 ID администраторов: {ADMIN_IDS}")
    print("📡 Ожидание сообщений...")
    
    application.run_polling(allowed_updates=['message', 'callback_query'])

if __name__ == '__main__':
    main()
