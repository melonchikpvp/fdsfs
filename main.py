import logging
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ConversationHandler
)

from config import BOT_TOKEN, DATABASE_URL, ADMIN_IDS
from database import init_db
from handlers import (
    start, button_callback, admin_panel, admin_list_open,
    receive_description, receive_proof, cancel, error_handler,
    CATEGORY, DESCRIPTION, PROOF
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    # Инициализация базы данных
    Session = init_db(DATABASE_URL)
    
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Сохраняем сессию базы данных в bot_data для доступа из всех обработчиков
    application.bot_data['session'] = Session
    
    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    
    # Обработчик нажатий на кнопки (основной)
    application.add_handler(CallbackQueryHandler(button_callback, pattern="^(?!admin_)"))
    
    # Обработчик для админских кнопок
    application.add_handler(CallbackQueryHandler(admin_list_open, pattern="^admin_list_open$"))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    
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