#!/usr/bin/env python3
"""
=============================================================================
🤖 УНИВЕРСАЛЬНЫЙ TELEGRAM БОТ — ОДИН ФАЙЛ
=============================================================================
Модули: Шахта | Рыбалка | Работа | Поле | Грядки | Гонки
Все функции в одном файле для простоты запуска
Поддержка двух аккаунтов
=============================================================================
"""

import asyncio
import logging
import sys
import time
import os
import re
import random
import unicodedata
from typing import Optional, List, Tuple, Dict

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.types import Message

import config

# =============================================================================
# 📁 НАСТРОЙКИ
# =============================================================================
SESSION_DIR = 'sessions'
if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# =============================================================================
# 📸 КАПЧА (распознавание по эталонам)
# =============================================================================
from PIL import Image
import numpy as np
import io


class CaptchaSolver:
    def __init__(self, templates_dir="captcha_templates"):
        self.templates_dir = templates_dir
        self.templates = {}  # {emoji: image_array}
        self._load_templates()

    def _load_templates(self):
        """Загружает все эталоны из папки"""
        if not os.path.exists(self.templates_dir):
            logger.warning(f"Папка {self.templates_dir} не найдена")
            return

        for filename in os.listdir(self.templates_dir):
            if filename.endswith(('.png', '.jpg', '.jpeg')):
                # Имя файла = эмодзи (например "👍.png")
                emoji = filename.split('.')[0]
                try:
                    img_path = os.path.join(self.templates_dir, filename)
                    img = Image.open(img_path).convert('RGB')
                    self.templates[emoji] = np.array(img)
                    logger.info(f"📸 Загружен эталон: {emoji}")
                except Exception as e:
                    logger.error(f"Ошибка загрузки {filename}: {e}")

        logger.info(f"📸 Загружено эталонов: {len(self.templates)}")

    def compare_images(self, img_array, template_array):
        """Сравнивает два изображения (возвращает разницу)"""
        # Приводим к одинаковому размеру
        if img_array.shape != template_array.shape:
            # Ресайзим до размера эталона
            img_pil = Image.fromarray(img_array)
            img_pil = img_pil.resize((template_array.shape[1], template_array.shape[0]))
            img_array = np.array(img_pil)

        # Вычисляем разницу
        diff = np.sum((img_array - template_array) ** 2)
        return diff

    async def solve(self, client, message, chat_id, my_id) -> Optional[str]:
        """
        Решает капчу: скачивает картинку, находит эмодзи, нажимает кнопку
        Возвращает True если успешно
        """
        if not message.photo:
            return None

        logger.info("📸 Обнаружена капча! Решаем...")

        # 1. Скачиваем картинку
        try:
            photo_path = await message.download_media()
            if not photo_path:
                logger.error("Не удалось скачать картинку")
                return None
        except Exception as e:
            logger.error(f"Ошибка скачивания: {e}")
            return None

        # 2. Загружаем картинку
        try:
            img = Image.open(photo_path).convert('RGB')
            img_array = np.array(img)
        except Exception as e:
            logger.error(f"Ошибка загрузки картинки: {e}")
            os.remove(photo_path)
            return None

        # 3. Ищем самый похожий эталон
        best_match = None
        best_score = float('inf')

        for emoji, template in self.templates.items():
            try:
                score = self.compare_images(img_array, template)
                logger.debug(f"Сравнение с {emoji}: разница {score}")
                if score < best_score:
                    best_score = score
                    best_match = emoji
            except Exception as e:
                logger.error(f"Ошибка сравнения с {emoji}: {e}")

        # Удаляем временный файл
        os.remove(photo_path)

        if not best_match:
            logger.warning("Не удалось распознать эмодзи на капче")
            return None

        logger.info(f"📸 Распознан эмодзи: {best_match} (разница: {best_score})")

        # 4. Нажимаем кнопку с этим эмодзи
        if not message.reply_markup:
            logger.warning("Нет кнопок для нажатия")
            return None

        buttons = [btn for row in message.buttons for btn in row]
        for idx, btn in enumerate(buttons):
            if hasattr(btn, 'text') and btn.text and best_match in btn.text:
                logger.info(f"✅ Нажимаем кнопку: {btn.text}")
                await click_safe(client, message, idx, delay=2)
                return best_match

        logger.warning(f"Кнопка с эмодзи {best_match} не найдена")
        return None


# Создаем глобальный экземпляр
captcha_solver = CaptchaSolver()


# =============================================================================
# 🔧 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def normalize_text(text: str) -> str:
    """Нормализовать текст: убрать невидимые символы"""
    if not text:
        return ""
    text = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff]', '', text)
    text = unicodedata.normalize('NFKC', text)
    return text.strip()


async def click_safe(client, message: Message, index: int, delay: float = None) -> bool:
    """Безопасный клик с обработкой FloodWait"""
    if delay is None:
        delay = config.CLICK_DELAY
    try:
        if not message or not message.reply_markup:
            return False
        await message.click(index)
        await asyncio.sleep(delay)
        return True
    except FloodWaitError as e:
        logger.warning(f"⏳ FloodWait: {e.seconds} сек")
        await asyncio.sleep(e.seconds + 1)
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка клика: {e}")
        return False


async def wait_for_message(client, chat_id: int, my_id: int, after_id: int = 0,
                           timeout: int = None, check_text: str = None,
                           has_buttons: bool = False) -> Optional[Message]:
    """Ожидать сообщение с условиями"""
    if timeout is None:
        timeout = config.MESSAGE_TIMEOUT
    start = time.time()
    while time.time() - start < timeout:
        try:
            async for msg in client.iter_messages(chat_id, limit=10):
                if msg.id <= after_id:
                    continue
                if msg.sender_id == my_id:
                    continue
                if has_buttons and not msg.reply_markup:
                    continue
                if check_text and msg.text and check_text.lower() not in msg.text.lower():
                    continue
                return msg
        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
        await asyncio.sleep(0.8)
    return None


