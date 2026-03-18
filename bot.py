import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

# ============================================
# НАСТРОЙКА (ТОЛЬКО ЭТО МЕНЯЕМ!)
# ============================================

# Токен вашего бота (от @BotFather)
BOT_TOKEN = "8742043015:AAF4EBWameQbc_qTZGlU347-A-R7shrK5GI"

# ID чата, где сидят боты (с минусом в начале)
CHAT_ID = -1003847436974

# Username игрового бота (БЕЗ @)
GAME_BOT_USERNAME = "qalais_bot"

# ============================================
# САМ БОТ (НИЧЕГО НЕ МЕНЯТЬ!)
# ============================================

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Создаем объекты бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Флаг, чтобы не запускать несколько кликов одновременно
is_clicking = False

@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    """Команда /start - проверка что бот работает"""
    await message.answer(
        "✅ Бот запущен и работает!\n"
        "Каждые 30 минут я буду:\n"
        "1. Писать 'Гавань'\n"
        "2. Нажимать 'Склад'\n"
        "3. Нажимать 'Продать ресурсы'\n\n"
        "Команды:\n"
        "/status - проверить статус\n"
        "/click_now - запустить цикл сейчас"
    )

@dp.message(Command('status'))
async def cmd_status(message: types.Message):
    """Команда /status - проверка статуса"""
    await message.answer(
        f"📊 Статус:\n"
        f"• Чат ID: {CHAT_ID}\n"
        f"• Игровой бот: @{GAME_BOT_USERNAME}\n"
        f"• Сейчас кликаем: {'да' if is_clicking else 'нет'}\n"
        f"• Следующий клик по расписанию"
    )

@dp.message(Command('click_now'))
async def cmd_click_now(message: types.Message):
    """Команда /click_now - запустить цикл вручную"""
    global is_clicking
    if is_clicking:
        await message.answer("Уже выполняется клик, подождите...")
        return
    
    await message.answer("🔄 Запускаю цикл...")
    asyncio.create_task(click_cycle())

async def click_cycle():
    """Главная функция: отправка Гавань и нажатие кнопок"""
    global is_clicking
    
    # Если уже кликаем - выходим
    if is_clicking:
        return
    
    try:
        is_clicking = True
        logging.info(f"Начинаю цикл в {datetime.now()}")
        
        # ===== ШАГ 1: Отправляем "Гавань" =====
        await bot.send_message(chat_id=CHAT_ID, text="Гавань")
        logging.info("✅ Отправил 'Гавань'")
        
        # ===== ВРЕМЕННАЯ ДИАГНОСТИКА =====
        logging.info("🔍 ДИАГНОСТИКА: Смотрю, кто писал в чат последним...")
        async for msg in bot.get_chat_history(chat_id=CHAT_ID, limit=10):
            if msg.from_user:
                username = msg.from_user.username or "нет username"
                name = msg.from_user.first_name or ""
                logging.info(f"   📨 От @{username} ({name}): {msg.text[:50] if msg.text else 'не текст'}")
                if msg.reply_markup and msg.reply_markup.inline_keyboard:
                    logging.info(f"      🔘 Есть инлайн-кнопки!")
        logging.info("🔍 ДИАГНОСТИКА ЗАВЕРШЕНА")
        # ===== КОНЕЦ ДИАГНОСТИКИ =====
        
        # Ждем 3 секунды, чтобы игровой бот ответил
        await asyncio.sleep(3)
        
        # ===== ШАГ 2: Ищем ответ от игрового бота =====
        messages = []
        async for msg in bot.get_chat_history(chat_id=CHAT_ID, limit=5):
            messages.append(msg)
        
        # Ищем сообщение от игрового бота с кнопками
        game_message = None
        for msg in messages:
            if (msg.from_user and 
                msg.from_user.username == GAME_BOT_USERNAME and 
                msg.reply_markup and 
                msg.reply_markup.inline_keyboard):
                game_message = msg
                logging.info(f"✅ Нашел сообщение от игрового бота!")
                break
        
        if not game_message:
            logging.warning("❌ Не нашел сообщение от игрового бота с кнопками")
            return
        
        # Показываем все найденные кнопки
        logging.info("🔘 Доступные кнопки:")
        for i, row in enumerate(game_message.reply_markup.inline_keyboard):
            for j, button in enumerate(row):
                logging.info(f"   Кнопка [{i},{j}]: '{button.text}'")
        
        # ===== ШАГ 3: Ищем и нажимаем кнопку "Склад" =====
        found_sklad = False
        for row in game_message.reply_markup.inline_keyboard:
            for button in row:
                if "склад" in button.text.lower():
                    await game_message.click(button.callback_data)
                    logging.info(f"✅ Нажал кнопку: {button.text}")
                    found_sklad = True
                    break
            if found_sklad:
                break
        
        if not found_sklad:
            logging.warning("❌ Не нашел кнопку 'Склад'")
            return
        
        # Ждем, пока обновится сообщение
        await asyncio.sleep(2)
        
        # ===== ШАГ 4: Ищем новое сообщение с кнопкой продажи =====
        messages = []
        async for msg in bot.get_chat_history(chat_id=CHAT_ID, limit=5):
            messages.append(msg)
        
        # Ищем новое сообщение от игрового бота
        game_message = None
        for msg in messages:
            if (msg.from_user and 
                msg.from_user.username == GAME_BOT_USERNAME and 
                msg.reply_markup and 
                msg.reply_markup.inline_keyboard):
                game_message = msg
                logging.info(f"✅ Нашел новое сообщение от игрового бота!")
                break
        
        if not game_message:
            logging.warning("❌ Не нашел сообщение с кнопкой продажи")
            return
        
        # Показываем кнопки в новом сообщении
        logging.info("🔘 Кнопки в новом сообщении:")
        for i, row in enumerate(game_message.reply_markup.inline_keyboard):
            for j, button in enumerate(row):
                logging.info(f"   Кнопка [{i},{j}]: '{button.text}'")
        
        # ===== ШАГ 5: Ищем и нажимаем кнопку "Продать ресурсы" =====
        found_sell = False
        for row in game_message.reply_markup.inline_keyboard:
            for button in row:
                if "продать" in button.text.lower() or "ресурс" in button.text.lower():
                    await game_message.click(button.callback_data)
                    logging.info(f"✅ Нажал кнопку: {button.text}")
                    found_sell = True
                    break
            if found_sell:
                break
        
        if not found_sell:
            logging.warning("❌ Не нашел кнопку продажи")
            return
        
        logging.info("✅ ЦИКЛ УСПЕШНО ЗАВЕРШЕН!")
        
    except Exception as e:
        logging.error(f"❌ Ошибка: {e}")
    finally:
        is_clicking = False

async def scheduled_click():
    """Функция для запуска по расписанию"""
    await click_cycle()

async def main():
    """Запуск бота"""
    
    # Добавляем задачу в расписание - каждые 30 минут
    scheduler.add_job(
        scheduled_click, 
        'interval', 
        minutes=30, 
        id='game_clicker',
        next_run_time=datetime.now()
    )
    scheduler.start()
    logging.info("✅ Расписание запущено: каждые 30 минут")
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
