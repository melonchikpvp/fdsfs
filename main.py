import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import datetime

# ============================================
# ДАННЫЕ
# ============================================
BOT_TOKEN = "8548246370:AAEYqEVTSdslgQNQPAqo6xh_PEcbnRajt6M"
ADMIN_IDS = [6979197416]

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
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================
# ГЛАВНОЕ МЕНЮ
# ============================================
async def main_menu(update, context, user_id, text="👋 Главное меню. Выбери действие:", edit=True):
    keyboard = [
        [InlineKeyboardButton("📝 Создать обращение", callback_data="new_ticket")],
        [InlineKeyboardButton("📋 Мои обращения", callback_data="my_tickets")],
        [InlineKeyboardButton("ℹ️ О боте", callback_data="about")]
    ]
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel")])
    
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ============================================
# START
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    users_db[user.id] = {
        'id': user.id, 'username': user.username, 'first_name': user.first_name,
        'last_name': user.last_name, 'registered_at': datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
    }
    await main_menu(update, context, user.id, edit=False)

# ============================================
# ОБРАБОТЧИК КНОПОК
# ============================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    # Назад в главное меню
    if data == "back_to_main":
        await main_menu(update, context, user_id)
        return

    # О боте
    if data == "about":
        await query.edit_message_text(
            "ℹ️ **О боте**\n\nБот поддержки LAST STAND\nВерсия: 1.0.0\nРазработка: @melonchikpvp",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]])
        )
        return

    # Создание обращения - выбор категории
    if data == "new_ticket":
        keyboard = []
        for key, value in CATEGORIES.items():
            keyboard.append([InlineKeyboardButton(value, callback_data=f"cat_{key}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
        await query.edit_message_text("📋 Выбери категорию:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Выбрана категория
    if data.startswith("cat_"):
        cat_key = data.replace("cat_", "")
        context.user_data['ticket_category'] = CATEGORIES[cat_key]
        context.user_data['waiting_for'] = 'description'
        await query.edit_message_text(
            f"📝 Категория: **{CATEGORIES[cat_key]}**\n\nОпиши ситуацию (ник, время, что случилось):",
            parse_mode='Markdown'
        )
        return

    # Мои обращения
    if data == "my_tickets":
        user_tickets = [t for t in tickets_db.values() if t['user_id'] == user_id]
        if not user_tickets:
            await query.edit_message_text(
                "📭 Нет обращений.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]])
            )
            return
        
        text = "📋 **Твои обращения:**\n\n"
        keyboard = []
        for ticket in user_tickets[-5:]:
            status = {'open': '🟢', 'in_progress': '🟡', 'closed': '🔵', 'rejected': '🔴'}.get(ticket['status'], '⚪')
            text += f"{status} #{ticket['number']} - {ticket['category']}\n"
            keyboard.append([InlineKeyboardButton(f"#{ticket['number']}", callback_data=f"view_{ticket['id']}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Просмотр обращения
    if data.startswith("view_"):
        ticket_id = int(data.replace("view_", ""))
        ticket = tickets_db.get(ticket_id)
        if not ticket:
            await query.edit_message_text("❌ Не найдено", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]]))
            return
        
        status_text = {'open': '🟢 Открыто', 'in_progress': '🟡 В работе', 'closed': '🔵 Закрыто', 'rejected': '🔴 Отклонено'}.get(ticket['status'], '⚪')
        text = (f"📋 **#{ticket['number']}**\n📌 {ticket['category']}\n📊 {status_text}\n📅 {ticket['created_at']}\n\n📝 {ticket['description']}")
        if ticket.get('proof'):
            text += f"\n\n📎 {ticket['proof']}"
        if ticket.get('admin_reply'):
            text += f"\n\n💬 **Ответ:** {ticket['admin_reply']}"
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="my_tickets")]]))
        return

    # Админ-панель
    if data == "admin_panel" and user_id in ADMIN_IDS:
        total = len(tickets_db)
        open_tickets = len([t for t in tickets_db.values() if t['status'] == 'open'])
        progress = len([t for t in tickets_db.values() if t['status'] == 'in_progress'])
        text = f"👑 **Админ-панель**\n\n📊 Всего: {total}\n🟢 Открыто: {open_tickets}\n🟡 В работе: {progress}"
        keyboard = [
            [InlineKeyboardButton("📋 Открытые", callback_data="admin_open")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]
        ]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Список открытых (админ)
    if data == "admin_open" and user_id in ADMIN_IDS:
        open_tickets = [t for t in tickets_db.values() if t['status'] in ['open', 'in_progress']]
        if not open_tickets:
            await query.edit_message_text("📭 Нет открытых", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]))
            return
        
        text = "📋 **Открытые:**\n\n"
        keyboard = []
        for ticket in open_tickets[:10]:
            status = '🟡' if ticket['status'] == 'in_progress' else '🟢'
            user = users_db.get(ticket['user_id'], {})
            text += f"{status} #{ticket['number']} - @{user.get('username', '?')}\n"
            keyboard.append([InlineKeyboardButton(f"#{ticket['number']}", callback_data=f"admin_view_{ticket['id']}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")])
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Просмотр обращения (админ)
    if data.startswith("admin_view_") and user_id in ADMIN_IDS:
        ticket_id = int(data.replace("admin_view_", ""))
        ticket = tickets_db.get(ticket_id)
        if not ticket:
            await query.edit_message_text("❌ Не найдено", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_open")]]))
            return
        
        user = users_db.get(ticket['user_id'], {})
        status_text = {'open': '🟢 Открыто', 'in_progress': '🟡 В работе', 'closed': '🔵 Закрыто', 'rejected': '🔴 Отклонено'}.get(ticket['status'], '⚪')
        text = (f"📋 **#{ticket['number']}**\n👤 @{user.get('username', '?')}\n📌 {ticket['category']}\n📊 {status_text}\n📅 {ticket['created_at']}\n\n📝 {ticket['description']}")
        if ticket.get('proof'):
            text += f"\n\n📎 {ticket['proof']}"
        
        keyboard = []
        if ticket['status'] == 'open':
            keyboard.append([InlineKeyboardButton("✅ Взять", callback_data=f"admin_take_{ticket_id}")])
        if ticket['status'] != 'closed':
            keyboard.append([InlineKeyboardButton("🔒 Закрыть", callback_data=f"admin_close_{ticket_id}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_open")])
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Взять обращение
    if data.startswith("admin_take_") and user_id in ADMIN_IDS:
        ticket_id = int(data.replace("admin_take_", ""))
        if ticket_id in tickets_db:
            tickets_db[ticket_id]['status'] = 'in_progress'
            await query.answer("✅ Взято!")
        await button_handler(update, context)
        return

    # Закрыть обращение
    if data.startswith("admin_close_") and user_id in ADMIN_IDS:
        ticket_id = int(data.replace("admin_close_", ""))
        if ticket_id in tickets_db:
            tickets_db[ticket_id]['status'] = 'closed'
            uid = tickets_db[ticket_id]['user_id']
            try:
                await context.bot.send_message(uid, f"🔵 Обращение #{tickets_db[ticket_id]['number']} закрыто.")
            except:
                pass
            await query.answer("✅ Закрыто!")
        await button_handler(update, context)
        return

# ============================================
# ОБРАБОТЧИК ТЕКСТА
# ============================================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ticket_counter
    user_id = update.effective_user.id

    # Ожидаем описание
    if context.user_data.get('waiting_for') == 'description':
        context.user_data['ticket_description'] = update.message.text
        context.user_data['waiting_for'] = 'proof'
        await update.message.reply_text("📎 Пришли ссылки на доказательства (или 'нет'):")
        return

    # Ожидаем доказательства
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
            'admin_reply': None
        }

        # Уведомление админам
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"🆕 **Новое обращение #{ticket_number}**\n👤 @{update.effective_user.username}\n📌 {tickets_db[ticket_counter]['category']}",
                    parse_mode='Markdown'
                )
            except:
                pass

        context.user_data.clear()
        await update.message.reply_text(
            f"✅ Обращение #{ticket_number} создано!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В меню", callback_data="back_to_main")]])
        )
        return

# ============================================
# ЗАПУСК
# ============================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    print("🚀 Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
