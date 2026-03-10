import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import datetime

# ============================================
# ДАННЫЕ (ЗАПОЛНИ СВОИ)
# ============================================
BOT_TOKEN = "8548246370:AAEYqEVTSdslgQNQPAqo6xh_PEcbnRajt6M"
ADMIN_IDS = [6979197416]  # Твой ID

# ============================================
# ХРАНИЛИЩЕ ДАННЫХ
# ============================================
users = {}        # {user_id: {'name':, 'username':}}
tickets = {}      # {ticket_id: {'number':, 'user_id':, 'category':, 'text':, 'status':, 'created':}}
ticket_counter = 0
user_state = {}   # {user_id: 'waiting_category' или 'waiting_text'}

# ============================================
# КАТЕГОРИИ
# ============================================
CATEGORIES = {
    '1': '👤 Жалоба на игрока',
    '2': '📦 Возврат ресурсов',
    '3': '❓ Вопрос по правилам',
    '4': '🛠 Связь с админом',
    '5': '🐞 Баг',
    '6': '💡 Идея'
}

# ============================================
# НАСТРОЙКА ЛОГОВ
# ============================================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================
# ФУНКЦИЯ ГЛАВНОГО МЕНЮ
# ============================================
async def show_main_menu(update, context, user_id, message=None, edit=False):
    """Показывает главное меню"""
    keyboard = [
        [InlineKeyboardButton("📝 Создать тикет", callback_data="new_ticket")],
        [InlineKeyboardButton("📋 Мои тикеты", callback_data="my_tickets")]
    ]
    
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
    
    text = message or "👋 **Главное меню**\nВыбери действие:"
    
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ============================================
# START
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users[user.id] = {
        'name': user.full_name,
        'username': f"@{user.username}" if user.username else "нет юзернейма"
    }
    await show_main_menu(update, context, user.id, edit=False)

# ============================================
# ОБРАБОТЧИК КНОПОК
# ============================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Важно! Убирает "часики" на кнопке
    user_id = update.effective_user.id
    data = query.data

    # === НАЗАД В МЕНЮ ===
    if data == "main_menu":
        await show_main_menu(update, context, user_id, edit=True)
        return

    # === СОЗДАТЬ ТИКЕТ - ВЫБОР КАТЕГОРИИ ===
    if data == "new_ticket":
        keyboard = []
        for key, cat in CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(cat, callback_data=f"cat_{key}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_menu")])
        
        await query.edit_message_text(
            "📋 **Выбери категорию тикета:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return

    # === КАТЕГОРИЯ ВЫБРАНА ===
    if data.startswith("cat_"):
        cat_key = data.replace("cat_", "")
        context.user_data['temp_category'] = CATEGORIES[cat_key]
        context.user_data['temp_state'] = 'waiting_text'
        
        await query.edit_message_text(
            f"📝 **Категория:** {CATEGORIES[cat_key]}\n\n"
            f"✍️ Опиши ситуацию подробно:\n"
            f"• Ник игрока (если есть)\n"
            f"• Время и место\n"
            f"• Что случилось",
            parse_mode='Markdown'
        )
        return

    # === МОИ ТИКЕТЫ ===
    if data == "my_tickets":
        user_tickets = [t for t in tickets.values() if t['user_id'] == user_id]
        
        if not user_tickets:
            await query.edit_message_text(
                "📭 **У тебя пока нет тикетов.**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]),
                parse_mode='Markdown'
            )
            return
        
        text = "📋 **Твои тикеты:**\n\n"
        keyboard = []
        for ticket in sorted(user_tickets, key=lambda x: x['id'], reverse=True)[:5]:
            status_emoji = {
                'open': '🟢',
                'in_progress': '🟡',
                'closed': '🔵',
                'rejected': '🔴'
            }.get(ticket['status'], '⚪')
            
            text += f"{status_emoji} `{ticket['number']}` - {ticket['category']}\n"
            keyboard.append([InlineKeyboardButton(f"Тикет {ticket['number']}", callback_data=f"view_{ticket['id']}")])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_menu")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    # === ПРОСМОТР ТИКЕТА ===
    if data.startswith("view_"):
        ticket_id = int(data.replace("view_", ""))
        ticket = tickets.get(ticket_id)
        
        if not ticket:
            await query.edit_message_text("❌ Тикет не найден", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="my_tickets")]]))
            return
        
        status_text = {
            'open': '🟢 Открыт',
            'in_progress': '🟡 В работе',
            'closed': '🔵 Закрыт',
            'rejected': '🔴 Отклонён'
        }.get(ticket['status'], '⚪')
        
        text = (
            f"📋 **Тикет {ticket['number']}**\n"
            f"📌 {ticket['category']}\n"
            f"📊 {status_text}\n"
            f"📅 {ticket['created']}\n\n"
            f"📝 **Описание:**\n{ticket['text']}"
        )
        
        if ticket.get('reply'):
            text += f"\n\n💬 **Ответ:**\n{ticket['reply']}"
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="my_tickets")]]),
            parse_mode='Markdown'
        )
        return

    # === АДМИН-ПАНЕЛЬ ===
    if data == "admin_panel" and user_id in ADMIN_IDS:
        total = len(tickets)
        open_count = len([t for t in tickets.values() if t['status'] == 'open'])
        progress_count = len([t for t in tickets.values() if t['status'] == 'in_progress'])
        
        text = (
            f"👑 **Админ-панель**\n\n"
            f"📊 **Статистика:**\n"
            f"• Всего тикетов: {total}\n"
            f"• 🟢 Открыто: {open_count}\n"
            f"• 🟡 В работе: {progress_count}"
        )
        
        keyboard = [
            [InlineKeyboardButton("📋 Открытые тикеты", callback_data="admin_open")],
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    # === ОТКРЫТЫЕ ТИКЕТЫ (АДМИН) ===
    if data == "admin_open" and user_id in ADMIN_IDS:
        open_tickets = [t for t in tickets.values() if t['status'] in ['open', 'in_progress']]
        
        if not open_tickets:
            await query.edit_message_text(
                "📭 **Нет открытых тикетов**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]),
                parse_mode='Markdown'
            )
            return
        
        text = "📋 **Открытые тикеты:**\n\n"
        keyboard = []
        for ticket in sorted(open_tickets, key=lambda x: x['id'], reverse=True):
            status_emoji = '🟡' if ticket['status'] == 'in_progress' else '🟢'
            user = users.get(ticket['user_id'], {})
            username = user.get('username', 'неизвестно')
            text += f"{status_emoji} `{ticket['number']}` - {username}\n"
            keyboard.append([InlineKeyboardButton(f"{ticket['number']}", callback_data=f"admin_view_{ticket['id']}")])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    # === ПРОСМОТР ТИКЕТА (АДМИН) ===
    if data.startswith("admin_view_") and user_id in ADMIN_IDS:
        ticket_id = int(data.replace("admin_view_", ""))
        ticket = tickets.get(ticket_id)
        
        if not ticket:
            await query.edit_message_text("❌ Тикет не найден", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_open")]]))
            return
        
        user = users.get(ticket['user_id'], {})
        status_text = {
            'open': '🟢 Открыт',
            'in_progress': '🟡 В работе',
            'closed': '🔵 Закрыт',
            'rejected': '🔴 Отклонён'
        }.get(ticket['status'], '⚪')
        
        text = (
            f"📋 **Тикет {ticket['number']}**\n"
            f"👤 {user.get('name', '?')} {user.get('username', '')}\n"
            f"📌 {ticket['category']}\n"
            f"📊 {status_text}\n"
            f"📅 {ticket['created']}\n\n"
            f"📝 **Описание:**\n{ticket['text']}"
        )
        
        keyboard = []
        if ticket['status'] == 'open':
            keyboard.append([InlineKeyboardButton("✅ Взять в работу", callback_data=f"admin_take_{ticket_id}")])
        if ticket['status'] != 'closed':
            keyboard.append([InlineKeyboardButton("🔒 Закрыть", callback_data=f"admin_close_{ticket_id}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_open")])
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return

    # === ВЗЯТЬ ТИКЕТ ===
    if data.startswith("admin_take_") and user_id in ADMIN_IDS:
        ticket_id = int(data.replace("admin_take_", ""))
        if ticket_id in tickets and tickets[ticket_id]['status'] == 'open':
            tickets[ticket_id]['status'] = 'in_progress'
            await query.answer("✅ Тикет взят в работу!")
            
            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    tickets[ticket_id]['user_id'],
                    f"🟡 Ваш тикет {tickets[ticket_id]['number']} взят в работу администратором."
                )
            except:
                pass
        
        # Обновляем просмотр
        await button_handler(update, context)
        return

    # === ЗАКРЫТЬ ТИКЕТ ===
    if data.startswith("admin_close_") and user_id in ADMIN_IDS:
        ticket_id = int(data.replace("admin_close_", ""))
        if ticket_id in tickets and tickets[ticket_id]['status'] != 'closed':
            tickets[ticket_id]['status'] = 'closed'
            await query.answer("✅ Тикет закрыт!")
            
            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    tickets[ticket_id]['user_id'],
                    f"🔵 Ваш тикет {tickets[ticket_id]['number']} закрыт.\nСпасибо за обращение!"
                )
            except:
                pass
        
        # Обновляем просмотр
        await button_handler(update, context)
        return

