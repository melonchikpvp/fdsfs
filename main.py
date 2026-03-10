import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import datetime
import asyncio
from collections import defaultdict

# ============================================
# ДАННЫЕ (ТВОИ - УЖЕ ВСТАВЛЕНЫ)
# ============================================
BOT_TOKEN = "8548246370:AAEYqEVTSdslgQNQPAqo6xh_PEcbnRajt6M"
ADMIN_IDS = [6979197416]

# ============================================
# ЗАЩИТА ОТ СПАМА
# ============================================
user_cooldown = defaultdict(lambda: 0)  # Время последнего действия
user_message_count = defaultdict(list)  # Счетчик сообщений для анти-флуда

# ============================================
# КАТЕГОРИИ
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
# ПРОВЕРКА НА СПАМ
# ============================================
def check_spam(user_id):
    """Проверяет, не спамит ли пользователь"""
    now = datetime.datetime.now().timestamp()
    
    # Проверка на частоту сообщений (не больше 5 за 10 секунд)
    user_message_count[user_id] = [t for t in user_message_count[user_id] if now - t < 10]
    if len(user_message_count[user_id]) >= 5:
        return True
    
    user_message_count[user_id].append(now)
    return False

# ============================================
# ГЛАВНОЕ МЕНЮ
# ============================================
async def main_menu(update, context, user_id, text="👋 **Главное меню**\nВыбери действие:", edit=True):
    """Показывает главное меню"""
    keyboard = [
        [InlineKeyboardButton("📝 Создать обращение", callback_data="new_ticket")],
        [InlineKeyboardButton("📋 Мои обращения", callback_data="my_tickets")],
        [InlineKeyboardButton("ℹ️ О боте", callback_data="about")]
    ]
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Ошибка меню: {e}")

# ============================================
# START
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Проверка на спам
    if check_spam(user.id):
        await update.message.reply_text("⏳ Не так быстро! Подожди немного.")
        return
    
    # Сохраняем пользователя
    users_db[user.id] = {
        'id': user.id,
        'username': user.username or "None",
        'first_name': user.first_name or "None",
        'last_name': user.last_name or "None",
        'registered_at': datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
    }
    
    logger.info(f"Новый пользователь: {user.id} (@{user.username})")
    await main_menu(update, context, user.id, edit=False)

