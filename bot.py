import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

# ============================================
# НАСТРОЙКА (ТОЛЬКО ЭТО МЕНЯЕМ!)
# ============================================

BOT_TOKEN = "8742043015:AAF4EBWameQbc_qTZGlU347-A-R7shrK5GI"  # Ваш токен
CHAT_ID = -1003847436974  # ID чата
GAME_BOT_USERNAME = "qalais_bot"  # Username игрового бота (БЕЗ @)

# ============================================
# САМ БОТ (НИЧЕГО НЕ МЕНЯТЬ!)
# ============================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Храним ID последнего обработанного сообщения
last_processed_id = None
is_checking = False

@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ Бот готов к работе!\n\n"
        "🔹 **Как использовать:**\n"
        "1. Напишите 'Гавань' в чат (вручную)\n"
        "2. Игровой бот пришлет кнопки\n"
        "3. Я автоматически нажму:\n"
        "   • 🏝️ Склад\n"
        "   • 🛒 Продать ресурсы\n"
        "   • ⬅️ Назад\n\n"
        "🔹 **Команды:**\n"
        "/check - проверить кнопки сейчас\n"
        "/status - статус бота"
    )

@dp.message(Command('status'))
async def cmd_status(message: types.Message):
    await message.answer(
        f"📊 Статус:\n"
        f"• Чат ID: {CHAT_ID}\n"
        f"• Игровой бот: @{GAME_BOT_USERNAME}\n"
        f"• Последний обработанный ID: {last_processed_id}\n"
        f"• Режим: {'проверка' if is_checking else 'ожидание'}"
    )

@dp.message(Command('check'))
async def cmd_check(message: types.Message):
    """Ручная проверка новых кнопок"""
    global is_checking
    if is_checking:
        await message.answer("Уже идет проверка, подождите...")
        return
    
    await message.answer("🔍 Проверяю наличие новых кнопок...")
    asyncio.create_task(check_for_buttons())

async def get_recent_messages(limit=10):
    """Получает последние сообщения из чата (РАБОЧИЙ МЕТОД)"""
    messages = []
    try:
        # В aiogram 3.x используем bot.get_chat_history напрямую
        async for msg in bot.get_chat_history(chat_id=CHAT_ID, limit=limit):
            messages.append(msg)
    except Exception as e:
        logging.error(f"Ошибка при получении истории: {e}")
    return messages

async def check_for_buttons():
    """Проверяет новые кнопки и нажимает их"""
    global is_checking, last_processed_id
    
    if is_checking:
        return
    
    try:
        is_checking = True
        logging.info(f"🔍 Начинаю проверку в {datetime.now()}")
        
        # Получаем последние сообщения
        messages = await get_recent_messages(15)
        logging.info(f"Получено {len(messages)} сообщений")
        
        # Ищем новое сообщение от игрового бота с кнопками
        game_message = None
        for msg in messages:
            if (msg.from_user and 
                msg.from_user.username == GAME_BOT_USERNAME and
                msg.message_id != last_processed_id and
                msg.reply_markup and 
                msg.reply_markup.inline_keyboard):
                game_message = msg
                last_processed_id = msg.message_id
                logging.info(f"✅ Нашел новое сообщение ID {msg.message_id}")
                
                # Показываем все кнопки
                for i, row in enumerate(msg.reply_markup.inline_keyboard):
                    for j, btn in enumerate(row):
                        logging.info(f"   Кнопка [{i},{j}]: '{btn.text}'")
                break
        
        if not game_message:
            logging.info("Новых сообщений с кнопками нет")
            return
        
        # ===== 1. НАЖИМАЕМ СКЛАД =====
        clicked = False
        for row in game_message.reply_markup.inline_keyboard:
            for btn in row:
                if "склад" in btn.text.lower():
                    await game_message.click(btn.callback_data)
                    logging.info(f"✅ [1/3] Нажал: {btn.text}")
                    clicked = True
                    break
            if clicked:
                break
        
        if not clicked:
            logging.warning("❌ Не нашел кнопку 'Склад'")
            return
        
        # Пауза 3 секунды
        await asyncio.sleep(3)
        
        # ===== 2. НАЖИМАЕМ ПРОДАТЬ =====
        # Получаем новые сообщения
        messages = await get_recent_messages(10)
        
        for msg in messages:
            if (msg.from_user and 
                msg.from_user.username == GAME_BOT_USERNAME and
                msg.reply_markup and 
                msg.reply_markup.inline_keyboard):
                
                clicked = False
                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        if "продать" in btn.text.lower() or "ресурс" in btn.text.lower():
                            await msg.click(btn.callback_data)
                            logging.info(f"✅ [2/3] Нажал: {btn.text}")
                            clicked = True
                            break
                    if clicked:
                        break
                if clicked:
                    break
        
        # Пауза 3 секунды
        await asyncio.sleep(3)
        
        # ===== 3. НАЖИМАЕМ НАЗАД =====
        messages = await get_recent_messages(10)
        
        for msg in messages:
            if (msg.from_user and 
                msg.from_user.username == GAME_BOT_USERNAME and
                msg.reply_markup and 
                msg.reply_markup.inline_keyboard):
                
                clicked = False
                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        if "назад" in btn.text.lower() or "⬅️" in btn.text:
                            await msg.click(btn.callback_data)
                            logging.info(f"✅ [3/3] Нажал: {btn.text}")
                            clicked = True
                            break
                    if clicked:
                        break
                if clicked:
                    break
        
        logging.info("🎉 Все кнопки нажаты!")
        
    except Exception as e:
        logging.error(f"❌ Ошибка: {e}")
    finally:
        is_checking = False

async def scheduled_check():
    """Запуск по расписанию"""
    await check_for_buttons()

async def main():
    # Проверка каждые 2 минуты
    scheduler.add_job(scheduled_check, 'interval', minutes=2)
    scheduler.start()
    
    logging.info("✅ Бот успешно запущен!")
    logging.info("👉 Напишите 'Гавань' в чат вручную")
    logging.info("👉 Используйте /check для ручной проверки")
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
