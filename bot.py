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

BOT_TOKEN = "8742043015:AAF4EBWameQbc_qTZGlU347-A-R7shrK5GI"  # Ваш токен
CHAT_ID = -1003847436974  # ID чата
GAME_BOT_USERNAME = "qalais_bot"  # Username игрового бота (БЕЗ @)

# ============================================
# САМ БОТ
# ============================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Храним ID последнего обработанного сообщения, чтобы не нажимать дважды
last_processed_message_id = None
is_checking = False

@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    await message.answer(
        "✅ Бот запущен в режиме ожидания!\n\n"
        "🔹 **Как это работает:**\n"
        "1. Вы пишете в чат 'Гавань' (вручную)\n"
        "2. Я автоматически нажму все нужные кнопки\n\n"
        "🔹 **Последовательность:**\n"
        "   • 🏝️ Склад\n"
        "   • 🛒 Продать ресурсы\n"
        "   • ⬅️ Назад\n"
        "   (пауза 3 секунды между нажатиями)\n\n"
        "🔹 **Команды:**\n"
        "/status - проверить статус\n"
        "/check_now - принудительно проверить кнопки"
    )

@dp.message(Command('status'))
async def cmd_status(message: types.Message):
    await message.answer(
        f"📊 Статус:\n"
        f"• Чат ID: {CHAT_ID}\n"
        f"• Игровой бот: @{GAME_BOT_USERNAME}\n"
        f"• Последний обработанный ID: {last_processed_message_id}\n"
        f"• Сейчас проверяю: {'да' if is_checking else 'нет'}"
    )

@dp.message(Command('check_now'))
async def cmd_check_now(message: types.Message):
    """Принудительная проверка новых кнопок"""
    global is_checking
    if is_checking:
        await message.answer("Уже идет проверка, подождите...")
        return
    
    await message.answer("🔍 Проверяю наличие новых кнопок...")
    asyncio.create_task(check_for_buttons())