# ============================================
# ОБРАБОТЧИК КНОПОК
# ============================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает все нажатия на кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    # Проверка на спам
    if check_spam(user_id):
        await query.edit_message_text("⏳ Не так быстро! Подожди немного.")
        return
    
    # ===== НАЗАД В ГЛАВНОЕ МЕНЮ =====
    if data == "back_to_main":
        await main_menu(update, context, user_id)
        return
    
    # ===== О БОТЕ =====
    if data == "about":
        text = (
            "ℹ️ **О боте**\n\n"
            "🤖 **LAST STAND Support Bot**\n"
            "Версия: **2.0.0**\n"
            "Разработчик: @melonchikpvp\n\n"
            "📌 **Возможности:**\n"
            "• Создание обращений\n"
            "• Отслеживание статуса\n"
            "• Уведомления в реальном времени\n"
            "• Админ-панель\n\n"
            "По вопросам: @Suppmelo_bot"
        )
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # ===== СОЗДАНИЕ ОБРАЩЕНИЯ - ВЫБОР КАТЕГОРИИ =====
    if data == "new_ticket":
        keyboard = []
        for key, value in CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(value, callback_data=f"cat_{key}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
        
        await query.edit_message_text(
            "📋 **Выбери категорию обращения:**",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # ===== КАТЕГОРИЯ ВЫБРАНА =====
    if data.startswith("cat_"):
        cat_key = data.replace("cat_", "")
        context.user_data['ticket_category'] = CATEGORIES[cat_key]
        context.user_data['waiting_for'] = 'description'
        
        await query.edit_message_text(
            f"📝 **Категория:** {CATEGORIES[cat_key]}\n\n"
            "✍️ **Опиши ситуацию:**\n"
            "• Ник игрока (если есть)\n"
            "• Время и координаты\n"
            "• Что произошло\n\n"
            "_Отправь описание одним сообщением_",
            parse_mode='Markdown'
        )
        return
    
    # ===== МОИ ОБРАЩЕНИЯ =====
    if data == "my_tickets":
        user_tickets = [t for t in tickets_db.values() if t['user_id'] == user_id]
        
        if not user_tickets:
            await query.edit_message_text(
                "📭 **У тебя пока нет обращений**",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")
                ]])
            )
            return
        
        # Сортируем по дате (новые сверху)
        user_tickets.sort(key=lambda x: x['created_at'], reverse=True)
        
        text = "📋 **Твои обращения:**\n\n"
        keyboard = []
        
        for ticket in user_tickets[:10]:  # Показываем последние 10
            status_emoji = {
                'open': '🟢',
                'in_progress': '🟡',
                'closed': '🔵',
                'rejected': '🔴'
            }.get(ticket['status'], '⚪')
            
            text += f"{status_emoji} **#{ticket['number']}** - {ticket['category']}\n"
            keyboard.append([InlineKeyboardButton(
                f"#{ticket['number']} ({ticket['category'][:20]}...)",
                callback_data=f"view_{ticket['id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # ===== ПРОСМОТР ОБРАЩЕНИЯ =====
    if data.startswith("view_"):
        ticket_id = int(data.replace("view_", ""))
        ticket = tickets_db.get(ticket_id)
        
        if not ticket:
            await query.edit_message_text(
                "❌ **Обращение не найдено**",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="my_tickets")
                ]])
            )
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
        
        if ticket.get('proof'):
            text += f"\n📎 **Доказательства:**\n{ticket['proof']}\n"
        
        if ticket.get('admin_reply'):
            text += f"\n💬 **Ответ админа:**\n{ticket['admin_reply']}\n"
        
        if ticket.get('admin_name'):
            text += f"\n👤 **Администратор:** {ticket['admin_name']}\n"
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="my_tickets")
            ]])
        )
        return
    
    # ===== АДМИН-ПАНЕЛЬ =====
    if data == "admin_panel" and user_id in ADMIN_IDS:
        total = len(tickets_db)
        open_tickets = len([t for t in tickets_db.values() if t['status'] == 'open'])
        in_progress = len([t for t in tickets_db.values() if t['status'] == 'in_progress'])
        closed = len([t for t in tickets_db.values() if t['status'] == 'closed'])
        rejected = len([t for t in tickets_db.values() if t['status'] == 'rejected'])
        
        text = (
            f"👑 **Админ-панель**\n\n"
            f"📊 **Статистика:**\n"
            f"• Всего: **{total}**\n"
            f"• 🟢 Открыто: **{open_tickets}**\n"
            f"• 🟡 В работе: **{in_progress}**\n"
            f"• 🔵 Закрыто: **{closed}**\n"
            f"• 🔴 Отклонено: **{rejected}**\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("📋 Открытые обращения", callback_data="admin_open")],
            [InlineKeyboardButton("📊 Вся статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
        ]
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # ===== СПИСОК ОТКРЫТЫХ (АДМИН) =====
    if data == "admin_open" and user_id in ADMIN_IDS:
        open_tickets = [t for t in tickets_db.values() if t['status'] in ['open', 'in_progress']]
        open_tickets.sort(key=lambda x: x['created_at'], reverse=True)
        
        if not open_tickets:
            await query.edit_message_text(
                "📭 **Нет открытых обращений**",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")
                ]])
            )
            return
        
        text = "📋 **Открытые обращения:**\n\n"
        keyboard = []
        
        for ticket in open_tickets[:15]:  # Показываем до 15
            status_emoji = '🟡' if ticket['status'] == 'in_progress' else '🟢'
            user = users_db.get(ticket['user_id'], {})
            username = user.get('username', 'неизвестно')
            
            text += f"{status_emoji} **#{ticket['number']}** - @{username}\n"
            keyboard.append([InlineKeyboardButton(
                f"#{ticket['number']} - @{username}",
                callback_data=f"admin_view_{ticket['id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")])
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # ===== ПРОСМОТР ОБРАЩЕНИЯ (АДМИН) =====
    if data.startswith("admin_view_") and user_id in ADMIN_IDS:
        ticket_id = int(data.replace("admin_view_", ""))
        ticket = tickets_db.get(ticket_id)
        
        if not ticket:
            await query.edit_message_text(
                "❌ **Обращение не найдено**",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="admin_open")
                ]])
            )
            return
        
        user = users_db.get(ticket['user_id'], {})
        username = user.get('username', 'неизвестно')
        
        status_text = {
            'open': '🟢 Открыто',
            'in_progress': '🟡 В работе',
            'closed': '🔵 Закрыто',
            'rejected': '🔴 Отклонено'
        }.get(ticket['status'], '⚪ Неизвестно')
        
        text = (
            f"📋 **Обращение #{ticket['number']}**\n\n"
            f"👤 **Пользователь:** @{username}\n"
            f"📌 **Категория:** {ticket['category']}\n"
            f"📊 **Статус:** {status_text}\n"
            f"📅 **Создано:** {ticket['created_at']}\n\n"
            f"📝 **Описание:**\n{ticket['description']}\n"
        )
        
        if ticket.get('proof'):
            text += f"\n📎 **Доказательства:**\n{ticket['proof']}\n"
        
        if ticket.get('admin_reply'):
            text += f"\n💬 **Ответ:**\n{ticket['admin_reply']}\n"
        
        keyboard = []
        
        if ticket['status'] == 'open':
            keyboard.append([InlineKeyboardButton("✅ Взять в работу", callback_data=f"admin_take_{ticket_id}")])
        
        if ticket['status'] != 'closed' and ticket['status'] != 'rejected':
            keyboard.append([InlineKeyboardButton("📝 Ответить", callback_data=f"admin_reply_{ticket_id}")])
            keyboard.append([InlineKeyboardButton("🔒 Закрыть", callback_data=f"admin_close_{ticket_id}")])
            keyboard.append([InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_reject_{ticket_id}")])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_open")])
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # ===== ВЗЯТЬ ОБРАЩЕНИЕ (АДМИН) =====
    if data.startswith("admin_take_") and user_id in ADMIN_IDS:
        ticket_id = int(data.replace("admin_take_", ""))
        
        if ticket_id in tickets_db and tickets_db[ticket_id]['status'] == 'open':
            tickets_db[ticket_id]['status'] = 'in_progress'
            tickets_db[ticket_id]['admin_id'] = user_id
            tickets_db[ticket_id]['admin_name'] = f"@{update.effective_user.username}"
            
            # Уведомление пользователю
            try:
                await context.bot.send_message(
                    tickets_db[ticket_id]['user_id'],
                    f"🟡 **Обращение #{tickets_db[ticket_id]['number']}**\n"
                    f"Администратор **@{update.effective_user.username}** взял ваше обращение в работу."
                )
            except:
                pass
            
            await query.answer("✅ Обращение взято в работу!")
        
        # Возвращаемся к списку
        await button_handler(update, context)
        return
    
    # ===== ОТВЕТИТЬ НА ОБРАЩЕНИЕ (АДМИН) =====
    if data.startswith("admin_reply_") and user_id in ADMIN_IDS:
        ticket_id = int(data.replace("admin_reply_", ""))
        context.user_data['reply_ticket_id'] = ticket_id
        context.user_data['waiting_for'] = 'admin_reply'
        
        await query.edit_message_text(
            f"📝 **Напиши ответ** на обращение #{tickets_db[ticket_id]['number']}:\n\n"
            "_Ответ будет отправлен пользователю_",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data=f"admin_view_{ticket_id}")
            ]])
        )
        return
    
    # ===== ЗАКРЫТЬ ОБРАЩЕНИЕ (АДМИН) =====
    if data.startswith("admin_close_") and user_id in ADMIN_IDS:
        ticket_id = int(data.replace("admin_close_", ""))
        
        if ticket_id in tickets_db:
            tickets_db[ticket_id]['status'] = 'closed'
            
            # Уведомление пользователю
            try:
                await context.bot.send_message(
                    tickets_db[ticket_id]['user_id'],
                    f"🔵 **Обращение #{tickets_db[ticket_id]['number']} закрыто**\n"
                    f"Спасибо за обращение! Если остались вопросы, создай новое."
                )
            except:
                pass
            
            await query.answer("✅ Обращение закрыто!")
        
        await button_handler(update, context)
        return
    
    # ===== ОТКЛОНИТЬ ОБРАЩЕНИЕ (АДМИН) =====
    if data.startswith("admin_reject_") and user_id in ADMIN_IDS:
        ticket_id = int(data.replace("admin_reject_", ""))
        
        if ticket_id in tickets_db:
            tickets_db[ticket_id]['status'] = 'rejected'
            
            # Уведомление пользователю
            try:
                await context.bot.send_message(
                    tickets_db[ticket_id]['user_id'],
                    f"🔴 **Обращение #{tickets_db[ticket_id]['number']} отклонено**\n"
                    f"Причина: не соответствует правилам.\n"
                    f"Подробнее в правилах сервера."
                )
            except:
                pass
            
            await query.answer("✅ Обращение отклонено!")
        
        await button_handler(update, context)
        return

