import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

# ============================================
# НАСТРОЙКА
# ============================================
BOT_TOKEN = "8742043015:AAF4EBWameQbc_qTZGlU347-A-R7shrK5GI"
CHAT_ID = -1003847436974
GAME_BOT_USERNAME = "qalais_bot"

# ============================================
# САМ БОТ
# ============================================
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()
last_processed_id = None
is_working = False

@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ Бот готов!\n"
        "1. Напишите 'Гавань' в чат\n"
        "2. Я нажму кнопки\n\n"
        "Команды: /status, /check"
    )

@dp.message(Command('status'))
async def cmd_status(message: types.Message):
    await message.answer(f"Последний ID: {last_processed_id}")

@dp.message(Command('check'))
async def cmd_check(message: types.Message):
    await message.answer("🔍 Проверяю...")
    asyncio.create_task(check_buttons())

async def check_buttons():
    global is_working, last_processed_id
    
    if is_working:
        return
    
    try:
        is_working = True
        logging.info("🔍 Начинаю проверку")
        
        # Получаем последние 10 сообщений
        messages = []
        async for msg in bot.get_chat_history(CHAT_ID):
            messages.append(msg)
            if len(messages) >= 10:
                break
        
        # Ищем новое сообщение от игрового бота
        game_msg = None
        for msg in messages:
            if (msg.from_user and 
                msg.from_user.username == GAME_BOT_USERNAME and
                msg.message_id != last_processed_id and
                msg.reply_markup):
                game_msg = msg
                last_processed_id = msg.message_id
                logging.info(f"✅ Нашел сообщение ID {msg.message_id}")
                break
        
        if not game_msg:
            logging.info("Новых сообщений нет")
            return
        
        # Нажимаем Склад
        for row in game_msg.reply_markup.inline_keyboard:
            for btn in row:
                if "склад" in btn.text.lower():
                    await game_msg.click(btn.callback_data)
                    logging.info(f"✅ Нажал: {btn.text}")
                    break
            else:
                continue
            break
        
        await asyncio.sleep(3)
        
        # Получаем новые сообщения
        messages = []
        async for msg in bot.get_chat_history(CHAT_ID):
            messages.append(msg)
            if len(messages) >= 5:
                break
        
        # Ищем кнопку продажи
        for msg in messages:
            if msg.from_user and msg.from_user.username == GAME_BOT_USERNAME and msg.reply_markup:
                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        if "продать" in btn.text.lower():
                            await msg.click(btn.callback_data)
                            logging.info(f"✅ Нажал: {btn.text}")
                            break
                    else:
                        continue
                    break
                break
        
        await asyncio.sleep(3)
        
        # Получаем новые сообщения
        messages = []
        async for msg in bot.get_chat_history(CHAT_ID):
            messages.append(msg)
            if len(messages) >= 5:
                break
        
        # Ищем кнопку назад
        for msg in messages:
            if msg.from_user and msg.from_user.username == GAME_BOT_USERNAME and msg.reply_markup:
                for row in msg.reply_markup.inline_keyboard:
                    for btn in row:
                        if "назад" in btn.text.lower() or "⬅️" in btn.text:
                            await msg.click(btn.callback_data)
                            logging.info(f"✅ Нажал: {btn.text}")
                            break
                    else:
                        continue
                    break
                break
        
        logging.info("🎉 Готово!")
        
    except Exception as e:
        logging.error(f"Ошибка: {e}")
    finally:
        is_working = False

async def main():
    scheduler.add_job(check_buttons, 'interval', minutes=2)
    scheduler.start()
    logging.info("✅ Бот запущен")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
