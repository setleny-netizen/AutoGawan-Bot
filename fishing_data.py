# fish_data.py - данные о рыбах для игры Рыбалка

FISH_DATA = [
    # ========== ОБЫЧНЫЕ (20 видов) ==========
    {"emoji": "🐟", "name": "Сарган", "weight_range": (0.2, 1.5), "price_range": (3, 8), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Барабуля", "weight_range": (0.1, 1.0), "price_range": (2, 24), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Горбуша", "weight_range": (1.5, 2.2), "price_range": (5, 10), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Камбала", "weight_range": (0.5, 2.5), "price_range": (8, 20), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Окунь морской", "weight_range": (0.3, 1.2), "price_range": (6, 12), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Кефаль", "weight_range": (0.2, 1.0), "price_range": (4, 10), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Треска", "weight_range": (0.8, 4.0), "price_range": (5, 15), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Мойва", "weight_range": (0.05, 0.1), "price_range": (2, 5), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Килька", "weight_range": (0.02, 0.05), "price_range": (1, 3), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Хамса", "weight_range": (0.01, 0.03), "price_range": (1, 2), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Путассу", "weight_range": (0.1, 0.4), "price_range": (2, 4), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Минтай", "weight_range": (0.5, 2.0), "price_range": (3, 7), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Скумбрия", "weight_range": (0.3, 1.2), "price_range": (4, 9), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Ставрида", "weight_range": (0.1, 0.5), "price_range": (3, 6), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Зубатка", "weight_range": (1.0, 4.0), "price_range": (8, 16), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Палтус", "weight_range": (1.5, 6.0), "price_range": (12, 25), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Налим", "weight_range": (0.5, 2.5), "price_range": (5, 12), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Судак", "weight_range": (0.8, 3.0), "price_range": (6, 15), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Щука", "weight_range": (1.0, 5.0), "price_range": (5, 12), "rarity": "Обычная", "chance": 2.5},
    {"emoji": "🐟", "name": "Лещ", "weight_range": (0.3, 1.5), "price_range": (3, 8), "rarity": "Обычная", "chance": 2.5},
    
    # ========== РЕДКИЕ (8 видов) ==========
    {"emoji": "🦀", "name": "Морской краб", "weight_range": (0.5, 1.1), "price_range": (17, 27), "rarity": "Редкая", "chance": 2.5},
    {"emoji": "🦑", "name": "Кальмар", "weight_range": (0.3, 1.5), "price_range": (10, 20), "rarity": "Редкая", "chance": 2.5},
    {"emoji": "🦞", "name": "Омар", "weight_range": (0.5, 2.0), "price_range": (25, 40), "rarity": "Редкая", "chance": 2.5},
    {"emoji": "🐙", "name": "Осьминог", "weight_range": (1.0, 3.0), "price_range": (15, 30), "rarity": "Редкая", "chance": 2.5},
    {"emoji": "🐟", "name": "Дорада", "weight_range": (0.5, 2.0), "price_range": (12, 25), "rarity": "Редкая", "chance": 2.5},
    {"emoji": "🐟", "name": "Сибас", "weight_range": (0.4, 1.8), "price_range": (10, 22), "rarity": "Редкая", "chance": 2.5},
    {"emoji": "🐟", "name": "Морской язык", "weight_range": (0.2, 1.0), "price_range": (15, 30), "rarity": "Редкая", "chance": 2.5},
    {"emoji": "🐟", "name": "Угорь", "weight_range": (0.5, 2.5), "price_range": (12, 28), "rarity": "Редкая", "chance": 2.5},
    
    # ========== ОЧЕНЬ РЕДКИЕ (6 видов) ==========
    {"emoji": "🐠", "name": "Рыба-клоун", "weight_range": (0.015, 0.3), "price_range": (25, 50), "rarity": "Очень редкая", "chance": 2.5},
    {"emoji": "🐟", "name": "Золотая рыбка", "weight_range": (0.1, 0.5), "price_range": (150, 300), "rarity": "Очень редкая", "chance": 2.5},
    {"emoji": "🐟", "name": "Королевская макрель", "weight_range": (2.0, 8.0), "price_range": (20, 40), "rarity": "Очень редкая", "chance": 2.5},
    {"emoji": "🐟", "name": "Василиск", "weight_range": (1.5, 4.0), "price_range": (30, 60), "rarity": "Очень редкая", "chance": 2.5},
    {"emoji": "🐟", "name": "Пиранья", "weight_range": (0.3, 0.8), "price_range": (20, 35), "rarity": "Очень редкая", "chance": 2.5},
    {"emoji": "🐟", "name": "Электрический скат", "weight_range": (2.0, 10.0), "price_range": (25, 50), "rarity": "Очень редкая", "chance": 2.5},
    
    # ========== УНИКАЛЬНЫЕ (3 вида) ==========
    {"emoji": "🐡", "name": "Фугу", "weight_range": (1, 3), "price_range": (200, 400), "rarity": "Уникальная", "chance": 2.5},
    {"emoji": "🐟", "name": "Голубой марлин", "weight_range": (50, 300), "price_range": (40, 80), "rarity": "Уникальная", "chance": 2.5},
    {"emoji": "🐟", "name": "Меч-рыба", "weight_range": (30, 250), "price_range": (35, 70), "rarity": "Уникальная", "chance": 2.5},
    
    # ========== ЛЕГЕНДАРНЫЕ (2 вида) ==========
    {"emoji": "🦈", "name": "Белая акула", "weight_range": (680, 1800), "price_range": (15, 15), "rarity": "Легендарная", "chance": 2.5},
    {"emoji": "🦑", "name": "Гигантский кальмар", "weight_range": (100, 400), "price_range": (50, 100), "rarity": "Легендарная", "chance": 2.5},
    
    # ========== МИФИЧЕСКАЯ (1 вид) ==========
    {"emoji": "🐋", "name": "Синий кит", "weight_range": (100000, 190000), "price_range": (30, 30), "rarity": "Мифическая", "chance": 2.5},
]

# Шансы свитка (20%)
SCROLL_CHANCE = 20
MAX_SCROLLS = 30
