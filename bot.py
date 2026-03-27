#!/usr/bin/env python3
"""
Универсальный Telegram юзербот
Управление: шахта, рыбалка, работа
Команды:
  шах /shaft    - запустить шахту
  сшах /sshaft  - остановить шахту
  рыб /fishing  - запустить рыбалку
  срыб /sfishing - остановить рыбалку
  раб /work     - запустить работу
  сраб /swork   - остановить работу
  стат /status  - показать статус
"""

import asyncio
import logging
import sys
import time
import random
import re
import os
from typing import Optional, Tuple
from datetime import datetime

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.types import Message

import config

# Создаем папку для сессии если её нет
SESSION_DIR = 'sessions'
if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class UniversalBot:
    """Универсальный бот для шахты, рыбалки и работы"""

    def __init__(self):
        # Создаем клиент с единой сессией
        self.client = TelegramClient(
            f'{SESSION_DIR}/universal_bot',
            config.API_ID,
            config.API_HASH,
            device_model="Python Universal Bot",
            system_version="3.0"
        )

        # Состояния активностей
        self.shaft_running = False
        self.fishing_running = False
        self.work_running = False

        # Задачи активностей
        self.shaft_task: Optional[asyncio.Task] = None
        self.fishing_task: Optional[asyncio.Task] = None
        self.work_task: Optional[asyncio.Task] = None

        # Статистика
        self.bot_start_time = None
        self.shaft_stats = {'cycles': 0, 'start_time': None, 'next_time': None, 'last_duration': 0}
        self.fishing_stats = {'cycles': 0, 'start_time': None, 'next_time': None, 'last_duration': 0}
        self.work_stats = {'cycles': 0, 'start_time': None, 'next_time': None, 'last_duration': 0}

        # Общие настройки
        self.chat_id = int(config.CHAT_ID) if str(config.CHAT_ID).lstrip('-').isdigit() else config.CHAT_ID

        # Настройки шахты
        self.shaft_interval = config.SHAFT_INTERVAL
        self.shaft_timeout = config.SHAFT_TIMEOUT
        self.diamond_emoji = "💎"
        self.stone_emoji = "🪨"

        # Настройки рыбалки
        self.fishing_interval_min = config.FISHING_INTERVAL_MIN
        self.fishing_interval_max = config.FISHING_INTERVAL_MAX
        self.fishing_timeout = config.FISHING_TIMEOUT
        self.fishing_delay_min = config.FISHING_DELAY_MIN
        self.fishing_delay_max = config.FISHING_DELAY_MAX
        self.fishing_emojis = [
            '🐟', '🐠', '🐡', '🦈', '🐋', '🐳', '🐬', '🐙', '🦑', '🐚',
            '🦀', '🦞', '🦐', '🐉', '🐲', '🌊', '💧', '💦', '🎣', '🪸'
        ]

        # Настройки работы
        self.work_interval = config.WORK_INTERVAL
        self.work_timeout = config.WORK_TIMEOUT
        self.work_click_delay = config.WORK_CLICK_DELAY

        logger.info("Универсальный бот инициализирован")

    # ==================== ОБЩИЕ МЕТОДЫ ====================

    async def start_client(self):
        """Запуск клиента и авторизация"""
        try:
            await self.client.start(phone=config.PHONE_NUMBER)
            logger.info("Клиент успешно запущен и авторизован")

            me = await self.client.get_me()
            logger.info(f"Авторизован как: {me.first_name} (@{me.username}, ID: {me.id})")

            chat_entity = await self.client.get_entity(self.chat_id)
            chat_info = getattr(chat_entity, 'title', str(chat_entity.id))
            logger.info(f"Чат найден: {chat_info}")

        except FloodWaitError as e:
            logger.error(f"Ошибка FloodWait: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка запуска клиента: {e}")
            raise

    async def get_message_with_buttons(self, after_id: int = 0, exclude_self: bool = True) -> Optional[Message]:
        """Получить сообщение с кнопками"""
        try:
            me = await self.client.get_me() if exclude_self else None

            async for message in self.client.iter_messages(self.chat_id, limit=10):
                if message.id <= after_id:
                    continue
                if exclude_self and message.sender_id == me.id:
                    continue
                if message.reply_markup:
                    return message
        except Exception as e:
            logger.error(f"Ошибка получения сообщения: {e}")
        return None

    # ==================== МЕТОДЫ ШАХТЫ ====================

    async def shaft_send_message(self) -> Optional[Message]:
        """Отправка сообщения 'Шахта'"""
        try:
            message = await self.client.send_message(self.chat_id, "Шахта")
            logger.info("[ШАХТА] Сообщение отправлено")
            return message
        except Exception as e:
            logger.error(f"[ШАХТА] Ошибка: {e}")
            return None

    async def shaft_find_descent_button(self, message: Message) -> bool:
        """Найти и нажать кнопку 'Спуститься'"""
        try:
            if not message or not message.reply_markup:
                return False

            flat_buttons = []
            for row in message.buttons:
                for btn in row:
                    flat_buttons.append(btn)

            button_index = None
            for idx, btn in enumerate(flat_buttons):
                if hasattr(btn, 'text') and btn.text and "спуст" in btn.text.lower():
                    button_index = idx
                    break

            if button_index is None:
                return False

            await message.click(button_index)
            await asyncio.sleep(3)
            return True

        except Exception as e:
            logger.error(f"[ШАХТА] Ошибка нажатия кнопки: {e}")
            return False

    async def shaft_click_resources(self, message: Message) -> int:
        """Сбор ресурсов (сначала 💎, потом 🪨)"""
        success_count = 0
        click_delay = 3

        while True:
            try:
                current_msg = await self.client.get_messages(self.chat_id, ids=message.id)
                if not current_msg or not current_msg.reply_markup:
                    break
            except Exception:
                break

            found = False
            flat_buttons = []
            for row in current_msg.buttons:
                for btn in row:
                    flat_buttons.append(btn)

            # Алмазы
            for idx, button in enumerate(flat_buttons):
                if button.text and self.diamond_emoji in button.text:
                    try:
                        await current_msg.click(idx)
                        success_count += 1
                        found = True
                        await asyncio.sleep(click_delay)
                        break
                    except Exception:
                        continue

            if found:
                continue

            # Камни
            for idx, button in enumerate(flat_buttons):
                if button.text and self.stone_emoji in button.text:
                    try:
                        await current_msg.click(idx)
                        success_count += 1
                        found = True
                        await asyncio.sleep(click_delay)
                        break
                    except Exception:
                        continue

            if not found:
                break

        return success_count

    async def shaft_cycle(self) -> bool:
        """Один цикл шахты"""
        logger.info("[ШАХТА] Начинаем цикл")

        msg = await self.shaft_send_message()
        if not msg:
            return False

        # Ждем кнопку "Спуститься"
        descent_msg = None
        for _ in range(self.shaft_timeout):
            descent_msg = await self.get_message_with_buttons(after_id=msg.id)
            if descent_msg:
                if await self.shaft_find_descent_button(descent_msg):
                    break
            await asyncio.sleep(1)

        if not descent_msg:
            return False

        # Ждем сообщение с ресурсами
        resources_msg = None
        for _ in range(self.shaft_timeout):
            candidate = await self.get_message_with_buttons(after_id=descent_msg.id)
            if candidate and candidate.id != descent_msg.id and candidate.reply_markup:
                resources_msg = candidate
                break
            await asyncio.sleep(1)

        if not resources_msg:
            return False

        await self.shaft_click_resources(resources_msg)
        return True

    async def shaft_loop(self):
        """Бесконечный цикл шахты"""
        self.shaft_stats['start_time'] = time.time()
        cycle_count = 0

        while self.shaft_running:
            try:
                cycle_count += 1
                self.shaft_stats['cycles'] = cycle_count
                logger.info(f"[ШАХТА] === Цикл #{cycle_count} ===")

                start = time.time()
                await self.shaft_cycle()
                self.shaft_stats['last_duration'] = time.time() - start

                self.shaft_stats['next_time'] = time.time() + self.shaft_interval
                await asyncio.sleep(self.shaft_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[ШАХТА] Ошибка: {e}")
                await asyncio.sleep(self.shaft_interval)

    # ==================== МЕТОДЫ РЫБАЛКИ ====================

    async def fishing_send_message(self) -> Optional[Message]:
        """Отправка сообщения 'Рыбалка'"""
        try:
            message = await self.client.send_message(self.chat_id, "Рыбалка")
            logger.info("[РЫБАЛКА] Сообщение отправлено")
            return message
        except Exception as e:
            logger.error(f"[РЫБАЛКА] Ошибка: {e}")
            return None

    async def fishing_click_button(self, message: Message, target_text: str) -> bool:
        """Нажать кнопку по тексту"""
        try:
            if not message or not message.reply_markup:
                return False

            buttons = []
            for row in message.buttons:
                for btn in row:
                    buttons.append(btn)

            for idx, btn in enumerate(buttons):
                if hasattr(btn, 'text') and btn.text and target_text.lower() in btn.text.lower():
                    await message.click(idx)
                    await asyncio.sleep(1)
                    return True
            return False
        except Exception as e:
            logger.error(f"[РЫБАЛКА] Ошибка: {e}")
            return False

    async def fishing_click_emoji(self, message: Message) -> bool:
        """Подсечка рыбы (нажать на появившийся эмодзи)"""
        try:
            if not message or not message.reply_markup:
                return False

            buttons = []
            for row in message.buttons:
                for btn in row:
                    buttons.append(btn)

            for idx, btn in enumerate(buttons):
                if hasattr(btn, 'text') and btn.text:
                    for emoji in self.fishing_emojis:
                        if emoji in btn.text:
                            delay = random.uniform(self.fishing_delay_min, self.fishing_delay_max)
                            await asyncio.sleep(delay)
                            await message.click(idx)
                            await asyncio.sleep(1)
                            return True
            return False
        except Exception as e:
            logger.error(f"[РЫБАЛКА] Ошибка: {e}")
            return False

    async def fishing_cycle(self) -> bool:
        """Один цикл рыбалки"""
        logger.info("[РЫБАЛКА] Начинаем цикл")

        msg = await self.fishing_send_message()
        if not msg:
            return False

        # Ждем меню и нажимаем "Рыбачить"
        menu_msg = None
        for _ in range(self.fishing_timeout):
            menu_msg = await self.get_message_with_buttons(after_id=msg.id)
            if menu_msg:
                break
            await asyncio.sleep(1)

        if not menu_msg:
            return False

        if not await self.fishing_click_button(menu_msg, "рыбачить"):
            return False

        # Ждем сетку
        grid_msg = None
        for _ in range(self.fishing_timeout):
            grid_msg = await self.get_message_with_buttons(after_id=menu_msg.id)
            if grid_msg and "закинули удочку" in grid_msg.text.lower():
                break
            await asyncio.sleep(1)

        if not grid_msg:
            return False

        # Ждем поклевку
        max_wait = 15
        start_wait = time.time()

        while time.time() - start_wait < max_wait:
            current_msg = await self.client.get_messages(self.chat_id, ids=grid_msg.id)
            if current_msg and current_msg.reply_markup:
                if await self.fishing_click_emoji(current_msg):
                    await asyncio.sleep(3)
                    return True
            await asyncio.sleep(0.3)

        return False

    async def fishing_loop(self):
        """Бесконечный цикл рыбалки"""
        self.fishing_stats['start_time'] = time.time()
        cycle_count = 0

        while self.fishing_running:
            try:
                cycle_count += 1
                self.fishing_stats['cycles'] = cycle_count
                logger.info(f"[РЫБАЛКА] === Цикл #{cycle_count} ===")

                start = time.time()
                await self.fishing_cycle()
                self.fishing_stats['last_duration'] = time.time() - start

                interval = random.uniform(self.fishing_interval_min, self.fishing_interval_max)
                self.fishing_stats['next_time'] = time.time() + interval
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[РЫБАЛКА] Ошибка: {e}")
                await asyncio.sleep(60)

    # ==================== МЕТОДЫ РАБОТЫ ====================

    async def work_send_message(self) -> Optional[Message]:
        """Отправка сообщения 'Работать'"""
        try:
            message = await self.client.send_message(self.chat_id, "Работать")
            logger.info("[РАБОТА] Сообщение отправлено")
            return message
        except Exception as e:
            logger.error(f"[РАБОТА] Ошибка: {e}")
            return None

    def work_extract_emoji(self, text: str) -> Optional[str]:
        """Извлечь смайлик из текста (между « »)"""
        pattern = r'«([^»]+)»'
        matches = re.findall(pattern, text)
        return matches[0].strip() if matches else None

    def work_is_completed(self, text: str) -> bool:
        """Проверить завершение смены"""
        keywords = ["смена завершена", "зарплата", "следующая смена"]
        return any(k in text.lower() for k in keywords)

    async def work_click_emoji(self, message: Message, target_emoji: str) -> bool:
        """Нажать кнопку с нужным смайликом"""
        try:
            if not message or not message.reply_markup:
                return False

            buttons = []
            for row in message.buttons:
                for btn in row:
                    buttons.append(btn)

            for idx, btn in enumerate(buttons):
                if hasattr(btn, 'text') and btn.text and target_emoji in btn.text:
                    await message.click(idx)
                    await asyncio.sleep(self.work_click_delay)
                    return True
            return False
        except Exception as e:
            logger.error(f"[РАБОТА] Ошибка: {e}")
            return False

    async def work_cycle(self) -> bool:
        """Один цикл работы"""
        logger.info("[РАБОТА] Начинаем цикл")

        msg = await self.work_send_message()
        if not msg:
            return False

        # Получаем сообщение от бота
        current_msg = None
        for _ in range(self.work_timeout):
            current_msg = await self.get_message_with_buttons(after_id=msg.id)
            if current_msg:
                break
            await asyncio.sleep(1)

        if not current_msg:
            return False

        # Цикл выполнения заданий
        for _ in range(20):
            try:
                current_msg = await self.client.get_messages(self.chat_id, ids=current_msg.id)
                if not current_msg or not current_msg.text:
                    break

                if self.work_is_completed(current_msg.text):
                    return True

                target_emoji = self.work_extract_emoji(current_msg.text)
                if not target_emoji:
                    await asyncio.sleep(2)
                    continue

                if await self.work_click_emoji(current_msg, target_emoji):
                    await asyncio.sleep(2)
                    next_msg = await self.get_message_with_buttons(after_id=current_msg.id)
                    if next_msg:
                        current_msg = next_msg
                else:
                    await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"[РАБОТА] Ошибка: {e}")
                break

        return False

    async def work_loop(self):
        """Бесконечный цикл работы"""
        self.work_stats['start_time'] = time.time()
        cycle_count = 0

        while self.work_running:
            try:
                cycle_count += 1
                self.work_stats['cycles'] = cycle_count
                logger.info(f"[РАБОТА] === Цикл #{cycle_count} ===")

                start = time.time()
                await self.work_cycle()
                self.work_stats['last_duration'] = time.time() - start

                self.work_stats['next_time'] = time.time() + self.work_interval
                await asyncio.sleep(self.work_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[РАБОТА] Ошибка: {e}")
                await asyncio.sleep(self.work_interval)

    # ==================== УПРАВЛЕНИЕ ====================

    def format_uptime(self, start_time):
        """Форматирование времени работы"""
        if not start_time:
            return "0м"
        uptime = time.time() - start_time
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        if hours > 0:
            return f"{hours}ч {minutes}м"
        return f"{minutes}м"

    def get_next_time(self, next_time):
        """Время до следующего цикла"""
        if not next_time:
            return "—"
        wait = max(0, next_time - time.time())
        return f"{int(wait)}с"

    async def get_status_text(self) -> str:
        """Получить статус всех активностей"""
        status_lines = ["📊 Статус активностей:"]

        # Шахта
        if self.shaft_running:
            status_lines.append(f"├─ ⛏️ Шахта: ✅ работает")
            status_lines.append(f"│  ├─ Циклов: {self.shaft_stats['cycles']}")
            status_lines.append(f"│  ├─ Время работы: {self.format_uptime(self.shaft_stats['start_time'])}")
            status_lines.append(f"│  └─ Следующий: {self.get_next_time(self.shaft_stats['next_time'])}")
        else:
            status_lines.append("├─ ⛏️ Шахта: ⏹️ остановлена")

        # Рыбалка
        if self.fishing_running:
            status_lines.append(f"├─ 🎣 Рыбалка: ✅ работает")
            status_lines.append(f"│  ├─ Циклов: {self.fishing_stats['cycles']}")
            status_lines.append(f"│  ├─ Время работы: {self.format_uptime(self.fishing_stats['start_time'])}")
            status_lines.append(f"│  └─ Следующий: {self.get_next_time(self.fishing_stats['next_time'])}")
        else:
            status_lines.append("├─ 🎣 Рыбалка: ⏹️ остановлена")

        # Работа
        if self.work_running:
            status_lines.append(f"└─ 💼 Работа: ✅ работает")
            status_lines.append(f"   ├─ Циклов: {self.work_stats['cycles']}")
            status_lines.append(f"   ├─ Время работы: {self.format_uptime(self.work_stats['start_time'])}")
            status_lines.append(f"   └─ Следующий: {self.get_next_time(self.work_stats['next_time'])}")
        else:
            status_lines.append("└─ 💼 Работа: ⏹️ остановлена")

        # Общее время работы бота
        if self.bot_start_time:
            status_lines.append(f"\n⏱️ Бот работает: {self.format_uptime(self.bot_start_time)}")

        return "\n".join(status_lines)

    async def start_shaft(self) -> bool:
        """Запуск шахты"""
        if self.shaft_running:
            return False
        self.shaft_running = True
        self.shaft_task = asyncio.create_task(self.shaft_loop())
        logger.info("⛏️ Шахта запущена")
        return True

    async def stop_shaft(self) -> bool:
        """Остановка шахты"""
        if not self.shaft_running:
            return False
        self.shaft_running = False
        if self.shaft_task:
            self.shaft_task.cancel()
            self.shaft_task = None
        logger.info("⛏️ Шахта остановлена")
        return True

    async def start_fishing(self) -> bool:
        """Запуск рыбалки"""
        if self.fishing_running:
            return False
        self.fishing_running = True
        self.fishing_task = asyncio.create_task(self.fishing_loop())
        logger.info("🎣 Рыбалка запущена")
        return True

    async def stop_fishing(self) -> bool:
        """Остановка рыбалки"""
        if not self.fishing_running:
            return False
        self.fishing_running = False
        if self.fishing_task:
            self.fishing_task.cancel()
            self.fishing_task = None
        logger.info("🎣 Рыбалка остановлена")
        return True

    async def start_work(self) -> bool:
        """Запуск работы"""
        if self.work_running:
            return False
        self.work_running = True
        self.work_task = asyncio.create_task(self.work_loop())
        logger.info("💼 Работа запущена")
        return True

    async def stop_work(self) -> bool:
        """Остановка работы"""
        if not self.work_running:
            return False
        self.work_running = False
        if self.work_task:
            self.work_task.cancel()
            self.work_task = None
        logger.info("💼 Работа остановлена")
        return True

    # ==================== ОБРАБОТЧИК КОМАНД ====================

    async def setup_handlers(self):
        """Настройка обработчиков сообщений"""

        @self.client.on(events.NewMessage)
        async def message_handler(event):
            # Проверяем чат
            if event.chat_id != self.chat_id:
                return

            text = event.message.text.lower().strip() if event.message.text else ""
            if not text:
                return

            logger.info(f"Получена команда: {text}")

            # Шахта
            if text in ['/shaft', 'шах']:
                success = await self.start_shaft()
                response = "✅ Шахта запущена!" if success else "⚠️ Шахта уже работает!"
                await event.reply(response)

            elif text in ['/sshaft', 'сшах']:
                success = await self.stop_shaft()
                response = "⏹️ Шахта остановлена!" if success else "⚠️ Шахта не работает!"
                await event.reply(response)

            # Рыбалка
            elif text in ['/fishing', 'рыб']:
                success = await self.start_fishing()
                response = "🎣 Рыбалка запущена!" if success else "⚠️ Рыбалка уже работает!"
                await event.reply(response)

            elif text in ['/sfishing', 'срыб']:
                success = await self.stop_fishing()
                response = "⏹️ Рыбалка остановлена!" if success else "⚠️ Рыбалка не работает!"
                await event.reply(response)

            # Работа
            elif text in ['/work', 'раб']:
                success = await self.start_work()
                response = "💼 Работа запущена!" if success else "⚠️ Работа уже работает!"
                await event.reply(response)

            elif text in ['/swork', 'сраб']:
                success = await self.stop_work()
                response = "⏹️ Работа остановлена!" if success else "⚠️ Работа не работает!"
                await event.reply(response)

            # Статус
            elif text in ['/status', 'стат']:
                status_text = await self.get_status_text()
                await event.reply(status_text)

    # ==================== ЗАПУСК ====================

    async def run(self):
        """Запуск бота"""
        try:
            await self.start_client()
            await self.setup_handlers()

            self.bot_start_time = time.time()

            logger.info("=" * 50)
            logger.info("🤖 Универсальный бот готов!")
            logger.info("")
            logger.info("Команды:")
            logger.info("  шах /shaft    - запустить шахту")
            logger.info("  сшах /sshaft  - остановить шахту")
            logger.info("  рыб /fishing  - запустить рыбалку")
            logger.info("  срыб /sfishing - остановить рыбалку")
            logger.info("  раб /work     - запустить работу")
            logger.info("  сраб /swork   - остановить работу")
            logger.info("  стат /status  - показать статус")
            logger.info("=" * 50)

            await self.client.run_until_disconnected()

        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания")
            await self.stop_shaft()
            await self.stop_fishing()
            await self.stop_work()
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}", exc_info=True)
        finally:
            await self.client.disconnect()
            logger.info("Бот остановлен")


def main():
    """Главная функция"""
    bot = UniversalBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Приложение остановлено пользователем")
    except Exception as e:
        logger.error(f"Необработанное исключение: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
