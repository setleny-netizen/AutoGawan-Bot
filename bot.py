import random
import asyncio
import time
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Импорт данных о рыбах из отдельного файла
from fish_data import FISH_DATA, SCROLL_CHANCE

# ==================== ЦВЕТА ДЛЯ ЛОГОВ ====================
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = "8742043015:AAF4EBWameQbc_qTZGlU347-A-R7shrK5GI"
SAVE_FILE = "fishing_data.json"

# Глобальный лимит свитков
MAX_TOTAL_SCROLLS = 25
total_scrolls_dropped = 0  # сколько свитков уже выпало за всё время

# ==================== УРОВНИ (опыт до следующего уровня) ====================
LEVEL_EXP_REQUIREMENTS = {1: 12, 2: 24, 3: 36, 4: 48, 5: 60}
for i in range(6, 151):
    LEVEL_EXP_REQUIREMENTS[i] = LEVEL_EXP_REQUIREMENTS[i - 1] + 12

# ==================== ХРАНИЛИЩЕ ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ ====================
user_data: Dict[int, Dict[str, Any]] = {}

# ==================== ХРАНИЛИЩЕ КУЛДАУНОВ РЫБАЛКИ ====================
fishing_cooldowns: Dict[int, float] = {}

# ==================== НАЗВАНИЯ И ОПИСАНИЯ УЛУЧШЕНИЙ ====================
UPGRADE_NAMES = {
    "rod": "Удилище",
    "line": "Леска",
    "float": "Поплавок",
    "hook": "Крючок",
    "reel": "Катушка"
}

UPGRADE_DESCRIPTIONS = {
    "rod": "Позволяет ловить более крупную рыбу.",
    "line": "Позволяет ловить более крупную рыбу.",
    "float": "Уменьшает время ожидания поклёвки.",
    "hook": "Уменьшает время ожидания поклёвки.",
    "reel": "Увеличивает время на подсечку рыбы."
}


def get_upgrade_emoji(upgrade_type: str) -> str:
    """Возвращает эмодзи для типа улучшения"""
    emojis = {
        "rod": "🎣",
        "line": "📏",
        "float": "🎯",
        "hook": "🪝",
        "reel": "⚙️"
    }
    return emojis.get(upgrade_type, "🔧")


