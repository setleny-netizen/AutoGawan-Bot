#!/usr/bin/env python3
"""
Универсальный Telegram юзербот
Управление: шахта, рыбалка, работа, ранчо (поиск семян)
Команды:
  шах /shaft     - запустить шахту
  сшах /sshaft   - остановить шахту
  рыб /fishing   - запустить рыбалку
  срыб /sfishing - остановить рыбалку
  раб /work      - запустить работу
  сраб /swork    - остановить работу
  поле /field    - запустить поиск семян
  споле /sfield  - остановить поиск семян
  стат /status   - показать статус
"""

import asyncio
import logging
import sys
import time
import random
import re
import os
from typing import Optional, Tuple

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
    """Универсальный бот для шахты, рыбалки, работы и ранчо"""

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
        self.field_running = False

        # Задачи активностей
        self.shaft_task: Optional[asyncio.Task] = None
        self.fishing_task: Optional[asyncio.Task] = None
        self.work_task: Optional[asyncio.Task] = None
        self.field_task: Optional[asyncio.Task] = None

        # Статистика
        self.bot_start_time = None
        self.shaft_stats = {'cycles': 0, 'start_time': None, 'next_time': None, 'last_duration': 0}
        self.fishing_stats = {'cycles': 0, 'start_time': None, 'next_time': None, 'last_duration': 0}
        self.work_stats = {'cycles': 0, 'start_time': None, 'next_time': None, 'last_duration': 0}
        self.field_stats = {'cycles': 0, 'start_time': None, 'next_time': None, 'last_duration': 0}

        # Общие настройки
        self.chat_id = int(config.CHAT_ID) if str(config.CHAT_ID).lstrip('-').isdigit() else config.CHAT_ID
        self.game_bot_id = config.GAME_BOT_ID  # ID игрового бота для ранчо

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

        # Настройки ранчо (поиск семян)
        self.field_interval = config.FIELD_INTERVAL
        self.field_timeout = config.FIELD_TIMEOUT
        self.field_click_delay = config.FIELD_CLICK_DELAY
        # Эмодзи для семян (овощи, фрукты, ягоды)
        self.seed_emojis = [
            '🧅', '🍅', '🥬', '🥕', '🌽', '🥒', '🍆', '🫑', '🥔', '🍠',
            '🍓', '🫐', '🍇', '🍉', '🍊', '🍋', '🍎', '🍐', '🍑', '🍒',
            '🥝', '🥥', '🌶️', '🧄', '🫒', '🥦', '🌻', '🌾', '🍄', '🌿'
        ]

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

    async def get_message_with_buttons(self, after_id: int = 0, exclude_self: bool = True,
                                       use_game_bot: bool = False) -> Optional[Message]:
        """Получить сообщение с кнопками"""
        try:
            me = await self.client.get_me() if exclude_self else None
            chat_id = self.game_bot_id if use_game_bot else self.chat_id

            async for message in self.client.iter_messages(chat_id, limit=10):
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
            await asyncio.sleep(10)
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

    # ==================== МЕТОДЫ РАНЧО (ПОИСК СЕМЯН) ====================

    async def field_send_message(self) -> Optional[Message]:
        """Отправка сообщения 'Ранчо' в ЛС с игровым ботом"""
        try:
            message = await self.client.send_message(self.game_bot_id, "Ранчо")
            logger.info("[РАНЧО] Сообщение 'Ранчо' отправлено в ЛС")
            return message
        except Exception as e:
            logger.error(f"[РАНЧО] Ошибка отправки: {e}")
            return None

    async def field_click_button(self, message: Message, target_text: str) -> bool:
        """Нажать кнопку по тексту"""
        try:
            if not message or not message.reply_markup:
                return False

            buttons = []
            for row in message.buttons:
                for btn in row:
                    buttons.append(btn)

            button_texts = [btn.text for btn in buttons if hasattr(btn, 'text')]
            logger.info(f"[РАНЧО] Доступные кнопки: {button_texts}")

            for idx, btn in enumerate(buttons):
                if hasattr(btn, 'text') and btn.text:
                    btn_lower = btn.text.lower()
                    if "поле" in btn_lower or "поиск семян" in btn_lower:
                        logger.info(f"[РАНЧО] Найдена кнопка: {btn.text} (индекс {idx})")
                        await message.click(idx)
                        await asyncio.sleep(2)
                        return True

            logger.warning(f"[РАНЧО] Кнопка с текстом '{target_text}' не найдена")
            return False
        except Exception as e:
            logger.error(f"[РАНЧО] Ошибка нажатия кнопки: {e}")
            return False

    async def field_wait_for_message_update(self, message_id: int, timeout: int = 30, check_text: str = None) -> \
    Optional[Message]:
        """Ожидать обновления сообщения"""
        start_time = time.time()
        last_text = None

        while time.time() - start_time < timeout:
            try:
                # Получаем текущее сообщение
                current_msg = await self.client.get_messages(self.game_bot_id, ids=message_id)

                if current_msg and current_msg.text:
                    # Если указан текст для проверки и он найден
                    if check_text:
                        if check_text in current_msg.text.lower():
                            logger.info(f"[РАНЧО] Обнаружено обновление: {check_text}")
                            return current_msg
                    # Иначе ждем любого изменения текста
                    elif last_text is not None and current_msg.text != last_text:
                        logger.info("[РАНЧО] Обнаружено обновление сообщения")
                        return current_msg

                    last_text = current_msg.text

            except Exception as e:
                logger.error(f"[РАНЧО] Ошибка при проверке обновления: {e}")

            await asyncio.sleep(1)

        logger.warning(f"[РАНЧО] Таймаут ожидания обновления сообщения {message_id}")
        return None

    async def field_click_all_seeds(self, message: Message) -> int:
        """Собрать все семена (нажать на все эмодзи в сетке)"""
        success_count = 0

        if not message.reply_markup:
            logger.warning("[РАНЧО] В сообщении нет кнопок")
            return 0

        buttons = []
        for row in message.buttons:
            for btn in row:
                buttons.append(btn)

        logger.info(f"[РАНЧО] Всего кнопок в сетке: {len(buttons)}")

        # Выводим все кнопки для отладки
        for idx, btn in enumerate(buttons):
            if hasattr(btn, 'text') and btn.text:
                logger.info(f"[РАНЧО] Кнопка {idx}: '{btn.text}'")

        # Ищем и нажимаем кнопки с эмодзи семян
        for idx, btn in enumerate(buttons):
            if hasattr(btn, 'text') and btn.text:
                for emoji in self.seed_emojis:
                    if emoji in btn.text:
                        try:
                            logger.info(f"[РАНЧО] Собираем: {btn.text} (индекс {idx})")
                            await message.click(idx)
                            success_count += 1
                            await asyncio.sleep(self.field_click_delay)
                            break
                        except Exception as e:
                            logger.error(f"[РАНЧО] Ошибка при сборе: {e}")

        logger.info(f"[РАНЧО] Всего собрано семян: {success_count}")
        return success_count

    def field_extract_wait_time(self, text: str) -> Optional[int]:
        """Извлечь время ожидания из текста (формат мм:сс)"""
        # Ищем текст "через: 04:22"
        pattern = r'через:\s*(\d+):(\d+)'
        matches = re.findall(pattern, text)
        if matches:
            minutes = int(matches[0][0])
            seconds = int(matches[0][1])
            total_seconds = minutes * 60 + seconds + 10  # +10 сек запас
            logger.info(f"[РАНЧО] Найдено время: {minutes}:{seconds:02d} -> ждем {total_seconds} сек")
            return total_seconds

        logger.warning("[РАНЧО] Время не найдено в тексте")
        return None

    async def field_cycle(self) -> bool:
        """Один цикл поиска семян"""
        logger.info("[РАНЧО] Начинаем цикл поиска семян")

        # Отправляем "Ранчо" в ЛС игровому боту
        msg = await self.field_send_message()
        if not msg:
            return False

        # Ждем меню ранчо
        menu_msg = None
        for _ in range(self.field_timeout):
            menu_msg = await self.get_message_with_buttons(after_id=msg.id, use_game_bot=True)
            if menu_msg and "меню ранчо" in menu_msg.text.lower():
                logger.info("[РАНЧО] Меню ранчо получено")
                break
            await asyncio.sleep(1)

        if not menu_msg:
            logger.warning("[РАНЧО] Меню ранчо не получено")
            return False

        # Сохраняем ID сообщения
        message_id = menu_msg.id

        # Нажимаем кнопку "Поле [поиск семян]"
        if not await self.field_click_button(menu_msg, "поле"):
            logger.warning("[РАНЧО] Кнопка 'Поле' не найдена")
            return False

        # Ждем обновления сообщения (появится сетка)
        logger.info("[РАНЧО] Ожидаем появления сетки...")
        grid_msg = await self.field_wait_for_message_update(message_id, timeout=30, check_text="жмите на семена")

        if not grid_msg:
            logger.warning("[РАНЧО] Сетка с семенами не получена")
            return False

        logger.info("[РАНЧО] Сетка с семенами получена, начинаем сбор")

        # Собираем все семена
        collected = await self.field_click_all_seeds(grid_msg)
        logger.info(f"[РАНЧО] Собрано семян: {collected}")

        # Ждем следующего обновления сообщения (результат с временем)
        logger.info("[РАНЧО] Ожидаем результат...")
        result_msg = await self.field_wait_for_message_update(message_id, timeout=30, check_text="собрали семена")

        if result_msg:
            # Извлекаем время до следующего похода
            wait_time = self.field_extract_wait_time(result_msg.text)
            if wait_time:
                logger.info(f"[РАНЧО] Следующий поход через {wait_time} сек")
                self.field_stats['next_time'] = time.time() + wait_time
                await asyncio.sleep(wait_time)
            else:
                # Если не нашли время, ждем стандартный интервал
                wait_time = self.field_interval
                self.field_stats['next_time'] = time.time() + wait_time
                logger.info(f"[РАНЧО] Время не найдено, ждем {wait_time} сек")
                await asyncio.sleep(wait_time)
        else:
            # Если не получили результат, ждем стандартный интервал
            logger.info("[РАНЧО] Результат не получен")
            await asyncio.sleep(self.field_interval)

        return True

    async def field_loop(self):
        """Бесконечный цикл поиска семян"""
        self.field_stats['start_time'] = time.time()
        cycle_count = 0

        while self.field_running:
            try:
                cycle_count += 1
                self.field_stats['cycles'] = cycle_count
                logger.info(f"[РАНЧО] === Цикл #{cycle_count} ===")

                start = time.time()
                await self.field_cycle()
                self.field_stats['last_duration'] = time.time() - start

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[РАНЧО] Ошибка: {e}")
                await asyncio.sleep(60)

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
            status_lines.append(f"├─ 💼 Работа: ✅ работает")
            status_lines.append(f"│  ├─ Циклов: {self.work_stats['cycles']}")
            status_lines.append(f"│  ├─ Время работы: {self.format_uptime(self.work_stats['start_time'])}")
            status_lines.append(f"│  └─ Следующий: {self.get_next_time(self.work_stats['next_time'])}")
        else:
            status_lines.append("├─ 💼 Работа: ⏹️ остановлена")

        # Ранчо (поиск семян)
        if self.field_running:
            status_lines.append(f"└─ 🌾 Ранчо: ✅ работает")
            status_lines.append(f"   ├─ Циклов: {self.field_stats['cycles']}")
            status_lines.append(f"   ├─ Время работы: {self.format_uptime(self.field_stats['start_time'])}")
            status_lines.append(f"   └─ Следующий: {self.get_next_time(self.field_stats['next_time'])}")
        else:
            status_lines.append("└─ 🌾 Ранчо: ⏹️ остановлено")

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

    async def start_field(self) -> bool:
        """Запуск поиска семян"""
        if self.field_running:
            return False
        self.field_running = True
        self.field_task = asyncio.create_task(self.field_loop())
        logger.info("🌾 Поиск семян запущен")
        return True

    async def stop_field(self) -> bool:
        """Остановка поиска семян"""
        if not self.field_running:
            return False
        self.field_running = False
        if self.field_task:
            self.field_task.cancel()
            self.field_task = None
        logger.info("🌾 Поиск семян остановлен")
        return True

    # ==================== ОБРАБОТЧИК КОМАНД ====================

    async def setup_handlers(self):
        """Настройка обработчиков сообщений"""

        @self.client.on(events.NewMessage)
        async def message_handler(event):
            # Проверяем, что сообщение либо из группы Farm, либо из ЛС с игровым ботом
            if event.chat_id != self.chat_id and event.chat_id != self.game_bot_id:
                return

            text = event.message.text if event.message.text else ""
            if not text:
                return

            text_lower = text.lower().strip()

            # Список допустимых команд (только их обрабатываем)
            valid_commands = [
                '/shaft', 'шах',
                '/sshaft', 'сшах',
                '/fishing', 'рыб',
                '/sfishing', 'срыб',
                '/work', 'раб',
                '/swork', 'сраб',
                '/field', 'поле',
                '/sfield', 'споле',
                '/status', 'стат'
            ]

            # Если это не команда - игнорируем
            if text_lower not in valid_commands:
                return

            logger.info(f"Получена команда: {text_lower} (чат: {event.chat_id})")

            # Шахта
            if text_lower in ['/shaft', 'шах']:
                success = await self.start_shaft()
                response = "✅ Шахта запущена!" if success else "⚠️ Шахта уже работает!"
                await event.reply(response)

            elif text_lower in ['/sshaft', 'сшах']:
                success = await self.stop_shaft()
                response = "⏹️ Шахта остановлена!" if success else "⚠️ Шахта не работает!"
                await event.reply(response)

            # Рыбалка
            elif text_lower in ['/fishing', 'рыб']:
                success = await self.start_fishing()
                response = "🎣 Рыбалка запущена!" if success else "⚠️ Рыбалка уже работает!"
                await event.reply(response)

            elif text_lower in ['/sfishing', 'срыб']:
                success = await self.stop_fishing()
                response = "⏹️ Рыбалка остановлена!" if success else "⚠️ Рыбалка не работает!"
                await event.reply(response)

            # Работа
            elif text_lower in ['/work', 'раб']:
                success = await self.start_work()
                response = "💼 Работа запущена!" if success else "⚠️ Работа уже работает!"
                await event.reply(response)

            elif text_lower in ['/swork', 'сраб']:
                success = await self.stop_work()
                response = "⏹️ Работа остановлена!" if success else "⚠️ Работа не работает!"
                await event.reply(response)

            # Ранчо
            elif text_lower in ['/field', 'поле']:
                success = await self.start_field()
                response = "🌾 Поиск семян запущен!" if success else "⚠️ Поиск семян уже работает!"
                await event.reply(response)

            elif text_lower in ['/sfield', 'споле']:
                success = await self.stop_field()
                response = "⏹️ Поиск семян остановлен!" if success else "⚠️ Поиск семян не работает!"
                await event.reply(response)

            # Статус
            elif text_lower in ['/status', 'стат']:
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
            logger.info("  шах /shaft     - запустить шахту")
            logger.info("  сшах /sshaft   - остановить шахту")
            logger.info("  рыб /fishing   - запустить рыбалку")
            logger.info("  срыб /sfishing - остановить рыбалку")
            logger.info("  раб /work      - запустить работу")
            logger.info("  сраб /swork    - остановить работу")
            logger.info("  поле /field    - запустить поиск семян")
            logger.info("  споле /sfield  - остановить поиск семян")
            logger.info("  стат /status   - показать статус")
            logger.info("=" * 50)

            await self.client.run_until_disconnected()

        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания")
            await self.stop_shaft()
            await self.stop_fishing()
            await self.stop_work()
            await self.stop_field()
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