async def check_for_buttons():
    """Проверяет, появились ли новые кнопки от игрового бота"""
    global is_checking, last_processed_message_id
    
    if is_checking:
        return
    
    try:
        is_checking = True
        logging.info(f"🔍 Проверяю новые сообщения в {datetime.now()}")
        
        # ===== ЖЕСТКАЯ ДИАГНОСТИКА =====
        logging.info("🔴🔴🔴 ЖЕСТКАЯ ДИАГНОСТИКА 🔴🔴🔴")
        logging.info(f"Проверяю чат {CHAT_ID}, ищу @{GAME_BOT_USERNAME}")
        
        # Получаем последние сообщения из чата (ПРАВИЛЬНЫЙ СПОСОБ)
        all_msgs = []
        async for msg in bot.iter_chat_messages(chat_id=CHAT_ID, max_id=999999999):
            all_msgs.append(msg)
            if len(all_msgs) >= 20:
                break
        
        logging.info(f"Всего получил {len(all_msgs)} сообщений")
        
        for i, msg in enumerate(all_msgs):
            if msg.from_user:
                uname = msg.from_user.username or "НЕТ USERNAME"
                name = msg.from_user.first_name or ""
                text = msg.text or "[не текст]"
                has_buttons = "ДА" if (msg.reply_markup and msg.reply_markup.inline_keyboard) else "НЕТ"
                
                logging.info(f"[{i}] От @{uname} ({name}): {text[:50]}")
                logging.info(f"    Есть кнопки: {has_buttons}")
                
                if msg.reply_markup and msg.reply_markup.inline_keyboard:
                    for ri, row in enumerate(msg.reply_markup.inline_keyboard):
                        for ci, btn in enumerate(row):
                            logging.info(f"    Кнопка [{ri},{ci}]: '{btn.text}'")
            await asyncio.sleep(0.1)
        
        logging.info("🔴🔴🔴 ДИАГНОСТИКА ЗАВЕРШЕНА 🔴🔴🔴")
        # ===== КОНЕЦ ДИАГНОСТИКИ =====
        
        # Ищем новое сообщение от игрового бота с кнопками
        game_message = None
        for msg in all_msgs:
            # Проверяем, что это сообщение от игрового бота и оно еще не обработано
            if (msg.from_user and 
                msg.from_user.username == GAME_BOT_USERNAME and 
                msg.message_id != last_processed_message_id and
                msg.reply_markup and 
                msg.reply_markup.inline_keyboard):
                game_message = msg
                logging.info(f"✅ Нашел НОВОЕ сообщение от игрового бота (ID: {msg.message_id})")
                break
        
        if not game_message:
            logging.info("Новых сообщений с кнопками нет")
            return
        
        # Запоминаем ID обработанного сообщения
        last_processed_message_id = game_message.message_id
        
        # Показываем все найденные кнопки
        logging.info("🔘 Доступные кнопки в первом сообщении:")
        for i, row in enumerate(game_message.reply_markup.inline_keyboard):
            for j, button in enumerate(row):
                logging.info(f"   Кнопка [{i},{j}]: '{button.text}'")
        
        # ===== 1. НАЖИМАЕМ КНОПКУ "СКЛАД" =====
        found_sklad = False
        for row in game_message.reply_markup.inline_keyboard:
            for button in row:
                if "склад" in button.text.lower():
                    await game_message.click(button.callback_data)
                    logging.info(f"✅ [1/3] Нажал кнопку: {button.text}")
                    found_sklad = True
                    break
            if found_sklad:
                break
        
        if not found_sklad:
            logging.warning("❌ Не нашел кнопку 'Склад'")
            return
        
        # Пауза 3 секунды
        logging.info("⏱ Жду 3 секунды...")
        await asyncio.sleep(3)
        
        # Получаем свежие сообщения после нажатия (ПРАВИЛЬНЫЙ СПОСОБ)
        msgs_after = []
        async for msg in bot.iter_chat_messages(chat_id=CHAT_ID, max_id=999999999):
            msgs_after.append(msg)
            if len(msgs_after) >= 10:
                break
        
        # Ищем новое сообщение от игрового бота с кнопкой продажи
        game_message = None
        for msg in msgs_after:
            if (msg.from_user and 
                msg.from_user.username == GAME_BOT_USERNAME and 
                msg.reply_markup and 
                msg.reply_markup.inline_keyboard):
                game_message = msg
                logging.info(f"✅ Нашел следующее сообщение от игрового бота")
                break
        
        if not game_message:
            logging.warning("❌ Не нашел сообщение с кнопкой продажи")
            return
        
        # Показываем кнопки в новом сообщении
        logging.info("🔘 Кнопки во втором сообщении:")
        for i, row in enumerate(game_message.reply_markup.inline_keyboard):
            for j, button in enumerate(row):
                logging.info(f"   Кнопка [{i},{j}]: '{button.text}'")
        
        # ===== 2. НАЖИМАЕМ КНОПКУ "ПРОДАТЬ РЕСУРСЫ" =====
        found_sell = False
        for row in game_message.reply_markup.inline_keyboard:
            for button in row:
                if "продать" in button.text.lower() or "ресурс" in button.text.lower():
                    await game_message.click(button.callback_data)
                    logging.info(f"✅ [2/3] Нажал кнопку: {button.text}")
                    found_sell = True
                    break
            if found_sell:
                break
        
        if not found_sell:
            logging.warning("❌ Не нашел кнопку продажи")
            return
        
        # Пауза 3 секунды
        logging.info("⏱ Жду 3 секунды...")
        await asyncio.sleep(3)
        
        # Получаем свежие сообщения после продажи (ПРАВИЛЬНЫЙ СПОСОБ)
        msgs_final = []
        async for msg in bot.iter_chat_messages(chat_id=CHAT_ID, max_id=999999999):
            msgs_final.append(msg)
            if len(msgs_final) >= 10:
                break
        
        # Ищем сообщение с кнопкой "Назад"
        game_message = None
        for msg in msgs_final:
            if (msg.from_user and 
                msg.from_user.username == GAME_BOT_USERNAME and 
                msg.reply_markup and 
                msg.reply_markup.inline_keyboard):
                game_message = msg
                logging.info(f"✅ Нашел сообщение с кнопкой назад")
                break
        
        if not game_message:
            logging.warning("❌ Не нашел сообщение с кнопкой назад")
            return
        
        # Показываем кнопки
        logging.info("🔘 Кнопки в финальном сообщении:")
        for i, row in enumerate(game_message.reply_markup.inline_keyboard):
            for j, button in enumerate(row):
                logging.info(f"   Кнопка [{i},{j}]: '{button.text}'")
        
        # ===== 3. НАЖИМАЕМ КНОПКУ "НАЗАД" =====
        found_back = False
        for row in game_message.reply_markup.inline_keyboard:
            for button in row:
                if "назад" in button.text.lower() or "⬅️" in button.text:
                    await game_message.click(button.callback_data)
                    logging.info(f"✅ [3/3] Нажал кнопку: {button.text}")
                    found_back = True
                    break
            if found_back:
                break
        
        if not found_back:
            logging.warning("❌ Не нашел кнопку 'Назад'")
            return
        
        logging.info("🎉 ВСЕ ТРИ КНОПКИ УСПЕШНО НАЖАТЫ!")
        
    except Exception as e:
        logging.error(f"❌ Ошибка: {e}")
    finally:
        is_checking = False

async def scheduled_check():
    """Запуск проверки по расписанию (каждые 2 минуты)"""
    await check_for_buttons()

async def main():
    # Проверяем новые кнопки каждые 2 минуты
    scheduler.add_job(
        scheduled_check, 
        'interval', 
        minutes=2,
        id='button_checker',
        next_run_time=datetime.now()
    )
    scheduler.start()
    logging.info("✅ Режим ожидания запущен: проверяю новые кнопки каждые 2 минуты")
    logging.info("👉 Напишите 'Гавань' в чат вручную, а я нажму кнопки!")
    logging.info("👉 Последовательность: Склад → Продать → Назад (с паузой 3 сек)")
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