# ==================== ФУНКЦИЯ ЛОГИРОВАНИЯ ====================
def log_event(event_type: str, user_id: int, user_name: str, details: str = "", color: str = RESET) -> None:
    """Выводит в консоль отформатированный лог события"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{timestamp}] [{event_type}] {user_name} (ID:{user_id}) | {details}{RESET}")


# ==================== СОХРАНЕНИЕ И ЗАГРУЗКА ДАННЫХ ====================
def save_data() -> None:
    """Сохраняет user_data и глобальные переменные в JSON файл"""
    global total_scrolls_dropped
    try:
        to_save = {
            "users": {str(k): v for k, v in user_data.items()},
            "total_scrolls_dropped": total_scrolls_dropped
        }
        with open(SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(to_save, f, ensure_ascii=False, indent=2)
        log_event("SAVE", 0, "SYSTEM",
                  f"Данные сохранены ({len(user_data)} игроков, свитков: {total_scrolls_dropped}/{MAX_TOTAL_SCROLLS})",
                  CYAN)
    except Exception as e:
        print(f"Ошибка сохранения: {e}")


def load_data() -> None:
    """Загружает user_data и глобальные переменные из JSON файла"""
    global user_data, total_scrolls_dropped
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # Загружаем пользователей
                if "users" in loaded:
                    user_data = {int(k): v for k, v in loaded["users"].items()}
                else:
                    # Обратная совместимость со старым форматом
                    user_data = {int(k): v for k, v in loaded.items()}

                # Миграция старых данных — добавляем отсутствующие поля
                for uid, data in user_data.items():
                    if "nets" not in data:
                        data["nets"] = {
                            "active_nets": [],
                            "max_nets": 3,
                            "used_nets": 0,
                            "net_duration": 1200
                        }
                    if "biggest_catch" not in data:
                        data["biggest_catch"] = {
                            "name": "",
                            "weight": 0.0,
                            "rarity": "",
                            "emoji": ""
                        }
                    if "fish_records" not in data:
                        data["fish_records"] = {}
                    if "scrolls" not in data:
                        data["scrolls"] = 0
                    if "upgrades" not in data:
                        data["upgrades"] = {
                            "rod": 0, "line": 0, "float": 0, "hook": 0, "reel": 0
                        }
                    if "unique_fish_caught" not in data:
                        data["unique_fish_caught"] = []

                # Загружаем глобальный счётчик свитков
                total_scrolls_dropped = loaded.get("total_scrolls_dropped", 0)
            log_event("LOAD", 0, "SYSTEM",
                      f"Данные загружены ({len(user_data)} игроков, свитков: {total_scrolls_dropped}/{MAX_TOTAL_SCROLLS})",
                      CYAN)
        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            user_data = {}
            total_scrolls_dropped = 0
    else:
        user_data = {}
        total_scrolls_dropped = 0
        log_event("LOAD", 0, "SYSTEM", "Файл сохранения не найден, создан новый", CYAN)


def init_user(user_id: int, first_name: str) -> None:
    """Инициализация нового пользователя"""
    if user_id not in user_data:
        game_id = random.randint(100000, 999999)
        user_data[user_id] = {
            "name": first_name,
            "game_id": game_id,
            "reg_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "level": 1,
            "exp": 0,
            "balance": 0.0,
            "total_fish_caught": 0,
            "inventory": [],
            "upgrades": {
                "rod": 0,
                "line": 0,
                "float": 0,
                "hook": 0,
                "reel": 0,
            },
            "scrolls": 0,
            "fish_records": {},
            "biggest_catch": {
                "name": "",
                "weight": 0.0,
                "rarity": "",
                "emoji": ""
            },
            "nets": {
                "active_nets": [],
                "max_nets": 3,
                "used_nets": 0,
                "net_duration": 1200
            },
            "unique_fish_caught": []
        }
        log_event("NEW_USER", user_id, first_name, f"Зарегистрирован, GameID: {game_id}", GREEN)
        save_data()


def get_level_exp(user_id: int) -> Tuple[int, int, int]:
    user = user_data[user_id]
    level = user["level"]
    exp = user["exp"]
    exp_needed = LEVEL_EXP_REQUIREMENTS.get(level, 12 * level)
    return level, exp, exp_needed


async def add_exp(user_id: int, amount: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = user_data[user_id]
    old_level = user["level"]
    user["exp"] += amount
    user["total_fish_caught"] += 1

    level, exp, exp_needed = get_level_exp(user_id)
    leveled_up = False

    while exp >= exp_needed:
        user["level"] += 1
        user["exp"] -= exp_needed
        level, exp, exp_needed = get_level_exp(user_id)
        leveled_up = True

    if leveled_up:
        log_event("LEVEL_UP", user_id, user["name"],
                  f"Уровень: {old_level} → {user['level']}, Опыт: {user['exp']}/{LEVEL_EXP_REQUIREMENTS.get(user['level'], 12 * user['level'])}",
                  CYAN)
        save_data()

        # Отправляем сообщение с картинкой о повышении уровня
        try:
            with open("img/lvlup.jpg", "rb") as photo:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=photo,
                    caption=f"🎉 Поздравляем! Вы достигли {user['level']} уровня! 🎉"
                )
        except FileNotFoundError:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 Поздравляем! Вы достигли {user['level']} уровня! 🎉"
            )

    return leveled_up


def get_max_weight(user_id: int) -> float:
    user = user_data[user_id]
    rod_level = user["upgrades"]["rod"]
    line_level = user["upgrades"]["line"]
    total_power = rod_level + line_level
    return 5 * (2.88 ** total_power)


def get_bite_time_range(user_id: int) -> Tuple[float, float]:
    user = user_data[user_id]
    float_level = user["upgrades"]["float"]
    hook_level = user["upgrades"]["hook"]
    total_float_power = float_level + hook_level
    multiplier = 1.1487 ** total_float_power
    min_time = 30 / multiplier
    max_time = 45 / multiplier
    return min_time, max_time


def get_net_bite_time(user_id: int) -> float:
    """Возвращает интервал появления рыбы для сетей (30-60 сек) с учётом улучшений"""
    min_time, max_time = get_bite_time_range(user_id)
    return random.uniform(min_time, max_time)


def get_reaction_time(user_id: int) -> float:
    user = user_data[user_id]
    reel_level = user["upgrades"]["reel"]
    return 2 * (1.1487 ** reel_level)


def get_available_fish(user_id: int, check_max_weight: bool = True) -> List[Dict]:
    """Возвращает список доступных рыб. Если check_max_weight=False, возвращает всех рыб."""
    if not check_max_weight:
        return [fish.copy() for fish in FISH_DATA]

    max_weight = get_max_weight(user_id)
    available = []

    for fish in FISH_DATA:
        min_weight = fish["weight_range"][0]
        if min_weight <= max_weight:
            available.append(fish.copy())

    if not available:
        return [FISH_DATA[0].copy()]

    return available


def get_random_fish(user_id: int, check_max_weight: bool = True) -> Optional[Dict[str, Any]]:
    """Генерирует случайную рыбу. Если check_max_weight=False, не ограничивает по весу."""
    available_fish = get_available_fish(user_id, check_max_weight)
    total_chance = sum(fish["chance"] for fish in available_fish)
    rand = random.uniform(0, total_chance)
    cumulative = 0

    for fish in available_fish:
        cumulative += fish["chance"]
        if rand <= cumulative:
            weight = round(random.uniform(*fish["weight_range"]), 2)
            price_per_kg = round(random.uniform(*fish["price_range"]), 2)
            total_price = round(weight * price_per_kg, 2)

            return {
                "emoji": fish["emoji"],
                "name": fish["name"],
                "weight": weight,
                "price_per_kg": price_per_kg,
                "total_price": total_price,
                "rarity": fish["rarity"],
            }

    return {
        "emoji": "🐟",
        "name": "Сарган",
        "weight": 1.0,
        "price_per_kg": 5.0,
        "total_price": 5.0,
        "rarity": "Обычная"
    }


def format_number(num: float) -> str:
    parts = f"{num:,.2f}".replace(",", "'").split(".")
    if len(parts) > 1:
        if parts[1] == "00":
            return parts[0]
        return f"{parts[0]}.{parts[1]}"
    return parts[0]


def are_all_upgrades_maxed(user_id: int) -> bool:
    user = user_data[user_id]
    upgrades = user["upgrades"]
    return (upgrades["rod"] == 5 and upgrades["line"] == 5 and
            upgrades["float"] == 5 and upgrades["hook"] == 5 and
            upgrades["reel"] == 5)


# ==================== КЛАВИАТУРЫ ====================
def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("🎣 Меню рыбалки")],
        [KeyboardButton("👤 Профиль")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_fishing_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    user = user_data[user_id]
    level = user["level"]

    # Кнопка рыбалки сетями (заблокирована до 7 уровня)
    if level >= 7:
        net_button = InlineKeyboardButton("🕸 Рыбачить сетями", callback_data="start_net_fishing")
    else:
        net_button = InlineKeyboardButton("🔒 Рыбачить сетями (7 ур.)", callback_data="net_locked")

    keyboard = [
        [InlineKeyboardButton("🎣 Рыбачить", callback_data="start_fishing_new")],
        [net_button],
        [InlineKeyboardButton("🪝 Улучшения", callback_data="show_upgrades"),
         InlineKeyboardButton("📦 Склад", callback_data="show_inventory")],
        [InlineKeyboardButton("📖 Книга рыбака", callback_data="fish_album")],
    ]

    return InlineKeyboardMarkup(keyboard)


def get_inventory_keyboard(is_empty: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура для склада"""
    if is_empty:
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_fishing_menu")]]
    else:
        keyboard = [
            [InlineKeyboardButton("💰 Продать рыбу", callback_data="sell_fish")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_fishing_menu")],
        ]
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура только с кнопкой Назад"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_fishing_menu")]
    ])


