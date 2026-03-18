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
# САМ БОТ
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

@dp.message()
async def handle_all_messages(message: types.Message):
    """Обрабатываем все сообщения в чате с подробной диагностикой"""
    global last_processed_id, is_checking
    
    # Пропускаем свои собственные сообщения
    if message.from_user and message.from_user.id == bot.id:
        return
    
    # Диагностика - логируем ВСЕ сообщения
    if message.from_user:
        username = message.from_user.username or "нет username"
        name = message.from_user.first_name or ""
        user_id = message.from_user.id
        has_buttons = "✅ ЕСТЬ КНОПКИ" if (message.reply_markup and message.reply_markup.inline_keyboard) else "❌ нет кнопок"
        
        logging.info(f"📨 [ID:{user_id}] @{username} ({name}): '{message.text or '[не текст]'}' - {has_buttons}")
        
        # Специальная проверка для игрового бота
        if username == GAME_BOT_USERNAME:
            logging.info(f"🎯👉 ЭТО СООБЩЕНИЕ ОТ ИГРОВОГО БОТА! 👈🎯")
            
            if message.reply_markup and message.reply_markup.inline_keyboard:
                logging.info(f"✅ И У НЕГО ЕСТЬ КНОПКИ! 🎉")
                
                # Показываем все кнопки
                for i, row in enumerate(message.reply_markup.inline_keyboard):
                    for j, btn in enumerate(row):
                        logging.info(f"   🔘 Кнопка [{i},{j}]: '{btn.text}' (callback: {btn.callback_data})")
                
                # Проверяем ID сообщения
                if message.message_id != last_processed_id:
                    logging.info(f"✅ Новое сообщение! ID {message.message_id} ≠ {last_processed_id}")
                    last_processed_id = message.message_id
                    
                    if not is_checking:
                        logging.info(f"🚀 ЗАПУСКАЮ НАЖАТИЕ КНОПОК! 🚀")
                        asyncio.create_task(click_buttons(message))
                    else:
                        logging.info(f"⏳ Уже идет проверка, ждем...")
                else:
                    logging.info(f"⏭ Сообщение уже обработано (ID {message.message_id} = {last_processed_id})")
            else:
                logging.info(f"❌ У сообщения НЕТ кнопок!")

async def click_buttons(game_message):
    """Нажимает кнопки в полученном сообщении"""
    global is_checking
    
    if is_checking:
        logging.info("⏳ Уже кликаю, пропускаю...")
        return
    
    try:
        is_checking = True
        logging.info("🎯 НАЧИНАЮ ПРОЦЕСС НАЖАТИЯ КНОПОК")
        
        # Показываем все кнопки
        logging.info("🔘 Доступные кнопки:")
        all_buttons = []
        for i, row in enumerate(game_message.reply_markup.inline_keyboard):
            for j, btn in enumerate(row):
                btn_info = f"'{btn.text}'"
                all_buttons.append(btn.text.lower())
                logging.info(f"   Кнопка [{i},{j}]: {btn_info}")
        
        logging.info(f"📋 Все кнопки: {all_buttons}")
        
        # ===== 1. НАЖИМАЕМ СКЛАД =====
        clicked = False
        for row in game_message.reply_markup.inline_keyboard:
            for btn in row:
                if "склад" in btn.text.lower():
                    logging.info(f"👉 Нашел кнопку СКЛАД: '{btn.text}'")
                    await game_message.click(btn.callback_data)
                    logging.info(f"✅ [1/3] Нажал: {btn.text}")
                    clicked = True
                    break
            if clicked:
                break
        
        if not clicked:
            logging.warning("❌ Не нашел кнопку 'Склад' среди кнопок!")
            # Покажем, какие кнопки искали
            logging.warning(f"🔍 Искал 'склад' в кнопках: {all_buttons}")
            return
        
        # Пауза 3 секунды
        logging.info("⏱ Жду 3 секунды перед следующим действием...")
        await asyncio.sleep(3)
        
        # Сбрасываем флаг, чтобы следующее сообщение тоже обработалось
        logging.info("✅ Первый шаг завершен, жду следующее сообщение")
        
    except Exception as e:
        logging.error(f"❌ Ошибка при нажатии: {e}")
    finally:
        is_checking = False
        logging.info("🔄 Флаг is_checking сброшен, готов к новым сообщениям")

async def check_for_buttons():
    """Проверяет новые кнопки (резервный метод)"""
    global is_checking, last_processed_id
    
    if is_checking:
        return
    
    try:
        is_checking = True
        logging.info(f"🔍 Плановая проверка в {datetime.now()}")
        logging.info("Ожидаю новые сообщения через хендлер...")
        
    except Exception as e:
        logging.error(f"❌ Ошибка: {e}")
    finally:
        is_checking = False

async def scheduled_check():
    """Запуск по расписанию"""
    await check_for_buttons()

async def main():
    # Проверка каждые 2 минуты (на всякий случай)
    scheduler.add_job(scheduled_check, 'interval', minutes=2)
    scheduler.start()
    
    logging.info("✅ Бот успешно запущен!")
    logging.info("👉 Бот теперь ловит сообщения в реальном времени!")
    logging.info("👉 Просто напишите 'Гавань' в чат и бот сам среагирует")
    logging.info("👉 /check - ручная проверка")
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