async def handle_ok_alert(client, chat_id: int, my_id: int, timeout: int = 8) -> bool:
    """Найти и нажать ОК"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            async for msg in client.iter_messages(chat_id, limit=5):
                if msg.sender_id == my_id:
                    continue
                if msg.text and msg.reply_markup:
                    for row in msg.buttons:
                        for btn in row:
                            if hasattr(btn, 'text') and btn.text:
                                if btn.text.lower() in config.BUTTONS['ok']:
                                    await msg.click(btn)
                                    await asyncio.sleep(0.8)
                                    return True
        except:
            pass
        await asyncio.sleep(0.7)
    return False


# =============================================================================
# ⛏️  МОДУЛЬ: ШАХТА
# =============================================================================

class ShaftModule:
    def __init__(self, client, my_id):
        self.name = "⛏️ ШАХТА"
        self.chat_id = config.GROUP_CHAT_ID
        self.client = client
        self.my_id = my_id
        self.running = False
        self.task = None
        self.stats = {'cycles': 0, 'start_time': None, 'success': 0, 'fail': 0}
        logger.info(f"[{self.name}] Инициализирован")

    async def cycle(self) -> bool:
        logger.info(f"[{self.name}] Начинаем цикл")

        msg = await self.client.send_message(self.chat_id, "Шахта")
        await asyncio.sleep(1)

        menu_msg = await wait_for_message(self.client, self.chat_id, self.my_id,
                                          after_id=msg.id, has_buttons=True,
                                          timeout=config.SHAFT_TIMEOUT)
        if not menu_msg:
            return False

        # Найти и нажать "Спуститься"
        buttons = []
        for row in menu_msg.buttons:
            for btn in row:
                buttons.append(btn)
        for idx, btn in enumerate(buttons):
            if hasattr(btn, 'text') and btn.text and "спуст" in btn.text.lower():
                await click_safe(self.client, menu_msg, idx, delay=2)
                break

        # Ждём ресурсы
        resources_msg = await wait_for_message(self.client, self.chat_id, self.my_id,
                                               after_id=menu_msg.id, has_buttons=True,
                                               timeout=config.SHAFT_TIMEOUT)
        if not resources_msg:
            return False

        # Собираем 💎 → 🪨
        collected = await self._collect(resources_msg)
        logger.info(f"[{self.name}] Собрано: {collected}")
        return collected > 0

    async def _collect(self, message: Message) -> int:
        count = 0
        if not message.reply_markup:
            return 0

        for _ in range(10):  # Алмазы
            found = False
            buttons = [btn for row in message.buttons for btn in row]
            for idx, btn in enumerate(buttons):
                if hasattr(btn, 'text') and btn.text and config.SHAFT_EMOJIS['diamond'] in btn.text:
                    if await click_safe(self.client, message, idx, delay=2):
                        count += 1
                        found = True
                        try:
                            message = await self.client.get_messages(self.chat_id, ids=message.id)
                        except:
                            pass
                        break
            if not found:
                break

        for _ in range(10):  # Камни
            found = False
            buttons = [btn for row in message.buttons for btn in row]
            for idx, btn in enumerate(buttons):
                if hasattr(btn, 'text') and btn.text and config.SHAFT_EMOJIS['stone'] in btn.text:
                    if await click_safe(self.client, message, idx, delay=2):
                        count += 1
                        found = True
                        try:
                            message = await self.client.get_messages(self.chat_id, ids=message.id)
                        except:
                            pass
                        break
            if not found:
                break
        return count

    async def loop(self):
        self.stats['start_time'] = time.time()
        logger.info(f"[{self.name}] 🚀 Запущен")
        while self.running:
            try:
                self.stats['cycles'] += 1
                logger.info(f"[{self.name}] 📊 Цикл #{self.stats['cycles']}")
                start = time.time()
                ok = await self.cycle()
                if ok:
                    self.stats['success'] += 1
                else:
                    self.stats['fail'] += 1
                logger.info(f"[{self.name}] ⏱️ {int(time.time() - start)}сек")
                await asyncio.sleep(config.SHAFT_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.name}] ❌ {e}")
                await asyncio.sleep(60)

    async def start(self):
        if self.running:
            return False
        self.running = True
        self.task = asyncio.create_task(self.loop())
        return True

    async def stop(self):
        if not self.running:
            return False
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except:
                pass
        return True

    def get_status(self) -> dict:
        uptime = "0м"
        if self.stats['start_time']:
            m = int((time.time() - self.stats['start_time']) / 60)
            uptime = f"{m}мин"
        return {'name': self.name, 'running': self.running, 'cycles': self.stats['cycles'],
                'uptime': uptime, 'success': self.stats['success'], 'fail': self.stats['fail']}


# =============================================================================
# 🎣  МОДУЛЬ: РЫБАЛКА
# =============================================================================

class FishingModule:
    def __init__(self, client, my_id):
        self.name = "🎣 РЫБАЛКА"
        self.chat_id = config.GROUP_CHAT_ID
        self.client = client
        self.my_id = my_id
        self.running = False
        self.task = None
        self.stats = {'cycles': 0, 'start_time': None, 'success': 0, 'fail': 0}
        logger.info(f"[{self.name}] Инициализирован")

    async def cycle(self) -> bool:
        logger.info(f"[{self.name}] Начинаем цикл")

        msg = await self.client.send_message(self.chat_id, "Рыбалка")
        await asyncio.sleep(1.5)

        menu_msg = await wait_for_message(self.client, self.chat_id, self.my_id,
                                          after_id=msg.id, has_buttons=True,
                                          timeout=config.FISHING_TIMEOUT)
        if not menu_msg:
            return False

        # Нажать "Рыбачить"
        buttons = [btn for row in menu_msg.buttons for btn in row]
        for idx, btn in enumerate(buttons):
            if hasattr(btn, 'text') and btn.text and 'рыбачить' in btn.text.lower():
                await click_safe(self.client, menu_msg, idx, delay=2)
                break

        # Ждём сетку
        grid_id = None
        start = time.time()
        while time.time() - start < config.FISHING_TIMEOUT:
            async for m in self.client.iter_messages(self.chat_id, limit=10):
                if m.id <= menu_msg.id or m.sender_id == self.my_id:
                    continue
                if m.text and 'закинули удочку' in m.text.lower():
                    grid_id = m.id
                    break
            if grid_id:
                break
            await asyncio.sleep(0.5)

        if not grid_id:
            return False

        return await self._wait_and_hook(grid_id)

    async def _wait_and_hook(self, grid_id: int, max_wait: int = 30) -> bool:
        start = time.time()
        while time.time() - start < max_wait:
            try:
                msg = await self.client.get_messages(self.chat_id, ids=grid_id)
                if not msg or not msg.reply_markup:
                    await asyncio.sleep(0.3)
                    continue

                buttons = [(btn.text, btn) for row in msg.buttons for btn in row if hasattr(btn, 'text')]

                for idx, (txt, btn) in enumerate(buttons):
                    if txt:
                        for emoji in config.FISHING_EMOJIS:
                            if emoji in txt:
                                delay = random.uniform(config.FISHING_DELAY_MIN, config.FISHING_DELAY_MAX)
                                logger.info(f"[{self.name}] 🐟 Поклевка! ({emoji}) Задержка {delay:.1f}с")
                                await asyncio.sleep(delay)

                                for attempt in range(3):
                                    try:
                                        fresh = await self.client.get_messages(self.chat_id, ids=grid_id)
                                        await fresh.click(idx)
                                        await asyncio.sleep(1.5)
                                        check = await self.client.get_messages(self.chat_id, ids=grid_id)
                                        if check.text and ('поймали' in check.text.lower() or not check.reply_markup):
                                            return True
                                        await asyncio.sleep(1)
                                    except:
                                        await asyncio.sleep(0.5)
                                return False
            except Exception as e:
                logger.error(f"[{self.name}] Ошибка: {e}")
            await asyncio.sleep(0.4)
        return False

    async def loop(self):
        self.stats['start_time'] = time.time()
        logger.info(f"[{self.name}] 🚀 Запущен")
        while self.running:
            try:
                self.stats['cycles'] += 1
                logger.info(f"[{self.name}] 📊 Цикл #{self.stats['cycles']}")
                start = time.time()
                ok = await self.cycle()
                if ok:
                    self.stats['success'] += 1
                else:
                    self.stats['fail'] += 1
                logger.info(f"[{self.name}] ⏱️ {int(time.time() - start)}сек")
                interval = random.uniform(config.FISHING_INTERVAL_MIN, config.FISHING_INTERVAL_MAX)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.name}] ❌ {e}")
                await asyncio.sleep(60)

    async def start(self):
        if self.running:
            return False
        self.running = True
        self.task = asyncio.create_task(self.loop())
        return True

    async def stop(self):
        if not self.running:
            return False
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except:
                pass
        return True

    def get_status(self) -> dict:
        uptime = "0м"
        if self.stats['start_time']:
            m = int((time.time() - self.stats['start_time']) / 60)
            uptime = f"{m}мин"
        return {'name': self.name, 'running': self.running, 'cycles': self.stats['cycles'],
                'uptime': uptime, 'success': self.stats['success'], 'fail': self.stats['fail']}


# =============================================================================
# 💼  МОДУЛЬ: РАБОТА
# =============================================================================

class WorkModule:
    def __init__(self, client, my_id):
        self.name = "💼 РАБОТА"
        self.chat_id = config.GROUP_CHAT_ID
        self.client = client
        self.my_id = my_id
        self.running = False
        self.task = None
        self.stats = {'cycles': 0, 'start_time': None, 'success': 0, 'fail': 0}
        logger.info(f"[{self.name}] Инициализирован")

    def _extract_emoji(self, text: str) -> Optional[str]:
        if not text:
            return None
        pattern = r'«\s*([^\s»]+)\s*»'
        matches = re.findall(pattern, text)
        return matches[0].strip() if matches else None

    def _is_completed(self, text: str) -> bool:
        if not text:
            return False
        return any(k in text.lower() for k in config.WORK_KEYWORDS['completed'])

    def _extract_wait_time(self, text: str) -> Optional[int]:
        """Извлечь время ожидания из текста (формат мм:сс) и добавить +5 сек"""
        if not text:
            return None
        pattern = r'через:\s*(\d+):(\d+)'
        matches = re.findall(pattern, text)
        if matches:
            minutes = int(matches[0][0])
            seconds = int(matches[0][1])
            total_seconds = minutes * 60 + seconds + 2  # +2 сек запас
            logger.info(f"[{self.name}] ⏱️ Найдено время: {minutes}:{seconds:02d} -> ждем {total_seconds} сек")
            return total_seconds
        return None

    async def cycle(self) -> bool:
        logger.info(f"[{self.name}] Начинаем цикл")

        msg = await self.client.send_message(self.chat_id, "Работать")
        await asyncio.sleep(1.5)

        current = await wait_for_message(self.client, self.chat_id, self.my_id,
                                         after_id=msg.id, has_buttons=True,
                                         timeout=config.WORK_TIMEOUT)
        if not current or not current.text:
            return False

        for _ in range(30):
            if self._is_completed(current.text):
                logger.info(f"[{self.name}] ✅ Смена завершена!")
                # Извлекаем время до следующей смены
                wait_time = self._extract_wait_time(current.text)
                if wait_time:
                    logger.info(f"[{self.name}] ⏱️ Ждём {wait_time} сек до следующей смены")
                    await asyncio.sleep(wait_time)
                return True

            emoji = self._extract_emoji(current.text)
            if not emoji:
                await asyncio.sleep(2)
                try:
                    current = await self.client.get_messages(self.chat_id, ids=current.id)
                except:
                    break
                continue

            # Найти и нажать кнопку с эмодзи
            buttons = [btn for row in current.buttons for btn in row]
            clicked = False
            for idx, btn in enumerate(buttons):
                if hasattr(btn, 'text') and btn.text and emoji in btn.text:
                    await click_safe(self.client, current, idx, delay=config.WORK_CLICK_DELAY)
                    clicked = True
                    break

            if clicked:
                await asyncio.sleep(2.5)
                try:
                    current = await self.client.get_messages(self.chat_id, ids=current.id)
                except:
                    break
            else:
                await asyncio.sleep(2)
                try:
                    current = await self.client.get_messages(self.chat_id, ids=current.id)
                except:
                    break
        return True

    async def loop(self):
        self.stats['start_time'] = time.time()
        logger.info(f"[{self.name}] 🚀 Запущен")
        while self.running:
            try:
                self.stats['cycles'] += 1
                logger.info(f"[{self.name}] 📊 Цикл #{self.stats['cycles']}")
                start = time.time()
                ok = await self.cycle()
                if ok:
                    self.stats['success'] += 1
                else:
                    self.stats['fail'] += 1
                logger.info(f"[{self.name}] ⏱️ {int(time.time() - start)}сек")
                # Если время не было извлечено из сообщения, используем интервал из конфига
                # Но обычно время уже обработано в cycle()
                await asyncio.sleep(1)  # Небольшая пауза перед следующим циклом
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.name}] ❌ {e}")
                await asyncio.sleep(60)

    async def start(self):
        if self.running:
            return False
        self.running = True
        self.task = asyncio.create_task(self.loop())
        return True

    async def stop(self):
        if not self.running:
            return False
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except:
                pass
        return True

    def get_status(self) -> dict:
        uptime = "0м"
        if self.stats['start_time']:
            m = int((time.time() - self.stats['start_time']) / 60)
            uptime = f"{m}мин"
        return {'name': self.name, 'running': self.running, 'cycles': self.stats['cycles'],
                'uptime': uptime, 'success': self.stats['success'], 'fail': self.stats['fail']}


# =============================================================================
# 🌾  МОДУЛЬ: ПОЛЕ (ПОИСК СЕМЯН)
# =============================================================================

class FieldModule:
    def __init__(self, client, my_id):
        self.name = "🌾 ПОЛЕ"
        self.chat_id = config.PRIVATE_CHAT_ID
        self.client = client
        self.my_id = my_id
        self.running = False
        self.task = None
        self.stats = {'cycles': 0, 'start_time': None, 'success': 0, 'fail': 0}
        logger.info(f"[{self.name}] Инициализирован")

    async def cycle(self) -> bool:
        logger.info(f"[{self.name}] Начинаем цикл")

        msg = await self.client.send_message(self.chat_id, "Ранчо")
        await asyncio.sleep(1)

        menu = await wait_for_message(self.client, self.chat_id, self.my_id,
                                      after_id=msg.id, check_text="меню ранчо",
                                      has_buttons=True, timeout=config.FIELD_TIMEOUT)
        if not menu:
            return False

        msg_id = menu.id

        # Нажать "Поле"
        buttons = [btn for row in menu.buttons for btn in row]
        clicked = False
        for idx, btn in enumerate(buttons):
            if hasattr(btn, 'text') and btn.text:
                if any(k in btn.text.lower() for k in ['поле', 'поиск семян']):
                    await click_safe(self.client, menu, idx, delay=2)
                    clicked = True
                    break
        if not clicked:
            return False

        # Ждём сетку
        grid = None
        start = time.time()
        while time.time() - start < config.FIELD_TIMEOUT:
            try:
                m = await self.client.get_messages(self.chat_id, ids=msg_id)
                if m and m.text and "жмите на семена" in m.text.lower():
                    grid = m
                    break
            except:
                pass
            await asyncio.sleep(1)

        if not grid:
            return False

        # Собираем семена
        collected = 0
        buttons = [btn for row in grid.buttons for btn in row]
        for idx, btn in enumerate(buttons):
            if hasattr(btn, 'text') and btn.text:
                for emoji in config.SEED_EMOJIS:
                    if emoji in btn.text:
                        if await click_safe(self.client, grid, idx, delay=config.FIELD_CLICK_DELAY):
                            collected += 1
                        break

        logger.info(f"[{self.name}] 🌱 Собрано: {collected}")

        # Ждём результат с временем
        wait_time = None
        start = time.time()
        while time.time() - start < config.FIELD_TIMEOUT:
            try:
                m = await self.client.get_messages(self.chat_id, ids=msg_id)
                if m and m.text and "собрали семена" in m.text.lower():
                    pattern = r'через:\s*(\d+):(\d+)'
                    matches = re.findall(pattern, m.text)
                    if matches:
                        wait_time = int(matches[0][0]) * 60 + int(matches[0][1]) + 2  # +2 сек запас
                    break
            except:
                pass
            await asyncio.sleep(1)

        if wait_time:
            logger.info(f"[{self.name}] ⏱️ Ждём {wait_time} сек")
            await asyncio.sleep(wait_time)
        else:
            await asyncio.sleep(config.FIELD_INTERVAL)

        return True

    async def loop(self):
        self.stats['start_time'] = time.time()
        logger.info(f"[{self.name}] 🚀 Запущен")
        while self.running:
            try:
                self.stats['cycles'] += 1
                logger.info(f"[{self.name}] 📊 Цикл #{self.stats['cycles']}")
                start = time.time()
                ok = await self.cycle()
                if ok:
                    self.stats['success'] += 1
                else:
                    self.stats['fail'] += 1
                logger.info(f"[{self.name}] ⏱️ {int(time.time() - start)}сек")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.name}] ❌ {e}")
                await asyncio.sleep(60)

    async def start(self):
        if self.running:
            return False
        self.running = True
        self.task = asyncio.create_task(self.loop())
        return True

    async def stop(self):
        if not self.running:
            return False
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except:
                pass
        return True

    def get_status(self) -> dict:
        uptime = "0м"
        if self.stats['start_time']:
            m = int((time.time() - self.stats['start_time']) / 60)
            uptime = f"{m}мин"
        return {'name': self.name, 'running': self.running, 'cycles': self.stats['cycles'],
                'uptime': uptime, 'success': self.stats['success'], 'fail': self.stats['fail']}


# =============================================================================
# 🌱  МОДУЛЬ: ГРЯДКИ
# =============================================================================

class GardenModule:
    def __init__(self, client, my_id):
        self.name = "🌱 ГРЯДКИ"
        self.chat_id = config.PRIVATE_CHAT_ID
        self.client = client
        self.my_id = my_id
        self.running = False
        self.task = None
        self.stats = {'cycles': 0, 'start_time': None, 'success': 0, 'fail': 0}
        self.garden_msg: Optional[Message] = None
        self.ranch_id: Optional[int] = None
        logger.info(f"[{self.name}] Инициализирован")

    def _get_bed_action(self, text: str) -> str:
        if not text:
            return 'skip'
        if text.strip() == '' or text == '⠀' or text in config.BED_STATES['empty']:
            return 'plant'
        for s in config.BED_STATES['ready']:
            if s in text:
                return 'harvest'
        for s in config.BED_STATES['water']:
            if s in text:
                return 'water'
        return 'skip'

    def _verify(self, old: str, new: str, action: str) -> bool:
        if action == 'plant':
            if (old.strip() == '' or old == '⠀') and (new.strip() != '' and new != '⠀'):
                return True
            return any(e in new for e in config.PLANT_EMOJIS)
        elif action == 'water':
            return '💧' in old and '💧' not in new
        elif action == 'harvest':
            return '🌾' in old and '🌾' not in new
        return False

    async def _navigate(self) -> bool:
        msg = await self.client.send_message(self.chat_id, "Ранчо")
        await asyncio.sleep(1)

        async for menu in self.client.iter_messages(self.chat_id, limit=10):
            if menu.sender_id == self.my_id:
                continue
            if menu.reply_markup and 'Грядки' in str(menu.reply_markup):
                self.ranch_id = menu.id
                buttons = [btn for row in menu.buttons for btn in row]
                for idx, btn in enumerate(buttons):
                    if hasattr(btn, 'text') and 'Грядки' in btn.text:
                        await click_safe(self.client, menu, idx, delay=2)
                        break
                await asyncio.sleep(1.5)

                async for gm in self.client.iter_messages(self.chat_id, limit=10):
                    if gm.sender_id == self.my_id:
                        continue
                    if gm.text and 'грядк' in gm.text.lower():
                        self.garden_msg = gm
                        return True
                break
        return False

    async def _refresh(self):
        await asyncio.sleep(1)
        if not self.ranch_id:
            return
        async for m in self.client.iter_messages(self.chat_id, limit=10):
            if m.sender_id == self.my_id:
                continue
            if (m.id == self.ranch_id or m.id > self.ranch_id) and m.text and 'грядк' in m.text.lower():
                self.garden_msg = m
                return

    def _get_beds(self) -> List[str]:
        if not self.garden_msg or not self.garden_msg.reply_markup:
            return []
        beds = []
        for row in self.garden_msg.buttons:
            for btn in row:
                if hasattr(btn, 'text'):
                    beds.append(btn.text)
        return beds[:16]

    async def _process(self, idx: int, action: str) -> bool:
        beds = self._get_beds()
        if idx >= len(beds):
            return False
        old = beds[idx]

        await click_safe(self.client, self.garden_msg, idx, delay=config.CLICK_DELAY)
        await handle_ok_alert(self.client, self.chat_id, self.my_id)

        await self._refresh()
        new_beds = self._get_beds()
        if idx < len(new_beds):
            new = new_beds[idx]
            if self._verify(old, new, action):
                logger.info(f"[{self.name}] ✅ #{idx}: '{old}' → '{new}'")
                return True
        return False

    async def cycle(self) -> bool:
        logger.info(f"[{self.name}] Начинаем цикл")

        if not await self._navigate():
            return False

        beds = self._get_beds()
        if len(beds) < 16:
            return False

        stats = {'p': 0, 'w': 0, 'h': 0}

        for i in range(16):
            for attempt in range(3):
                beds = self._get_beds()
                if i >= len(beds):
                    break
                action = self._get_bed_action(beds[i])
                if action == 'skip':
                    break
                ok = await self._process(i, action)
                if ok:
                    if action == 'plant':
                        stats['p'] += 1
                    elif action == 'water':
                        stats['w'] += 1
                    elif action == 'harvest':
                        stats['h'] += 1
                    await self._refresh()
                    continue
                break
            await asyncio.sleep(0.5)

        logger.info(f"[{self.name}] ✅ 🌱{stats['p']} 💧{stats['w']} 🌾{stats['h']}")
        return True

    async def loop(self):
        self.stats['start_time'] = time.time()
        logger.info(f"[{self.name}] 🚀 Запущен")
        while self.running:
            try:
                self.stats['cycles'] += 1
                logger.info(f"[{self.name}] 📊 Цикл #{self.stats['cycles']}")
                start = time.time()
                ok = await self.cycle()
                if ok:
                    self.stats['success'] += 1
                else:
                    self.stats['fail'] += 1
                logger.info(f"[{self.name}] ⏱️ {int(time.time() - start)}сек")
                await asyncio.sleep(config.GARDEN_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.name}] ❌ {e}")
                await asyncio.sleep(60)

    async def start(self):
        if self.running:
            return False
        self.running = True
        self.task = asyncio.create_task(self.loop())
        return True

    async def stop(self):
        if not self.running:
            return False
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except:
                pass
        return True

    def get_status(self) -> dict:
        uptime = "0м"
        if self.stats['start_time']:
            m = int((time.time() - self.stats['start_time']) / 60)
            uptime = f"{m}мин"
        return {'name': self.name, 'running': self.running, 'cycles': self.stats['cycles'],
                'uptime': uptime, 'success': self.stats['success'], 'fail': self.stats['fail']}


# =============================================================================
# 🏁  МОДУЛЬ: ГОНКИ (с заправкой)
# =============================================================================

class RaceModule:
    def __init__(self, client, my_id):
        self.name = "🏁 ГОНКИ"
        self.chat_id = config.GROUP_CHAT_ID
        self.client = client
        self.my_id = my_id
        self.running = False
        self.task = None
        self.stats = {'cycles': 0, 'start_time': None, 'success': 0, 'fail': 0, 'refuels': 0}
        logger.info(f"[{self.name}] Инициализирован")

    def _get_target(self, text: str) -> Optional[str]:
        if not text:
            return None
        t = normalize_text(text).lower()
        if 'красн' in t:
            return config.RACE_BUTTONS['red']
        elif 'жёлт' in t or 'желт' in t:
            return config.RACE_BUTTONS['yellow']
        elif 'зелён' in t or 'зелен' in t:
            return config.RACE_BUTTONS['green']
        return None

    def _needs_refuel(self, text: str) -> bool:
        """Проверяет, нужно ли заправить машину"""
        if not text:
            return False
        t = text.lower()
        return "заправьте свой автомобиль" in t or "топливо: 0%" in t

    async def _handle_refuel(self) -> bool:
        """Обработка заправки машины"""
        logger.info(f"[{self.name}] ⛽️ Обнаружена необходимость заправки!")

        # 1. Находим сообщение с кнопкой "Машина" (🚘)
        car_msg = None
        for _ in range(config.RACE_TIMEOUT):
            async for msg in self.client.iter_messages(self.chat_id, limit=10):
                if msg.sender_id == self.my_id:
                    continue
                if msg.text and "заправьте свой автомобиль" in msg.text.lower():
                    car_msg = msg
                    break
            if car_msg:
                break
            await asyncio.sleep(1)

        if not car_msg:
            logger.warning(f"[{self.name}] Сообщение о заправке не найдено")
            return False

        # 2. Нажимаем кнопку "Машина" (🚘)
        buttons = [btn for row in car_msg.buttons for btn in row]
        clicked = False
        for idx, btn in enumerate(buttons):
            if hasattr(btn, 'text') and btn.text and "🚘" in btn.text:
                await click_safe(self.client, car_msg, idx, delay=2)
                clicked = True
                break

        if not clicked:
            logger.warning(f"[{self.name}] Кнопка 'Машина' не найдена")
            return False

        logger.info(f"[{self.name}] Нажата кнопка 'Машина', ожидаем меню...")
        await asyncio.sleep(2)

        # 3. Ждем сообщение с информацией о машине
        car_info = None
        for _ in range(config.RACE_TIMEOUT):
            async for msg in self.client.iter_messages(self.chat_id, limit=10):
                if msg.sender_id == self.my_id:
                    continue
                if msg.text and "информация о вашей машине" in msg.text.lower():
                    car_info = msg
                    break
            if car_info:
                break
            await asyncio.sleep(1)

        if not car_info:
            logger.warning(f"[{self.name}] Меню машины не получено")
            return False

        # 4. Нажимаем кнопку "Заправить" (⛽️)
        buttons = [btn for row in car_info.buttons for btn in row]
        clicked = False
        for idx, btn in enumerate(buttons):
            if hasattr(btn, 'text') and btn.text and "⛽️" in btn.text:
                await click_safe(self.client, car_info, idx, delay=2)
                clicked = True
                break

        if not clicked:
            logger.warning(f"[{self.name}] Кнопка 'Заправить' не найдена")
            return False

        logger.info(f"[{self.name}] Нажата кнопка 'Заправить', ожидаем подтверждения...")
        await asyncio.sleep(2)

        # 5. Нажимаем кнопку "ОК" на всплывающем окне
        ok_clicked = await handle_ok_alert(self.client, self.chat_id, self.my_id, timeout=10)

        if ok_clicked:
            self.stats['refuels'] += 1
            logger.info(f"[{self.name}] ⛽️ Заправка завершена! (Всего: {self.stats['refuels']})")
            return True
        else:
            logger.warning(f"[{self.name}] Не удалось подтвердить заправку")
            return False

    async def cycle(self) -> bool:
        logger.info(f"[{self.name}] Начинаем гонку")

        msg = await self.client.send_message(self.chat_id, "Гонка")
        await asyncio.sleep(1)

        btn_msg = await wait_for_message(self.client, self.chat_id, self.my_id,
                                         after_id=msg.id, has_buttons=True,
                                         timeout=config.RACE_TIMEOUT)
        if not btn_msg:
            return False

        # Проверяем, нужно ли заправиться
        if self._needs_refuel(btn_msg.text):
            logger.info(f"[{self.name}] ⛽️ Требуется заправка!")
            refuel_ok = await self._handle_refuel()
            if refuel_ok:
                # После заправки повторяем цикл
                return True
            else:
                logger.warning(f"[{self.name}] Заправка не удалась")
                return False

        target = self._get_target(btn_msg.text)
        if not target:
            logger.warning(f"[{self.name}] Не определён цвет")
            return False

        # Нажать кнопку с эмодзи
        buttons = [btn for row in btn_msg.buttons for btn in row]
        for idx, btn in enumerate(buttons):
            if hasattr(btn, 'text') and btn.text and target in btn.text:
                await click_safe(self.client, btn_msg, idx, delay=1)
                break

        # Ждём финиш
        start = time.time()
        while time.time() - start < 60:
            async for m in self.client.iter_messages(self.chat_id, limit=20):
                if m.id <= btn_msg.id or m.sender_id == self.my_id:
                    continue
                if m.text:
                    ct = normalize_text(m.text).lower()
                    if any(p in ct for p in config.RACE_FINISH_PHRASES):
                        logger.info(f"[{self.name}] 🏁 Финиш!")
                        return True
            await asyncio.sleep(1)
        return True

    async def loop(self):
        self.stats['start_time'] = time.time()
        logger.info(f"[{self.name}] 🚀 Запущен")
        while self.running:
            try:
                self.stats['cycles'] += 1
                logger.info(f"[{self.name}] 📊 Цикл #{self.stats['cycles']}")
                start = time.time()
                ok = await self.cycle()
                if ok:
                    self.stats['success'] += 1
                else:
                    self.stats['fail'] += 1
                logger.info(f"[{self.name}] ⏱️ {int(time.time() - start)}сек")
                await asyncio.sleep(config.RACE_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.name}] ❌ {e}")
                await asyncio.sleep(60)

    async def start(self):
        if self.running:
            return False
        self.running = True
        self.task = asyncio.create_task(self.loop())
        return True

    async def stop(self):
        if not self.running:
            return False
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except:
                pass
        return True

    def get_status(self) -> dict:
        uptime = "0м"
        if self.stats['start_time']:
            m = int((time.time() - self.stats['start_time']) / 60)
            uptime = f"{m}мин"
        return {
            'name': self.name,
            'running': self.running,
            'cycles': self.stats['cycles'],
            'uptime': uptime,
            'success': self.stats['success'],
            'fail': self.stats['fail'],
            'refuels': self.stats.get('refuels', 0)
        }


# =============================================================================
# 👤 КЛАСС ДЛЯ ОТДЕЛЬНОГО АККАУНТА
# =============================================================================

class UnifiedAccount:
    """Класс для одного аккаунта со всеми модулями"""

    def __init__(self, account_config: dict):
        self.name = account_config['name']
        self.phone = account_config['phone']
        self.api_id = account_config['api_id']
        self.api_hash = account_config['api_hash']
        self.enabled = account_config['enabled']

        self.client = None
        self.my_id = None
        self.modules: Dict[str, object] = {}
        self.start_time = None

    async def start_client(self):
        """Запуск клиента и авторизация"""
        session_name = f"{SESSION_DIR}/account_{self.phone.replace('+', '')}"
        self.client = TelegramClient(
            session_name,
            self.api_id,
            self.api_hash,
            device_model="Python Universal Bot",
            system_version="3.0"
        )

        await self.client.start(phone=self.phone)
        logger.info(f"[{self.name}] ✅ Авторизован")

        me = await self.client.get_me()
        self.my_id = me.id
        logger.info(f"[{self.name}] 👤 {me.first_name} (@{me.username})")

        self._init_modules()

    def _init_modules(self):
        """Инициализация модулей для аккаунта"""
        if config.SHAFT_ENABLED:
            self.modules['shaft'] = ShaftModule(self.client, self.my_id)
        if config.FISHING_ENABLED:
            self.modules['fishing'] = FishingModule(self.client, self.my_id)
        if config.WORK_ENABLED:
            self.modules['work'] = WorkModule(self.client, self.my_id)
        if config.FIELD_ENABLED:
            self.modules['field'] = FieldModule(self.client, self.my_id)
        if config.GARDEN_ENABLED:
            self.modules['garden'] = GardenModule(self.client, self.my_id)
        if config.RACE_ENABLED:
            self.modules['race'] = RaceModule(self.client, self.my_id)
        logger.info(f"[{self.name}] 📦 Модулей: {len(self.modules)}")

    async def setup_handlers(self):
        """Настройка обработчиков команд для аккаунта"""

        @self.client.on(events.NewMessage)
        async def handler(event):
            if event.chat_id not in [config.GROUP_CHAT_ID, config.PRIVATE_CHAT_ID]:
                return

            # Проверка капчи
            if event.message.photo and event.message.reply_markup:
                logger.info(f"[{self.name}] 🔍 Найдена капча! Запускаем распознавание...")
                result = await captcha_solver.solve(self.client, event.message, event.chat_id, self.my_id)
                if result:
                    logger.info(f"[{self.name}] ✅ Капча решена! Нажато: {result}")
                    return
                else:
                    logger.warning(f"[{self.name}] ❌ Не удалось решить капчу")
                    return

            # Обработка команд
            text = (event.message.text or "").lower().strip()
            if not text:
                return

            # Шахта
            if text in config.COMMANDS['shaft_start']:
                ok = await self.modules.get('shaft', type('', (), {
                    'start': lambda s: False})()).start() if 'shaft' in self.modules else False
                await event.reply("✅ Шахта запущена!" if ok else "⚠️ Не найдена!")
            elif text in config.COMMANDS['shaft_stop']:
                ok = await self.modules.get('shaft', type('', (), {
                    'stop': lambda s: False})()).stop() if 'shaft' in self.modules else False
                await event.reply("⏹️ Остановлена!" if ok else "⚠️ Не работает!")

            # Рыбалка
            elif text in config.COMMANDS['fishing_start']:
                ok = await self.modules.get('fishing', type('', (), {
                    'start': lambda s: False})()).start() if 'fishing' in self.modules else False
                await event.reply("🎣 Рыбалка запущена!" if ok else "⚠️ Не найдена!")
            elif text in config.COMMANDS['fishing_stop']:
                ok = await self.modules.get('fishing', type('', (), {
                    'stop': lambda s: False})()).stop() if 'fishing' in self.modules else False
                await event.reply("⏹️ Остановлена!" if ok else "⚠️ Не работает!")

            # Работа
            elif text in config.COMMANDS['work_start']:
                ok = await self.modules.get('work', type('', (), {
                    'start': lambda s: False})()).start() if 'work' in self.modules else False
                await event.reply("💼 Работа запущена!" if ok else "⚠️ Не найдена!")
            elif text in config.COMMANDS['work_stop']:
                ok = await self.modules.get('work', type('', (), {
                    'stop': lambda s: False})()).stop() if 'work' in self.modules else False
                await event.reply("⏹️ Остановлена!" if ok else "⚠️ Не работает!")

            # Поле
            elif text in config.COMMANDS['field_start']:
                ok = await self.modules.get('field', type('', (), {
                    'start': lambda s: False})()).start() if 'field' in self.modules else False
                await event.reply("🌾 Поле запущено!" if ok else "⚠️ Не найдено!")
            elif text in config.COMMANDS['field_stop']:
                ok = await self.modules.get('field', type('', (), {
                    'stop': lambda s: False})()).stop() if 'field' in self.modules else False
                await event.reply("⏹️ Остановлено!" if ok else "⚠️ Не работает!")

            # Грядки
            elif text in config.COMMANDS['garden_start']:
                ok = await self.modules.get('garden', type('', (), {
                    'start': lambda s: False})()).start() if 'garden' in self.modules else False
                await event.reply("🌱 Грядки запущены!" if ok else "⚠️ Не найдены!")
            elif text in config.COMMANDS['garden_stop']:
                ok = await self.modules.get('garden', type('', (), {
                    'stop': lambda s: False})()).stop() if 'garden' in self.modules else False
                await event.reply("⏹️ Остановлены!" if ok else "⚠️ Не работают!")

            # Гонки
            elif text in config.COMMANDS['race_start']:
                ok = await self.modules.get('race', type('', (), {
                    'start': lambda s: False})()).start() if 'race' in self.modules else False
                await event.reply("🏁 Гонки запущены!" if ok else "⚠️ Не найдены!")
            elif text in config.COMMANDS['race_stop']:
                ok = await self.modules.get('race', type('', (), {
                    'stop': lambda s: False})()).stop() if 'race' in self.modules else False
                await event.reply("⏹️ Остановлены!" if ok else "⚠️ Не идут!")

            # Статус
            elif text in config.COMMANDS['status']:
                status_text = await self.get_status_text()
                await event.reply(status_text)

    async def get_status_text(self) -> str:
        """Получить статус аккаунта"""
        lines = [f"📊 СТАТУС {self.name}", "=" * 40]
        info = {
            'shaft': ('⛏️ Шахта', 'Группа'),
            'fishing': ('🎣 Рыбалка', 'Группа'),
            'work': ('💼 Работа', 'Группа'),
            'field': ('🌾 Поле', 'ЛС'),
            'garden': ('🌱 Грядки', 'ЛС'),
            'race': ('🏁 Гонки', 'Группа'),
        }
        for key in info:
            if key in self.modules:
                s = self.modules[key].get_status()
                name, chat = info[key]
                icon = "✅" if s['running'] else "⏹️"
                lines.append(f"{icon} {name} ({chat})")
                lines.append(f"   ├─ Циклов: {s['cycles']}")
                lines.append(f"   ├─ Время: {s['uptime']}")
                lines.append(f"   ├─ Успех: {s['success']}")
                lines.append(f"   └─ Ошибки: {s['fail']}")
                lines.append("")
            else:
                name, chat = info.get(key, (key, '?'))
                lines.append(f"⏸️ {name} ({chat}) — отключен")
                lines.append("")
        if self.start_time:
            m = int((time.time() - self.start_time) / 60)
            lines.append(f"⏱️ Бот работает: {m} минут")
        return "\n".join(lines)

    async def run(self):
        """Запуск аккаунта"""
        try:
            await self.start_client()
            await self.setup_handlers()
            self.start_time = time.time()

            logger.info(f"[{self.name}] 🤖 Бот готов!")
            logger.info(f"[{self.name}] 💬 Группа: {config.GROUP_CHAT_ID}")
            logger.info(f"[{self.name}] 💬 ЛС: {config.PRIVATE_CHAT_ID}")

            await self.client.run_until_disconnected()
        except KeyboardInterrupt:
            logger.info(f"[{self.name}] ⏹️ Остановка")
            for m in self.modules.values():
                await m.stop()
        except Exception as e:
            logger.error(f"[{self.name}] ❌ Ошибка: {e}")
        finally:
            await self.client.disconnect()


# =============================================================================
# 🤖 ГЛАВНЫЙ КЛАСС БОТА (управление аккаунтами)
# =============================================================================

class UniversalBot:
    def __init__(self):
        self.accounts: List[UnifiedAccount] = []
        self.start_time = None
        logger.info("🤖 Универсальный бот инициализирован")

    async def start_all_accounts(self):
        """Запуск всех аккаунтов из конфига"""
        for acc_config in config.ACCOUNTS:
            if acc_config.get('enabled', True):
                account = UnifiedAccount(acc_config)
                self.accounts.append(account)
                await account.start_client()
                await account.setup_handlers()
                logger.info(f"✅ Аккаунт {account.name} запущен")

        logger.info(f"📦 Всего аккаунтов: {len(self.accounts)}")

    async def run(self):
        try:
            await self.start_all_accounts()
            self.start_time = time.time()

            logger.info("=" * 50)
            logger.info("🤖 УНИВЕРСАЛЬНЫЙ БОТ ГОТОВ!")
            logger.info(f"👤 Аккаунтов запущено: {len(self.accounts)}")
            logger.info(f"💬 Группа: {config.GROUP_CHAT_ID}")
            logger.info(f"💬 ЛС: {config.PRIVATE_CHAT_ID}")
            logger.info("")
            logger.info("📋 Команды для каждого аккаунта:")
            logger.info("  ⛏️  шах /shaft     - шахта")
            logger.info("  🎣  рыб /fishing   - рыбалка")
            logger.info("  💼  раб /work      - работа")
            logger.info("  🌾  поле /field    - поиск семян")
            logger.info("  🌱  гряд /garden   - грядки")
            logger.info("  🏁  гон /race      - гонки")
            logger.info("  📊  стат /stat     - статус")
            logger.info("=" * 50)

            # Запускаем всех клиентов параллельно
            await asyncio.gather(*[account.client.run_until_disconnected() for account in self.accounts])

        except KeyboardInterrupt:
            logger.info("⏹️ Остановка всех аккаунтов")
            for account in self.accounts:
                for m in account.modules.values():
                    await m.stop()
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}", exc_info=True)
        finally:
            for account in self.accounts:
                await account.client.disconnect()
            logger.info("Все боты остановлены")


def main():
    bot = UniversalBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Остановлено")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()