def get_upgrades_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для главного меню улучшений (ведёт на информационные окна)"""
    user = user_data[user_id]
    upgrades = user["upgrades"]

    # Формируем текст для каждой кнопки с уровнем
    rod_text = f"🎣 Удилище ({upgrades['rod']}/5)" if upgrades['rod'] < 5 else "🎣 Удилище ✅"
    line_text = f"📏 Леска ({upgrades['line']}/5)" if upgrades['line'] < 5 else "📏 Леска ✅"
    float_text = f"🎯 Поплавок ({upgrades['float']}/5)" if upgrades['float'] < 5 else "🎯 Поплавок ✅"
    hook_text = f"🪝 Крючок ({upgrades['hook']}/5)" if upgrades['hook'] < 5 else "🪝 Крючок ✅"
    reel_text = f"⚙️ Катушка ({upgrades['reel']}/5)" if upgrades['reel'] < 5 else "⚙️ Катушка ✅"

    keyboard = [
        [InlineKeyboardButton(rod_text, callback_data="info_rod")],
        [InlineKeyboardButton(float_text, callback_data="info_float"),
         InlineKeyboardButton(reel_text, callback_data="info_reel")],
        [InlineKeyboardButton(hook_text, callback_data="info_hook"),
         InlineKeyboardButton(line_text, callback_data="info_line")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_fishing_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_upgrade_info_keyboard(upgrade_type: str) -> InlineKeyboardMarkup:
    """Клавиатура для информационного окна улучшения"""
    keyboard = [
        [InlineKeyboardButton("🔧 Улучшить", callback_data=f"upgrade_action_{upgrade_type}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="show_upgrades")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_catch_result_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для сообщения о поимке — только кнопка Рыбачить"""
    keyboard = [
        [InlineKeyboardButton("🎣 Рыбачить", callback_data="start_fishing_new")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_fail_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для сообщения о неудаче — только кнопка Рыбачить"""
    keyboard = [
        [InlineKeyboardButton("🎣 Рыбачить", callback_data="start_fishing_new")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_fish_details_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для возврата из деталей рыбы к списку"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад", callback_data="fish_album")]
    ])


def create_fishing_grid(fish_emoji: Optional[str] = None,
                        active_position: Optional[int] = None) -> InlineKeyboardMarkup:
    keyboard = []
    for i in range(5):
        row = []
        for j in range(5):
            pos = i * 5 + j
            if pos == active_position and fish_emoji:
                button_text = fish_emoji
            else:
                button_text = " "

            if pos == active_position and fish_emoji:
                callback_data = f"catch_{pos}"
            else:
                callback_data = f"miss_{pos}"

            row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)


def create_net_grid(active_positions: List[int]) -> InlineKeyboardMarkup:
    """Создаёт сетку 5x5 для рыбалки сетями"""
    keyboard = []
    for i in range(5):
        row = []
        for j in range(5):
            pos = i * 5 + j
            if pos in active_positions:
                button_text = "🕸"
                callback_data = f"net_check_{pos}"
            else:
                button_text = " "
                callback_data = f"net_place_{pos}"

            row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        keyboard.append(row)

    # Добавляем кнопку "Назад" под сеткой
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_fishing_menu")])

    return InlineKeyboardMarkup(keyboard)


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def is_user_fishing(context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not context.user_data.get("fishing_message_id"):
        return False
    if context.user_data.get("fishing_ended", True):
        return False
    return True


def is_user_net_fishing(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет, активна ли рыбалка сетями"""
    if not context.user_data.get("net_message_id"):
        return False
    if context.user_data.get("net_fishing_ended", True):
        return False
    return True


def get_remaining_fishing_time(context: ContextTypes.DEFAULT_TYPE) -> int:
    fishing_start_time = context.user_data.get("fishing_start_time")
    if not fishing_start_time:
        return 0

    fish_delay = context.user_data.get("fish_delay", 30)
    reaction_time = context.user_data.get("reaction_time", 2)
    total_duration = fish_delay + reaction_time
    end_time = fishing_start_time + total_duration
    remaining = max(0, end_time - time.time())
    return int(remaining)


def is_fishing_on_cooldown(user_id: int) -> Tuple[bool, int]:
    if user_id in fishing_cooldowns:
        remaining = fishing_cooldowns[user_id] - time.time()
        if remaining > 0:
            return True, int(remaining)
        else:
            del fishing_cooldowns[user_id]
    return False, 0


def set_fishing_cooldown(user_id: int, seconds: int = 5) -> None:
    fishing_cooldowns[user_id] = time.time() + seconds


def reset_fishing_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    keys_to_clear = [
        "fishing_message_id",
        "fishing_chat_id",
        "fishing_ended",
        "fish_appeared",
        "active_position",
        "current_fish",
        "fishing_start_time",
        "fish_appear_time",
        "fish_delay",
        "reaction_time",
    ]
    for key in keys_to_clear:
        if key in context.user_data:
            del context.user_data[key]


def reset_net_fishing_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Сбрасывает состояние рыбалки сетями"""
    keys_to_clear = [
        "net_message_id",
        "net_chat_id",
        "net_fishing_ended",
        "net_fishing_active",
    ]
    for key in keys_to_clear:
        if key in context.user_data:
            del context.user_data[key]


def update_net_message(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Обновляет сообщение с сеткой и текстом"""
    if not context.user_data.get("net_message_id"):
        return

    user = user_data[user_id]
    nets = user["nets"]
    active_positions = [net["position"] for net in nets["active_nets"]]

    text = (
        f"🕸 {user['name']}, рыбалка сетями:\n"
        f"Доступно сетей: {nets['used_nets']}/{nets['max_nets']} забросов\n\n"
        f"🎯 Заброс сети ловит несколько рыб сразу.\n"
        f"🚩 Нажмите на пустую ячейку, чтобы установить сеть.\n"
        f"⏳ Нажмите на установленную сеть, чтобы узнать, сколько времени она еще будет собирать улов."
    )

    asyncio.create_task(context.bot.edit_message_text(
        chat_id=context.user_data["net_chat_id"],
        message_id=context.user_data["net_message_id"],
        text=text,
        reply_markup=create_net_grid(active_positions)
    ))


# ==================== ОБРАБОТЧИКИ КОМАНД ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    init_user(user.id, user.first_name)

    welcome_text = (
        f"🎣 Добро пожаловать, {user.first_name}!\n\n"
        f"Это игра «Рыбалка». Здесь ты можешь ловить рыбу, "
        f"продавать её, повышать уровень и улучшать снасти!\n\n"
        f"Используй кнопки ниже для навигации."
    )

    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "📖 **Помощь по игре «Рыбалка»**\n\n"
        "🎣 **Как играть:**\n"
        "• Нажми «Меню рыбалки» → «Рыбачить»\n"
        "• Жди появления эмодзи рыбы в сетке 5×5\n"
        "• Успей нажать на неё за отведённое время\n"
        "• Пойманная рыба попадёт на склад\n\n"
        "🕸 **Рыбалка сетями (доступна с 7 ур.):**\n"
        "• Установи сеть в пустую ячейку\n"
        "• Сеть работает 2 часа и ловит рыбу автоматически\n"
        "• Максимум 3 сети одновременно\n\n"
        "📖 **Книга рыбака:**\n"
        "• Смотри рекорды по пойманным рыбам\n"
        "• Отслеживай свой прогресс\n\n"
        "🪝 **Улучшения:**\n"
        "• Улучшай снасти за свитки\n"
        "• Удилище + Леска увеличивают макс. вес рыбы\n"
        "• Поплавок + Крючок ускоряют поклёвку\n"
        "• Катушка увеличивает время реакции\n\n"
        "💰 **Продажа:**\n"
        "• На складе нажми «Продать рыбу»\n\n"
        "⭐ **Уровни:**\n"
        "• 1 пойманная рыба = 1 опыт\n\n"
        "🔄 **Сброс:**\n"
        "• /reset — полностью сбросить прогресс\n\n"
        "Удачной рыбалки! 🌊"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Полный сброс прогресса игрока"""
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name

    # Удаляем данные пользователя
    if user_id in user_data:
        del user_data[user_id]

    # Инициализируем заново
    init_user(user_id, first_name)

    await update.message.reply_text(
        "🔄 Ваш прогресс был полностью сброшен!\n"
        "🎣 Теперь вы начинаете рыбалку с нуля.\n\n"
        "Используйте /start для начала игры.",
        reply_markup=get_main_keyboard()
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user = update.effective_user
    user_id = user.id

    init_user(user_id, user.first_name)

    if text == "🎣 Меню рыбалки":
        await show_fishing_menu(update, context)
    elif text == "👤 Профиль":
        await show_profile(update, context)


async def show_fishing_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = user_data[user_id]

    level, exp, exp_needed = get_level_exp(user_id)
    unique_count = len(user.get("unique_fish_caught", []))
    total_unique = len(FISH_DATA)

    # Базовый текст меню
    menu_text = (
        f"🎣 {user['name']} | Меню рыбалки:\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐️ Уровень рыбака: {level} ({exp}/{exp_needed})\n"
        f"🐟 Поймано всего рыбы: {user['total_fish_caught']} шт.\n"
        f"🌊 Уникальные виды: {unique_count} из {total_unique}\n"
    )

    # Добавляем строку со свитками только если не все улучшения на максимуме
    if not are_all_upgrades_maxed(user_id):
        menu_text += f"\n📜 Свиток улучшения: {user['scrolls']} шт.\n"

    menu_text += f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # Добавляем блок крупнейшего улова
    biggest = user.get("biggest_catch", {})
    if biggest and biggest.get("weight", 0) > 0:
        menu_text += (
            f"🏆 Крупнейший улов:\n"
            f"⠀{biggest['emoji']} {biggest['name']} ({biggest['weight']:.2f} кг., {biggest['rarity']})"
        )
    else:
        menu_text += "🏆 Крупнейший улов:\n⠀Пока нет улова"

    await update.message.reply_text(
        menu_text,
        reply_markup=get_fishing_menu_keyboard(user_id)
    )


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user = user_data[user_id]

    level, exp, exp_needed = get_level_exp(user_id)

    profile_text = (
        f"🧢 {user['name']}, ваш профиль:\n\n"
        f"🌟 Уровень рыбака: {level} ({exp}/{exp_needed})\n"
        f"💰 Баланс: {format_number(user['balance'])}$\n\n"
        f"🆔 Игровой ид: {user['game_id']}\n"
        f"📚 Дата регистрации: {user['reg_date']}"
    )

    await update.message.reply_text(profile_text)


# ==================== РЫБАЛКА СЕТЯМИ ====================
async def start_net_fishing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запускает рыбалку сетями"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = user_data[user_id]
    nets = user["nets"]

    # Проверяем, не активна ли уже рыбалка сетями
    if is_user_net_fishing(context):
        await query.answer("⚠️ Вы уже на рыбалке сетями!", show_alert=True)
        return

    # Проверяем, не активна ли обычная рыбалка
    if is_user_fishing(context):
        remaining_time = get_remaining_fishing_time(context)
        await query.answer(f"⚠️ Сначала завершите обычную рыбалку! Осталось: {remaining_time} сек.", show_alert=True)
        return

    active_positions = [net["position"] for net in nets["active_nets"]]

    text = (
        f"🕸 {user['name']}, рыбалка сетями:\n"
        f"Доступно сетей: {nets['used_nets']}/{nets['max_nets']} забросов\n\n"
        f"🎯 Заброс сети ловит несколько рыб сразу.\n"
        f"🚩 Нажмите на пустую ячейку, чтобы установить сеть.\n"
        f"⏳ Нажмите на установленную сеть, чтобы узнать, сколько времени она еще будет собирать улов."
    )

    message = await query.message.reply_text(
        text,
        reply_markup=create_net_grid(active_positions)
    )

    context.user_data["net_message_id"] = message.message_id
    context.user_data["net_chat_id"] = message.chat_id
    context.user_data["net_fishing_ended"] = False
    context.user_data["net_fishing_active"] = True

    # Запускаем фоновую задачу для появления рыбы
    asyncio.create_task(net_fishing_task(update, context))


async def net_fishing_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Фоновая задача для появления рыбы при рыбалке сетями"""
    user_id = update.effective_user.id
    user = user_data[user_id]

    while context.user_data.get("net_fishing_active", False):
        bite_time = get_net_bite_time(user_id)
        await asyncio.sleep(bite_time)

        if not context.user_data.get("net_fishing_active", False):
            break

        nets = user["nets"]
        if not nets["active_nets"]:
            continue

        # Генерируем рыбу в случайной позиции
        current_fish = get_random_fish(user_id, check_max_weight=False)
        position = random.randint(0, 24)

        # Проверяем, есть ли сеть в этой позиции
        for net in nets["active_nets"]:
            if net["position"] == position:
                # Добавляем рыбу в улов сети
                net["catches"].append(current_fish)
                log_event("NET_FISH", user_id, user["name"],
                          f"Рыба попалась в сеть: {current_fish['name']}, Вес: {current_fish['weight']:.2f} кг, Позиция: {position}",
                          BLUE)
                break


async def place_net(update: Update, context: ContextTypes.DEFAULT_TYPE, position: int) -> None:
    """Устанавливает сеть в указанную позицию"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = user_data[user_id]
    nets = user["nets"]

    # Проверяем лимит сетей
    if nets["used_nets"] >= nets["max_nets"]:
        await query.answer(f"❌ Достигнут лимит сетей ({nets['max_nets']})!", show_alert=True)
        return

    # Проверяем, нет ли уже сети в этой позиции
    for net in nets["active_nets"]:
        if net["position"] == position:
            await query.answer("❌ В этой ячейке уже установлена сеть!", show_alert=True)
            return

    # Устанавливаем сеть
    expire_time = time.time() + nets["net_duration"]
    nets["active_nets"].append({
        "position": position,
        "expire_time": expire_time,
        "catches": []
    })
    nets["used_nets"] += 1

    log_event("NET_PLACE", user_id, user["name"],
              f"Сеть установлена в позиции {position}, осталось сетей: {nets['used_nets']}/{nets['max_nets']}",
              BLUE)

    save_data()
    update_net_message(context, user_id)


async def check_net(update: Update, context: ContextTypes.DEFAULT_TYPE, position: int) -> None:
    """Проверка состояния сети"""
    query = update.callback_query
    user_id = update.effective_user.id
    user = user_data[user_id]

    # Ищем сеть на этой позиции
    net = None
    for n in user["nets"]["active_nets"]:
        if n["position"] == position:
            net = n
            break

    if not net:
        await query.answer("❌ Здесь нет сети!", show_alert=True)
        return

    current_time = time.time()
    expire_time = net["expire_time"]

    if current_time >= expire_time:
        # Время вышло — можно собрать улов
        await collect_net_catch(update, context, position, net)
    else:
        # Показываем оставшееся время
        remaining = int(expire_time - current_time)
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        seconds = remaining % 60

        if hours > 0:
            time_str = f"{hours} ч {minutes} мин"
        elif minutes > 0:
            time_str = f"{minutes} мин {seconds} сек"
        else:
            time_str = f"{seconds} сек"

        await query.answer(f"⏳ Сеть будет работать ещё {time_str}", show_alert=True)


async def collect_net_catch(update: Update, context: ContextTypes.DEFAULT_TYPE, position: int, net: Dict) -> None:
    """Собирает улов с сети"""
    query = update.callback_query

    user_id = update.effective_user.id
    user = user_data[user_id]
    nets = user["nets"]

    # Удаляем сеть
    nets["active_nets"] = [n for n in nets["active_nets"] if n["position"] != position]
    nets["used_nets"] -= 1

    catches = net.get("catches", [])

    if not catches:
        await query.answer("📦 Сеть пуста, рыба не попалась.", show_alert=True)
        save_data()
        update_net_message(context, user_id)
        return

    # Группируем улов
    fish_summary = {}
    total_weight = 0.0

    for fish in catches:
        user["inventory"].append(fish)
        user["total_fish_caught"] += 1

        key = (fish["emoji"], fish["name"])
        if key not in fish_summary:
            fish_summary[key] = {"count": 0}
        fish_summary[key]["count"] += 1
        total_weight += fish["weight"]

        # Обновляем книгу рыбака и крупнейший улов (без опыта)
        if "fish_records" not in user:
            user["fish_records"] = {}

        fish_name = fish["name"]
        if fish_name not in user["fish_records"]:
            user["fish_records"][fish_name] = {
                "emoji": fish["emoji"],
                "rarity": fish["rarity"],
                "catches": [],
                "total_weight": 0.0,
                "total_count": 0,
                "max_weight": 0.0,
                "max_weight_date": ""
            }

        record = user["fish_records"][fish_name]
        catch_date = datetime.now().strftime("%d.%m.%y %H:%M")
        record["catches"].append({
            "weight": fish["weight"],
            "date": catch_date
        })
        record["total_weight"] += fish["weight"]
        record["total_count"] += 1

        if fish["weight"] > record["max_weight"]:
            record["max_weight"] = fish["weight"]
            record["max_weight_date"] = catch_date

        # Обновляем крупнейший улов
        if "biggest_catch" not in user:
            user["biggest_catch"] = {"name": "", "weight": 0.0, "rarity": "", "emoji": ""}

        if fish["weight"] > user["biggest_catch"]["weight"]:
            user["biggest_catch"] = {
                "name": fish["name"],
                "weight": fish["weight"],
                "rarity": fish["rarity"],
                "emoji": fish["emoji"]
            }

    # Формируем текст результата
    result_text = (
        f"🕸 {user['name']}, вы собрали улов с сети!\n\n"
    )

    for (emoji, name), data in fish_summary.items():
        result_text += f"{emoji} {name}: {data['count']} шт.\n"

    result_text += f"\nВсего поймано: {len(catches)} рыб, {total_weight:.2f} кг."

    log_event("NET_COLLECT", user_id, user["name"],
              f"Собрана сеть в позиции {position}, поймано: {len(catches)} рыб, {total_weight:.2f} кг",
              GREEN)

    save_data()

    # Отправляем результат новым сообщением
    await query.message.reply_text(result_text)

    # Обновляем сетку
    update_net_message(context, user_id)


# ==================== КНИГА РЫБАКА ====================
async def show_fish_album(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает книгу рыбака с пагинацией"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = user_data[user_id]

    fish_records = user.get("fish_records", {})

    if not fish_records:
        text = (
            f"📙 {user['name']}, это ваша Книга рыбака\n\n"
            f"Здесь хранится вся история вашей добычи:\n"
            f"🎣 Сколько и какой рыбы вы поймали за всё время.\n\n"
            f"❌ Пока что книга пуста. Отправляйтесь на рыбалку!"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_fishing_menu")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    # Сохраняем данные в context для пагинации
    fish_with_max_weight = []
    for fish_name, record in fish_records.items():
        max_weight = record.get("max_weight", 0)
        fish_with_max_weight.append((fish_name, max_weight))

    fish_with_max_weight.sort(key=lambda x: x[1], reverse=True)
    context.user_data["album_fish_list"] = [f[0] for f in fish_with_max_weight]
    context.user_data["album_page"] = 0

    await show_album_page(update, context, 0)


async def show_album_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    """Показывает конкретную страницу книги рыбака"""
    query = update.callback_query

    user_id = update.effective_user.id
    user = user_data[user_id]

    fish_list = context.user_data.get("album_fish_list", [])
    fish_records = user.get("fish_records", {})

    items_per_page = 5
    total_pages = (len(fish_list) + items_per_page - 1) // items_per_page

    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(fish_list))

    text = (
        f"📙 {user['name']}, это ваша Книга рыбака\n\n"
        f"Здесь хранится вся история вашей добычи:\n"
        f"🎣 Сколько и какой рыбы вы поймали за всё время."
    )

    keyboard = []
    for fish_name in fish_list[start_idx:end_idx]:
        record = fish_records[fish_name]
        max_weight = record.get("max_weight", 0)
        emoji = record.get("emoji", "🐟")

        keyboard.append([InlineKeyboardButton(
            f"{emoji} {fish_name} - 🏆 {max_weight:.2f} кг",
            callback_data=f"album_fish_{fish_name}"
        )])

    # Добавляем кнопки навигации
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data="album_prev"))
    nav_row.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="album_page"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("➡️", callback_data="album_next"))
    keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_fishing_menu")])

    context.user_data["album_page"] = page

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def album_change_page(update: Update, context: ContextTypes.DEFAULT_TYPE, direction: int) -> None:
    """Переключает страницу в книге рыбака"""
    query = update.callback_query
    await query.answer()

    current_page = context.user_data.get("album_page", 0)
    fish_list = context.user_data.get("album_fish_list", [])
    items_per_page = 5
    total_pages = (len(fish_list) + items_per_page - 1) // items_per_page

    new_page = current_page + direction
    if 0 <= new_page < total_pages:
        await show_album_page(update, context, new_page)


async def show_fish_details(update: Update, context: ContextTypes.DEFAULT_TYPE, fish_name: str) -> None:
    """Показывает детальную информацию о конкретной рыбе"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = user_data[user_id]

    fish_records = user.get("fish_records", {})
    record = fish_records.get(fish_name, {})
    catches = record.get("catches", [])

    if not catches:
        text = f"❌ Нет записей о рыбе {fish_name}"
        await query.edit_message_text(text, reply_markup=get_fish_details_keyboard())
        return

    # Сортируем по весу (от большего к меньшему)
    sorted_catches = sorted(catches, key=lambda x: x["weight"], reverse=True)

    emoji = record.get("emoji", "🐟")
    rarity = record.get("rarity", "Обычная")
    total_weight = record.get("total_weight", 0)
    total_count = record.get("total_count", 0)

    text = (
        f"{user['name']}, тут находится информация о пойманой рыбе:\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{emoji} {fish_name} ({rarity})\n"
    )

    medals = ["🥇", "🥈", "🥉"]
    for i, catch in enumerate(sorted_catches[:3]):
        text += f"{medals[i]}{catch['weight']:.2f} кг - {catch['date']}\n"

    text += (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Всего поймано - {total_weight:.2f} кг ({total_count} шт.)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎣 Продолжайте рыбачить чтобы поймать самую крупную особь в мире!"
    )

    await query.edit_message_text(
        text,
        reply_markup=get_fish_details_keyboard()
    )


# ==================== ЕДИНЫЙ ОБРАБОТЧИК CALLBACK ====================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    user_id = update.effective_user.id
    user = user_data.get(user_id, {})
    data = query.data

    if data == "start_fishing_new":
        on_cooldown, remaining = is_fishing_on_cooldown(user_id)
        if on_cooldown:
            log_event("COOLDOWN_BLOCK", user_id, user.get("name", "Unknown"),
                      f"Попытка начать рыбалку, осталось: {remaining} сек", YELLOW)
            await query.answer(f"⚠️ Новая рыбалка будет доступна через {remaining} сек.", show_alert=True)
            return

        if is_user_fishing(context):
            remaining_time = get_remaining_fishing_time(context)
            log_event("COOLDOWN_BLOCK", user_id, user.get("name", "Unknown"),
                      f"Уже на рыбалке, осталось: {remaining_time} сек", YELLOW)
            await query.answer(f"⚠️ Вы уже на рыбалке! Новая рыбалка будет доступна через {remaining_time} сек.",
                               show_alert=True)
            return

        await query.answer()
        await start_fishing_process_new_message(update, context)

    elif data == "start_net_fishing":
        await start_net_fishing(update, context)

    elif data == "net_locked":
        await query.answer("🔒 Рыбалка сетями станет доступна на 7 уровне!", show_alert=True)

    elif data.startswith("net_place_"):
        pos = int(data.replace("net_place_", ""))
        await place_net(update, context, pos)

    elif data.startswith("net_check_"):
        pos = int(data.replace("net_check_", ""))
        await check_net(update, context, pos)

    elif data == "show_inventory":
        await query.answer()
        await show_inventory(update, context)

    elif data == "sell_fish":
        await query.answer()
        await sell_all_fish(update, context)

    elif data == "show_upgrades":
        await query.answer()
        await show_upgrades_menu(update, context)

    elif data == "fish_album":
        await show_fish_album(update, context)

    elif data == "album_prev":
        await album_change_page(update, context, -1)

    elif data == "album_next":
        await album_change_page(update, context, 1)

    elif data == "album_page":
        await query.answer()

    elif data.startswith("album_fish_"):
        fish_name = data.replace("album_fish_", "")
        await show_fish_details(update, context, fish_name)

    elif data.startswith("info_"):
        await query.answer()
        upgrade_type = data.replace("info_", "")
        await show_upgrade_info(update, context, upgrade_type)

    elif data.startswith("upgrade_action_"):
        upgrade_type = data.replace("upgrade_action_", "")
        await handle_upgrade_action(update, context, upgrade_type)

    elif data == "back_to_fishing_menu":
        await query.answer()
        reset_fishing_state(context)
        reset_net_fishing_state(context)
        await back_to_fishing_menu(update, context)

    elif data.startswith("catch_"):
        await handle_catch(update, context)

    elif data.startswith("miss_"):
        await handle_miss(update, context)


async def show_upgrades_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает главное меню улучшений"""
    query = update.callback_query
    user_id = update.effective_user.id
    user = user_data[user_id]

    max_weight = get_max_weight(user_id)
    min_time, max_time = get_bite_time_range(user_id)
    reaction_time = get_reaction_time(user_id)

    text = (
        f"🪝 {user['name']}, список улучшений:\n\n"
        f"❔ Для улучшения требуется \"📜 Свиток улучшения\"\n\n"
        f"📊 Макс. вес рыбы: {format_number(max_weight)} кг\n"
        f"⏱ Время поклёвки: {min_time:.1f}-{max_time:.1f} сек\n"
        f"⚡ Время реакции: {reaction_time:.1f} сек\n\n"
        f"📜 У вас свитков: {user['scrolls']} шт.\n\n"
        f"Выберите улучшение для просмотра:"
    )

    await query.edit_message_text(
        text,
        reply_markup=get_upgrades_keyboard(user_id)
    )


async def show_upgrade_info(update: Update, context: ContextTypes.DEFAULT_TYPE, upgrade_type: str) -> None:
    """Показывает информационное окно конкретного улучшения"""
    query = update.callback_query
    user_id = update.effective_user.id
    user = user_data[user_id]

    current_level = user["upgrades"][upgrade_type]
    upgrade_name = UPGRADE_NAMES[upgrade_type]
    upgrade_emoji = get_upgrade_emoji(upgrade_type)
    description = UPGRADE_DESCRIPTIONS[upgrade_type]

    text = (
        f"🪝 {user['name']}, информация об улучшении:\n\n"
        f"{upgrade_emoji} Улучшение: {upgrade_name}\n"
        f"⭐️ Уровень: {current_level}/5\n"
        f"💡 Описание: {description}\n\n"
        f"📜 Для улучшения требуется свиток."
    )

    await query.edit_message_text(
        text,
        reply_markup=get_upgrade_info_keyboard(upgrade_type)
    )


async def handle_upgrade_action(update: Update, context: ContextTypes.DEFAULT_TYPE, upgrade_type: str) -> None:
    """Обрабатывает нажатие кнопки «Улучшить» в информационном окне"""
    query = update.callback_query
    user_id = update.effective_user.id
    user = user_data[user_id]

    current_level = user["upgrades"][upgrade_type]
    upgrade_name = UPGRADE_NAMES[upgrade_type]

    # Проверяем максимальный уровень
    if current_level >= 5:
        await query.answer(f"❌ {upgrade_name} уже на максимальном уровне!", show_alert=True)
        return

    # Проверяем наличие свитков
    if user["scrolls"] < 1:
        await query.answer("❌ У вас нет 📜 Свитков улучшения! Найдите их на рыбалке.", show_alert=True)
        return

    # Улучшаем
    old_level = current_level
    user["upgrades"][upgrade_type] += 1
    user["scrolls"] -= 1
    new_level = user["upgrades"][upgrade_type]

    log_event("UPGRADE", user_id, user["name"],
              f"Улучшение: {upgrade_name}, Уровень: {old_level} → {new_level}, Свитков осталось: {user['scrolls']}",
              GREEN)

    await query.answer(f"✅ {upgrade_name} улучшено до уровня {new_level}!", show_alert=True)
    save_data()

    # Обновляем информационное окно
    description = UPGRADE_DESCRIPTIONS[upgrade_type]
    upgrade_emoji = get_upgrade_emoji(upgrade_type)

    text = (
        f"🪝 {user['name']}, информация об улучшении:\n\n"
        f"{upgrade_emoji} Улучшение: {upgrade_name}\n"
        f"⭐️ Уровень: {new_level}/5\n"
        f"💡 Описание: {description}\n\n"
        f"📜 Для улучшения требуется свиток."
    )

    await query.edit_message_text(
        text,
        reply_markup=get_upgrade_info_keyboard(upgrade_type)
    )


async def show_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    user = user_data[user_id]

    inventory = user["inventory"]

    if not inventory:
        text = f"📦 {user['name']}, Ваш склад пуст. Отправляйтесь на рыбалку!"
        await query.edit_message_text(text, reply_markup=get_inventory_keyboard(is_empty=True))
        return

    total_value = sum(fish["total_price"] for fish in inventory)
    total_weight = sum(fish["weight"] for fish in inventory)

    fish_summary = {}
    for fish in inventory:
        key = (fish["emoji"], fish["name"])
        if key not in fish_summary:
            fish_summary[key] = {"total_weight": 0, "total_price": 0}
        fish_summary[key]["total_weight"] += fish["weight"]
        fish_summary[key]["total_price"] += fish["total_price"]

    sorted_fish = sorted(fish_summary.items(), key=lambda x: x[1]["total_price"], reverse=True)

    text = f"📦 {user['name']}, Ваш склад:\n\n"
    for (emoji, name), data in sorted_fish:
        weight_str = f"{data['total_weight']:.2f}".rstrip('0').rstrip('.')
        price_str = f"{data['total_price']:.2f}".rstrip('0').rstrip('.')
        text += f"{emoji} {name}: {weight_str} кг. ({price_str}$)\n"

    text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"📊 Всего рыб: {len(inventory)} шт.\n"
    text += f"⚖️ Всего рыбы: {format_number(total_weight)} кг.\n"
    text += f"💰 Цена всех рыб: {format_number(total_value)}$"

    await query.edit_message_text(
        text,
        reply_markup=get_inventory_keyboard(is_empty=False)
    )


async def sell_all_fish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    user = user_data[user_id]

    inventory = user["inventory"]

    if not inventory:
        await query.edit_message_text(
            "📦 Ваш склад пуст. Нечего продавать.",
            reply_markup=get_back_keyboard()
        )
        return

    total_earned = sum(fish["total_price"] for fish in inventory)
    fish_count = len(inventory)

    old_balance = user["balance"]
    user["balance"] += total_earned
    user["inventory"] = []

    log_event("SELL", user_id, user["name"],
              f"Продано: {fish_count} шт, Выручка: {total_earned:.2f}$, Баланс: {old_balance:.2f} → {user['balance']:.2f}$",
              GREEN)
    save_data()

    text = (
        f"✅ Вы продали {fish_count} рыб(ы) за {format_number(total_earned)}$!\n"
        f"💰 Ваш новый баланс: {format_number(user['balance'])}$"
    )

    await query.edit_message_text(
        text,
        reply_markup=get_back_keyboard()
    )


async def back_to_fishing_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    user = user_data[user_id]

    reset_fishing_state(context)
    reset_net_fishing_state(context)

    level, exp, exp_needed = get_level_exp(user_id)
    unique_count = len(user.get("unique_fish_caught", []))
    total_unique = len(FISH_DATA)

    # Базовый текст меню
    menu_text = (
        f"🎣 {user['name']} | Меню рыбалки:\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐️ Уровень рыбака: {level} ({exp}/{exp_needed})\n"
        f"🐟 Поймано всего рыбы: {user['total_fish_caught']} шт.\n"
        f"🌊 Уникальные виды: {unique_count} из {total_unique}\n"
    )

    # Добавляем строку со свитками только если не все улучшения на максимуме
    if not are_all_upgrades_maxed(user_id):
        menu_text += f"\n📜 Свиток улучшения: {user['scrolls']} шт.\n"

    menu_text += f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # Добавляем блок крупнейшего улова
    biggest = user.get("biggest_catch", {})
    if biggest and biggest.get("weight", 0) > 0:
        menu_text += (
            f"🏆 Крупнейший улов:\n"
            f"⠀{biggest['emoji']} {biggest['name']} ({biggest['weight']:.2f} кг., {biggest['rarity']})"
        )
    else:
        menu_text += "🏆 Крупнейший улов:\n⠀Пока нет улова"

    await query.edit_message_text(
        menu_text,
        reply_markup=get_fishing_menu_keyboard(user_id)
    )


async def start_fishing_process_new_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    user = user_data[user_id]

    min_time, max_time = get_bite_time_range(user_id)
    fish_delay = random.uniform(min_time, max_time)
    reaction_time = get_reaction_time(user_id)

    log_event("FISHING_START", user_id, user["name"],
              f"Ожидание: {fish_delay:.1f} сек, Реакция: {reaction_time:.1f} сек",
              BLUE)

    message = await query.message.reply_text(
        f"🎣 {user['name']}, вы закинули удочку.\n\n"
        f"🎯 Дождитесь момента, когда рыба зацепится за крючок и подсекайте ее.\n"
        f"⏰ У вас будет {reaction_time:.1f} сек., чтобы подсечь рыбу!",
        reply_markup=create_fishing_grid()
    )

    context.user_data["fishing_message_id"] = message.message_id
    context.user_data["fishing_chat_id"] = message.chat_id
    context.user_data["fishing_start_time"] = time.time()
    context.user_data["fish_delay"] = fish_delay
    context.user_data["reaction_time"] = reaction_time
    context.user_data["fish_appeared"] = False
    context.user_data["active_position"] = None
    context.user_data["current_fish"] = None
    context.user_data["fishing_ended"] = False

    asyncio.create_task(fish_appearance_task_new(update, context, fish_delay, reaction_time, message))


async def fish_appearance_task_new(update: Update, context: ContextTypes.DEFAULT_TYPE, delay: float,
                                   reaction_time: float, message) -> None:
    await asyncio.sleep(delay)

    if context.user_data.get("fishing_ended", False):
        return

    user_id = update.effective_user.id
    user = user_data[user_id]
    current_fish = get_random_fish(user_id)

    context.user_data["current_fish"] = current_fish

    position = random.randint(0, 24)
    context.user_data["active_position"] = position
    context.user_data["fish_appeared"] = True
    context.user_data["fish_appear_time"] = time.time()

    log_event("FISH_APPEAR", user_id, user["name"],
              f"Рыба: {current_fish['name']} ({current_fish['rarity']}), Вес: {current_fish['weight']:.2f} кг, Позиция: {position}",
              BLUE)

    try:
        await message.edit_reply_markup(
            reply_markup=create_fishing_grid(
                fish_emoji=current_fish["emoji"],
                active_position=position
            )
        )

        asyncio.create_task(fish_disappearance_task_new(update, context, reaction_time, message))
    except Exception as e:
        print(f"Ошибка при обновлении сетки: {e}")


async def fish_disappearance_task_new(update: Update, context: ContextTypes.DEFAULT_TYPE, reaction_time: float,
                                      message) -> None:
    await asyncio.sleep(reaction_time)

    if not context.user_data.get("fish_appeared", False):
        return

    user_id = update.effective_user.id
    user = user_data[user_id]
    current_fish = context.user_data.get("current_fish")
    fish_name = current_fish["name"] if current_fish else "рыба"

    log_event("FISH_FAIL", user_id, user["name"], f"Причина: не успел подсечь, Рыба: {fish_name}", RED)

    reset_fishing_state(context)
    set_fishing_cooldown(user_id, 0)

    await message.edit_text(
        f"😓 {user['name']}, вы не успели подсечь {fish_name}, она сорвалась с крючка и уплыла!",
        reply_markup=get_fail_keyboard()
    )


async def handle_catch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = user_data[user_id]

    if not context.user_data.get("fish_appeared", False):
        return

    clicked_pos = int(query.data.split("_")[1])
    active_pos = context.user_data.get("active_position")

    if clicked_pos != active_pos:
        current_fish = context.user_data.get("current_fish")
        fish_name = current_fish["name"] if current_fish else "рыба"

        log_event("FISH_FAIL", user_id, user["name"], f"Причина: промах, Рыба: {fish_name}", RED)

        reset_fishing_state(context)
        set_fishing_cooldown(user_id, 0)

        await query.edit_message_text(
            f"😓 {user['name']}, вы не успели подсечь {fish_name}, она сорвалась с крючка и уплыла!",
            reply_markup=get_fail_keyboard()
        )
        return

    appear_time = context.user_data.get("fish_appear_time", 0)
    current_time = time.time()
    reaction_time = context.user_data.get("reaction_time", 2)

    if current_time - appear_time > reaction_time:
        current_fish = context.user_data.get("current_fish")
        fish_name = current_fish["name"] if current_fish else "рыба"

        log_event("FISH_FAIL", user_id, user["name"], f"Причина: опоздал, Рыба: {fish_name}", RED)

        reset_fishing_state(context)
        set_fishing_cooldown(user_id, 0)

        await query.edit_message_text(
            f"😓 {user['name']}, вы не успели подсечь {fish_name}, она сорвалась с крючка и уплыла!",
            reply_markup=get_fail_keyboard()
        )
        return

    caught_fish = context.user_data.get("current_fish")
    if not caught_fish:
        caught_fish = get_random_fish(user_id)

    user["inventory"].append(caught_fish)

    # Обновляем крупнейший улов
    if "biggest_catch" not in user:
        user["biggest_catch"] = {
            "name": "",
            "weight": 0.0,
            "rarity": "",
            "emoji": ""
        }

    if caught_fish["weight"] > user["biggest_catch"]["weight"]:
        user["biggest_catch"] = {
            "name": caught_fish["name"],
            "weight": caught_fish["weight"],
            "rarity": caught_fish["rarity"],
            "emoji": caught_fish["emoji"]
        }

    # Добавляем в уникальные виды
    if caught_fish["rarity"] in ["Редкая", "Очень редкая", "Уникальная", "Легендарная", "Мифическая"]:
        if "unique_fish_caught" not in user:
            user["unique_fish_caught"] = []
        if caught_fish["name"] not in user["unique_fish_caught"]:
            user["unique_fish_caught"].append(caught_fish["name"])

    # Добавляем запись в книгу рыбака
    if "fish_records" not in user:
        user["fish_records"] = {}

    fish_name = caught_fish["name"]
    if fish_name not in user["fish_records"]:
        user["fish_records"][fish_name] = {
            "emoji": caught_fish["emoji"],
            "rarity": caught_fish["rarity"],
            "catches": [],
            "total_weight": 0.0,
            "total_count": 0,
            "max_weight": 0.0,
            "max_weight_date": ""
        }

    record = user["fish_records"][fish_name]
    catch_date = datetime.now().strftime("%d.%m.%y %H:%M")
    record["catches"].append({
        "weight": caught_fish["weight"],
        "date": catch_date
    })
    record["total_weight"] += caught_fish["weight"]
    record["total_count"] += 1

    if caught_fish["weight"] > record["max_weight"]:
        record["max_weight"] = caught_fish["weight"]
        record["max_weight_date"] = catch_date

    leveled_up = await add_exp(user_id, 1, context)

    # Проверяем выпадение свитка (глобальный лимит)
    global total_scrolls_dropped
    scroll_dropped = False
    if random.randint(1, 100) <= SCROLL_CHANCE and total_scrolls_dropped < MAX_TOTAL_SCROLLS:
        user["scrolls"] += 1
        total_scrolls_dropped += 1
        scroll_dropped = True
        log_event("SCROLL_DROPPED", user_id, user["name"],
                  f"Найден свиток! Всего выпало: {total_scrolls_dropped}/{MAX_TOTAL_SCROLLS}",
                  GREEN)

    scroll_info = f"ДА ({user['scrolls']} шт.)" if scroll_dropped else "Нет"
    log_event("FISH_CAUGHT", user_id, user["name"],
              f"Рыба: {fish_name}, Вес: {caught_fish['weight']:.2f} кг, Цена: {caught_fish['total_price']:.2f}$, Свиток: {scroll_info}",
              GREEN)

    reset_fishing_state(context)
    set_fishing_cooldown(user_id, 0)
    save_data()

    catch_text = (
        f"🎣 {user['name']}, вы поймали рыбу!\n\n"
        f"{caught_fish['emoji']} {fish_name}\n"
        f"⚖️ Вес: {caught_fish['weight']:.2f} кг.\n"
        f"💎 Редкость: {caught_fish['rarity']}\n\n"
        f"Поздравляем с удачной рыбалкой! 🌊"
    )

    if scroll_dropped:
        catch_text += "\n\nВнутри рыбы вы нашли 📜 Свиток улучшения!"

    if leveled_up:
        catch_text += f"\n\n🎉 Поздравляем! Вы достигли уровня {user['level']}! 🎉"

    await query.edit_message_text(
        catch_text,
        reply_markup=get_catch_result_keyboard()
    )


async def handle_miss(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user = user_data[user_id]

    if context.user_data.get("fish_appeared", False):
        current_fish = context.user_data.get("current_fish")
        fish_name = current_fish["name"] if current_fish else "рыба"

        log_event("FISH_FAIL", user_id, user["name"], f"Причина: промах (miss), Рыба: {fish_name}", RED)

        reset_fishing_state(context)
        set_fishing_cooldown(user_id, 0)

        await query.edit_message_text(
            f"😓 {user['name']}, вы не успели подсечь {fish_name}, она сорвалась с крючка и уплыла!",
            reply_markup=get_fail_keyboard()
        )


# ==================== ОБРАБОТКА ОШИБОК ====================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update and update.effective_user:
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        log_event("ERROR", user_id, user_name, f"Ошибка: {context.error}", RED)
    else:
        print(f"{RED}[{datetime.now().strftime('%H:%M:%S')}] [ERROR] {context.error}{RESET}")

    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Попробуйте позже или используйте /start для перезапуска."
            )
        except:
            pass


# ==================== ЗАПУСК БОТА ====================
def main() -> None:
    # Загружаем данные перед запуском
    load_data()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{CYAN}[{timestamp}] [BOT] Бот «Рыбалка» запущен!{RESET}")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
