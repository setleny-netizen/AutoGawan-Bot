# fish_data.py - данные о рыбах для игры Рыбалка

FISH_DATA = [
    {"emoji": "🐟", "name": "Сарган", "weight_range": (0.2, 1.5), "price_range": (3, 8), "rarity": "Обычная", "chance": 25},
    {"emoji": "🐟", "name": "Барабуля", "weight_range": (0.1, 1.0), "price_range": (2, 24), "rarity": "Обычная", "chance": 20},
    {"emoji": "🐟", "name": "Горбуша", "weight_range": (1.5, 2.2), "price_range": (5, 10), "rarity": "Обычная", "chance": 20},
    {"emoji": "🦀", "name": "Морской краб", "weight_range": (0.5, 1.1), "price_range": (17, 27), "rarity": "Редкая", "chance": 15},
    {"emoji": "🐠", "name": "Рыба-клоун", "weight_range": (0.015, 0.3), "price_range": (4.25, 42.5), "rarity": "Очень редкая", "chance": 12},
    {"emoji": "🐡", "name": "Фугу", "weight_range": (1, 3), "price_range": (200, 400), "rarity": "Уникальная", "chance": 5},
    {"emoji": "🦈", "name": "Белая акула", "weight_range": (680, 1800), "price_range": (15, 15), "rarity": "Легендарная", "chance": 2},
    {"emoji": "🐋", "name": "Синий кит", "weight_range": (100000, 190000), "price_range": (30, 30), "rarity": "Мифическая", "chance": 1},
]

# Шансы свитка (5%)
SCROLL_CHANCE = 90
MAX_SCROLLS = 30