# ============================================
# ОБРАБОТЧИК ТЕКСТА
# ============================================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения"""
    global ticket_counter
    user_id = update.effective_user.id
    
    # Проверка на спам
    if check_spam(user_id):
        await update.message.reply_text("⏳ Не так быстро! Подожди немного.")
        return
    
    # ===== АДМИН ОТВЕЧАЕТ НА ОБРАЩЕНИЕ =====
    if context.user_data.get('waiting_for') == 'admin_reply' and user_id in ADMIN_IDS:
        ticket_id = context.user_data.get('reply_ticket_id')
        reply_text = update.message.text
        
        if ticket_id and ticket_id in tickets_db:
            tickets_db[ticket_id]['admin_reply'] = reply_text
            tickets_db[ticket_id]['status'] = 'closed'
            
            # Отправляем ответ пользователю
            try:
                await context.bot.send_message(
                    tickets_db[ticket_id]['user_id'],
                    f"💬 **Ответ на обращение #{tickets_db[ticket_id]['number']}**\n\n"
                    f"{reply_text}\n\n"
                    f"👤 _Администратор @{update.effective_user.username}_"
                )
            except:
                pass
            
            context.user_data.clear()
            await update.message.reply_text(
                f"✅ **Ответ отправлен!**\nОбращение #{tickets_db[ticket_id]['number']} закрыто.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ В админ-панель", callback_data="admin_panel")
                ]])
            )
            return
    
    # ===== ПОЛЬЗОВАТЕЛЬ ОПИСЫВАЕТ ПРОБЛЕМУ =====
    if context.user_data.get('waiting_for') == 'description':
        context.user_data['ticket_description'] = update.message.text
        context.user_data['waiting_for'] = 'proof'
        
        await update.message.reply_text(
            "📎 **Пришли ссылки на доказательства**\n"
            "(скриншоты, видео) или напиши 'нет' если доказательств нет:"
        )
        return
    
    # ===== ПОЛЬЗОВАТЕЛЬ ПРИСЫЛАЕТ ДОКАЗАТЕЛЬСТВА =====
    if context.user_data.get('waiting_for') == 'proof':
        ticket_counter += 1
        date_str = datetime.datetime.now().strftime('%Y%m%d')
        ticket_number = f"LS-{date_str}-{ticket_counter:04d}"
        
        tickets_db[ticket_counter] = {
            'id': ticket_counter,
            'number': ticket_number,
            'user_id': user_id,
            'category': context.user_data.get('ticket_category', 'Другое'),
            'description': context.user_data.get('ticket_description', ''),
            'proof': update.message.text if update.message.text.lower() != 'нет' else '',
            'status': 'open',
            'created_at': datetime.datetime.now().strftime('%d.%m.%Y %H:%M'),
            'admin_reply': None,
            'admin_id': None,
            'admin_name': None
        }
        
        # Уведомление всем админам
        for admin_id in ADMIN_IDS:
            try:
                keyboard = [[InlineKeyboardButton(
                    "📋 Посмотреть", 
                    callback_data=f"admin_view_{ticket_counter}"
                )]]
                
                await context.bot.send_message(
                    admin_id,
                    f"🆕 **НОВОЕ ОБРАЩЕНИЕ!**\n\n"
                    f"📋 **#{ticket_number}**\n"
                    f"👤 От: @{update.effective_user.username}\n"
                    f"📌 Категория: {tickets_db[ticket_counter]['category']}\n"
                    f"📝 Описание: {tickets_db[ticket_counter]['description'][:100]}...",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления админа {admin_id}: {e}")
        
        context.user_data.clear()
        
        await update.message.reply_text(
            f"✅ **Обращение создано!**\n\n"
            f"📋 Номер: **#{ticket_number}**\n"
            f"📌 Категория: {tickets_db[ticket_counter]['category']}\n\n"
            f"Администратор ответит в ближайшее время.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_main")
            ]])
        )
        return

# ============================================
# ЗАПУСК
# ============================================
def main():
    """Запуск бота"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    # Запуск
    print("=" * 50)
    print("🚀 Бот поддержки LAST STAND v2.0")
    print(f"📊 Администраторы: {ADMIN_IDS}")
    print("✅ Защита от спама включена")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