# ============================================
# ОБРАБОТЧИК ТЕКСТА (СОЗДАНИЕ ТИКЕТА)
# ============================================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ticket_counter
    user_id = update.effective_user.id
    
    # Проверяем, ждём ли мы текст для тикета
    if context.user_data.get('temp_state') == 'waiting_text':
        category = context.user_data.get('temp_category', 'Другое')
        text = update.message.text
        
        # Создаём тикет
        ticket_counter += 1
        date_str = datetime.datetime.now().strftime('%Y%m%d')
        ticket_number = f"LS-{date_str}-{ticket_counter:04d}"
        
        tickets[ticket_counter] = {
            'id': ticket_counter,
            'number': ticket_number,
            'user_id': user_id,
            'category': category,
            'text': text,
            'status': 'open',
            'created': datetime.datetime.now().strftime('%d.%m.%Y %H:%M'),
            'reply': None
        }
        
        # Уведомление админам
        for admin_id in ADMIN_IDS:
            try:
                keyboard = [[InlineKeyboardButton("📋 Посмотреть", callback_data=f"admin_view_{ticket_counter}")]]
                await context.bot.send_message(
                    admin_id,
                    f"🆕 **Новый тикет!**\n"
                    f"📋 {ticket_number}\n"
                    f"👤 {users.get(user_id, {}).get('name', '?')}\n"
                    f"📌 {category}",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            except:
                pass
        
        # Очищаем состояние
        context.user_data.clear()
        
        # Подтверждение пользователю
        await update.message.reply_text(
            f"✅ **Тикет создан!**\n\n"
            f"Номер: `{ticket_number}`\n"
            f"Категория: {category}\n\n"
            f"Администратор ответит в ближайшее время.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В меню", callback_data="main_menu")]])
        )
        return
    
    # Если не ждём текст - показываем меню
    await show_main_menu(update, context, user_id, edit=False)

# ============================================
# ЗАПУСК
# ============================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    print("✅ Бот поддержки LAST STAND запущен!")
    print(f"👑 Админ ID: {ADMIN_IDS[0]}")
    app.run_polling()

if __name__ == "__main__":
    main()
