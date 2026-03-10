from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import datetime
import uuid

from database import User, Ticket, TicketMessage
from config import ADMIN_IDS

# Состояния для ConversationHandler
CATEGORY, DESCRIPTION, PROOF, ADMIN_REPLY, ADMIN_ACTION = range(5)

# Категории обращений
CATEGORIES = {
    "1": "👤 Жалоба на игрока",
    "2": "📦 Возврат ресурсов / Откат",
    "3": "❓ Вопрос по правилам",
    "4": "🛠 Связь с администрацией",
    "5": "🐞 Сообщить о баге",
    "6": "💡 Предложение / Идея"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Сохраняем или обновляем пользователя в базе
    session = context.bot_data['session']()
    db_user = session.query(User).filter_by(telegram_id=user.id).first()
    
    if not db_user:
        db_user = User(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        session.add(db_user)
        session.commit()
    
    session.close()
    
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
        ticket_id = query.data.replace("ticket_", "")
        await show_ticket_details(update, context, ticket_id)

async def show_user_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список обращений пользователя"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    session = context.bot_data['session']()
    db_user = session.query(User).filter_by(telegram_id=user_id).first()
    
    if not db_user or not db_user.tickets:
        await query.edit_message_text(
            "📭 У тебя пока нет обращений.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")
            ]])
        )
        session.close()
        return
    
    tickets = db_user.tickets
    text = "📋 **Твои обращения:**\n\n"
    
    keyboard = []
    for ticket in tickets[-5:]:  # Показываем последние 5
        status_emoji = {
            'open': '🟢',
            'in_progress': '🟡',
            'closed': '🔵',
            'rejected': '🔴'
        }.get(ticket.status, '⚪')
        
        text += f"{status_emoji} #{ticket.ticket_number} - {ticket.category}\n"
        keyboard.append([InlineKeyboardButton(
            f"#{ticket.ticket_number} ({ticket.category})", 
            callback_data=f"ticket_{ticket.id}"
        )])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    session.close()

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("📝 Создать обращение", callback_data="new_ticket")],
        [InlineKeyboardButton("📋 Мои обращения", callback_data="my_tickets")],
        [InlineKeyboardButton("ℹ️ О боте", callback_data="about")]
    ]
    
    user_id = update.effective_user.id
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
    proof = update.message.text
    if proof.lower() == 'нет':
        proof = ''
    
    user = update.effective_user
    
    # Создаём обращение в базе
    session = context.bot_data['session']()
    
    # Получаем или создаём пользователя
    db_user = session.query(User).filter_by(telegram_id=user.id).first()
    if not db_user:
        db_user = User(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        session.add(db_user)
        session.commit()
    
    # Генерируем номер обращения
    ticket_number = f"LS-{datetime.datetime.now().strftime('%Y%m%d')}-{db_user.total_tickets + 1:04d}"
    
    # Создаём обращение
    ticket = Ticket(
        ticket_number=ticket_number,
        user_id=db_user.id,
        category=context.user_data['ticket_category'],
        description=context.user_data['ticket_description'],
        proof=proof,
        status='open'
    )
    session.add(ticket)
    db_user.total_tickets += 1
    session.commit()
    
    # Отправляем уведомление админам
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"🆕 **Новое обращение!**\n\n"
                f"📋 Номер: #{ticket_number}\n"
                f"👤 От: {user.full_name} (@{user.username})\n"
                f"📌 Категория: {ticket.category}\n"
                f"📝 Описание: {ticket.description[:200]}...\n\n"
                f"Для ответа используй команду:\n"
                f"`/reply {ticket.id} [текст]`",
                parse_mode='Markdown'
            )
        except:
            pass
    
    session.close()
    
    # Очищаем временные данные
    context.user_data.clear()
    
    await update.message.reply_text(
        f"✅ **Обращение создано!**\n\n"
        f"Номер: #{ticket_number}\n"
        f"Категория: {ticket.category}\n\n"
        f"Администратор ответит в ближайшее время. Ты получишь уведомление.",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_main")
        ]])
    )
    
    return ConversationHandler.END

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-панель"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("⛔ У тебя нет доступа к админ-панели.")
        return
    
    session = context.bot_data['session']()
    
    # Статистика
    total_tickets = session.query(Ticket).count()
    open_tickets = session.query(Ticket).filter_by(status='open').count()
    in_progress = session.query(Ticket).filter_by(status='in_progress').count()
    closed_today = session.query(Ticket).filter(
        Ticket.closed_at >= datetime.datetime.utcnow().date()
    ).count()
    
    session.close()
    
    keyboard = [
        [InlineKeyboardButton("📋 Открытые обращения", callback_data="admin_list_open")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
    ]
    
    text = (
        f"👑 **Админ-панель**\n\n"
        f"📊 **Статистика:**\n"
        f"• Всего обращений: {total_tickets}\n"
        f"• Открыто: {open_tickets}\n"
        f"• В работе: {in_progress}\n"
        f"• Закрыто сегодня: {closed_today}\n"
    )
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def admin_list_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список открытых обращений для админа"""
    query = update.callback_query
    
    session = context.bot_data['session']()
    open_tickets = session.query(Ticket).filter(Ticket.status.in_(['open', 'in_progress'])).order_by(Ticket.created_at.desc()).limit(10).all()
    session.close()
    
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
    
    for ticket in open_tickets:
        status_emoji = '🟡' if ticket.status == 'in_progress' else '🟢'
        text += f"{status_emoji} #{ticket.ticket_number} - {ticket.category}\n"
        keyboard.append([InlineKeyboardButton(
            f"#{ticket.ticket_number} ({ticket.category})", 
            callback_data=f"admin_ticket_{ticket.id}"
        )])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def admin_ticket_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id):
    """Детали обращения для админа"""
    query = update.callback_query
    
    session = context.bot_data['session']()
    ticket = session.query(Ticket).get(ticket_id)
    
    if not ticket:
        await query.edit_message_text("❌ Обращение не найдено.")
        session.close()
        return
    
    user = ticket.user
    
    text = (
        f"📋 **Обращение #{ticket.ticket_number}**\n\n"
        f"👤 **Пользователь:** {user.first_name} @{user.username}\n"
        f"📌 **Категория:** {ticket.category}\n"
        f"🟢 **Статус:** {ticket.status}\n"
        f"📅 **Создано:** {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"📝 **Описание:**\n{ticket.description}\n\n"
    )
    
    if ticket.proof:
        text += f"📎 **Доказательства:** {ticket.proof}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("✅ Взять в работу", callback_data=f"admin_take_{ticket.id}")],
        [InlineKeyboardButton("💬 Ответить", callback_data=f"admin_reply_{ticket.id}")],
        [InlineKeyboardButton("🔒 Закрыть", callback_data=f"admin_close_{ticket.id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_reject_{ticket.id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_list_open")]
    ]
    
    session.close()
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

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
    print(f"Ошибка: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Произошла ошибка. Попробуй позже или обратись к @Suppmelo_bot"
        )