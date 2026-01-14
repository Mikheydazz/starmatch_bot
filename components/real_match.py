def sum_digits(num):
    """Суммирует цифры до однозначного числа (кроме 11, 22, 33)"""
    if num in [11, 22, 33]:
        return num
    while num > 9:
        num = sum(int(d) for d in str(num))
    return num

def calculate_elements(day, month, year):
    """Рассчитывает 4 стихии"""
    # Огонь - сумма цифр дня
    fire = sum_digits(day)
    
    # Земля - сумма цифр месяца
    earth = sum_digits(month)
    
    # Воздух - сумма цифр года
    air = sum_digits(sum(int(d) for d in str(year)))
    
    # Вода - сумма первых трёх
    water = sum_digits(fire + earth + air)
    
    return {'fire': fire, 'earth': earth, 'air': air, 'water': water}

def calculate_individual_matrix(date_str):
    """date_str в формате 'DD.MM.YYYY'"""
    day, month, year = map(int, date_str.split('.'))
    
    # 1. Число Личности
    personality = sum_digits(day)
    
    # 2. Число Судьбы
    full_sum = sum(int(d) for d in date_str.replace('.', ''))
    destiny = sum_digits(full_sum)
    
    # 3. Число Золотого Алхимика
    golden_alchemist = sum_digits(personality + destiny)
    
    # 4. Число Кармических Задач
    month_year_sum = sum(int(d) for d in f"{month:02d}{year}")
    karmic_tasks = sum_digits(month_year_sum)
    
    # Матрица 3x3
    matrix = [
        sum_digits(month),                    # Ячейка 1
        personality,                          # Ячейка 2 (уже суммировано)
        sum_digits(sum(int(d) for d in str(year))), # Ячейка 3
    ]
    
    # Ячейка 4
    matrix.append(sum_digits(matrix[0] + matrix[1] + matrix[2]))
    
    # Ячейка 5
    matrix.append(personality)
    
    # Ячейка 6
    matrix.append(karmic_tasks)
    
    # Ячейка 7
    matrix.append(destiny)
    
    # Ячейка 8
    matrix.append(golden_alchemist)
    
    # Ячейка 9
    matrix.append(sum_digits(sum(matrix[:8])))
    
    return {
        'matrix': matrix,  # список из 9 чисел
        'personality': personality,
        'destiny': destiny,
        'golden_alchemist': golden_alchemist,
        'karmic_tasks': karmic_tasks,
        'elements': calculate_elements(day, month, year)
    }

def calculate_matrix_compatibility(matrix1, matrix2):
    """
    Сравнивает 9 ячеек матриц.
    Возвращает процент 0-100%
    """
    compatibility_matrix = {
        # (число1, число2): балл (0-10)
        (1, 1): 10, (2, 2): 10, (3, 3): 10, (4, 4): 10, (5, 5): 10,
        (6, 6): 10, (7, 7): 10, (8, 8): 10, (9, 9): 10,
        
        # Гармоничные сочетания
        (1, 4): 9, (1, 7): 9, (4, 1): 9, (7, 1): 9,
        (2, 5): 9, (2, 8): 9, (5, 2): 9, (8, 2): 9,
        (3, 6): 9, (3, 9): 9, (6, 3): 9, (9, 3): 9,
        
        (1, 8): 8, (8, 1): 8,  # лидер + организатор
        (2, 6): 8, (6, 2): 8,  # дипломат + миротворец
        (4, 7): 8, (7, 4): 8,  # практик + аналитик
        
        # Нейтральные (добавлены для покрытия)
        (1, 2): 6, (1, 3): 6, (1, 5): 6, (1, 6): 6, (1, 9): 6,
        (2, 1): 6, (2, 3): 6, (2, 4): 6, (2, 7): 6, (2, 9): 6,
        (3, 1): 6, (3, 2): 6, (3, 4): 6, (3, 5): 6, (3, 7): 6, (3, 8): 6,
        (4, 2): 6, (4, 3): 6, (4, 5): 6, (4, 6): 6, (4, 8): 6, (4, 9): 6,
        (5, 1): 6, (5, 3): 6, (5, 4): 6, (5, 6): 6, (5, 7): 6, (5, 9): 6,
        (6, 1): 6, (6, 4): 6, (6, 5): 6, (6, 7): 6, (6, 8): 6, (6, 9): 6,
        (7, 2): 6, (7, 3): 6, (7, 5): 6, (7, 6): 6, (7, 8): 6, (7, 9): 6,
        (8, 3): 6, (8, 4): 6, (8, 6): 6, (8, 7): 6, (8, 9): 6,
        (9, 1): 6, (9, 2): 6, (9, 4): 6, (9, 5): 6, (9, 6): 6, (9, 7): 6, (9, 8): 6,
        
        # Сложные сочетания
        (4, 5): 4, (5, 4): 4,  # стабильность vs перемены
        (1, 7): 4, (7, 1): 4,  # практик vs аналитик (конфликт)
        (8, 9): 4, (9, 8): 4,  # материя vs духовность
    }
    
    total_score = 0
    for i in range(9):
        pair = (matrix1[i], matrix2[i])
        # Если нет в таблице, используем нейтральный балл 5
        score = compatibility_matrix.get(pair, 5)
        total_score += score
    
    # Переводим в процент: 9 ячеек * макс 10 баллов = 90
    return (total_score / 90) * 100

def calculate_elements_compatibility(elem1, elem2):
    """
    Сравнивает 4 стихии.
    Возвращает процент 0-100%
    """
    elements_compatibility = {
        'identical': 10,      # одинаковые значения
        'harmonious': 8,      # разница 1-2
        'neutral': 6,         # разница 3-4
        'challenging': 4,     # разница 5+
        'opposite': 2         # противоположные (1 и 9, 2 и 8 и т.д.)
    }
    
    total_score = 0
    elements = ['fire', 'earth', 'air', 'water']
    
    for elem in elements:
        val1, val2 = elem1[elem], elem2[elem]
        diff = abs(val1 - val2)
        
        if val1 == val2:
            score = elements_compatibility['identical']
        elif diff <= 2:
            score = elements_compatibility['harmonious']
        elif diff <= 4:
            score = elements_compatibility['neutral']
        elif diff >= 6 and (val1 + val2 == 10 or abs(val1 - val2) >= 8):
            score = elements_compatibility['opposite']
        else:
            score = elements_compatibility['challenging']
        
        total_score += score
    
    # 4 стихии * макс 10 баллов = 40
    return (total_score / 40) * 100

def calculate_key_numbers_compatibility(person1, person2):
    """
    Сравнивает ключевые числа.
    Возвращает процент 0-100%
    """
    # Таблица совместимости ключевых чисел
    key_numbers_comp = {
        # Числа Судьбы
        (1, 1): 9, (2, 2): 9, (3, 3): 9, (4, 4): 9, (5, 5): 9,
        (6, 6): 9, (7, 7): 9, (8, 8): 9, (9, 9): 9,
        
        (1, 4): 8, (1, 7): 8, (4, 1): 8, (7, 1): 8,
        (1, 8): 9, (8, 1): 9,  # идеальное деловое партнёрство
        (2, 6): 8, (6, 2): 8,
        (3, 9): 8, (9, 3): 8,
        (4, 7): 8, (7, 4): 8,
        
        # Числа Личности
        (2, 9): 7, (9, 2): 7,  # дополнение
        (1, 2): 6, (2, 1): 6,
        
        # По умолчанию
        'default': 5
    }
    
    # 1. Совместимость Чисел Судьбы
    destiny_pair = (person1['destiny'], person2['destiny'])
    destiny_score = key_numbers_comp.get(destiny_pair, key_numbers_comp['default'])
    
    # 2. Совместимость Чисел Личности
    personality_pair = (person1['personality'], person2['personality'])
    personality_score = key_numbers_comp.get(personality_pair, key_numbers_comp['default'])
    
    # 3. Совместимость Кармических Задач
    karmic_pair = (person1['karmic_tasks'], person2['karmic_tasks'])
    karmic_score = key_numbers_comp.get(karmic_pair, key_numbers_comp['default'])
    
    # Средний балл по трём параметрам
    avg_score = (destiny_score + personality_score + karmic_score) / 3
    
    # Переводим в процент: макс 10 баллов
    return (avg_score / 10) * 100

def calculate_compatibility(date1, date2):
    """
    Возвращает процент совместимости 0-100%
    date1, date2 в формате 'DD.MM.YYYY'
    """
    
    # 1. Рассчитываем индивидуальные данные
    person1 = calculate_individual_matrix(date1)
    person2 = calculate_individual_matrix(date2)
    
    # 2. Совместимость по матрице (9 ячеек)
    matrix_score = calculate_matrix_compatibility(
        person1['matrix'], 
        person2['matrix']
    )
    
    # 3. Совместимость по стихиям
    elements_score = calculate_elements_compatibility(
        person1['elements'],
        person2['elements']
    )
    
    # 4. Совместимость по ключевым числам
    key_numbers_score = calculate_key_numbers_compatibility(person1, person2)
    
    # 5. Итоговый процент
    # final_percentage = (matrix_score + elements_score + key_numbers_score) / 3
    final_percentage = matrix_score
    
    return {
        'percentage': round(final_percentage, 1),
        'details': {
            'matrix_score': matrix_score,
            'elements_score': elements_score,
            'key_numbers_score': key_numbers_score
        },
        'person1': person1,
        'person2': person2
    }


# components.py
# ... существующий код ...

def get_zodiac_sign(day, month):
    """Определяет знак зодиака по дню и месяцу"""
    if (month == 3 and day >= 21) or (month == 4 and day <= 19):
        return "Овен ♈"
    elif (month == 4 and day >= 20) or (month == 5 and day <= 20):
        return "Телец ♉"
    elif (month == 5 and day >= 21) or (month == 6 and day <= 20):
        return "Близнецы ♊"
    elif (month == 6 and day >= 21) or (month == 7 and day <= 22):
        return "Рак ♋"
    elif (month == 7 and day >= 23) or (month == 8 and day <= 22):
        return "Лев ♌"
    elif (month == 8 and day >= 23) or (month == 9 and day <= 22):
        return "Дева ♍"
    elif (month == 9 and day >= 23) or (month == 10 and day <= 22):
        return "Весы ♎"
    elif (month == 10 and day >= 23) or (month == 11 and day <= 21):
        return "Скорпион ♏"
    elif (month == 11 and day >= 22) or (month == 12 and day <= 21):
        return "Стрелец ♐"
    elif (month == 12 and day >= 22) or (month == 1 and day <= 19):
        return "Козерог ♑"
    elif (month == 1 and day >= 20) or (month == 2 and day <= 18):
        return "Водолей ♒"
    else:  # (month == 2 and day >= 19) or (month == 3 and day <= 20)
        return "Рыбы ♓"

def get_zodiac_emoji(sign_name):
    """Возвращает эмодзи для знака зодиака"""
    emoji_map = {
        "Овен": "♈",
        "Телец": "♉", 
        "Близнецы": "♊",
        "Рак": "♋",
        "Лев": "♌",
        "Дева": "♍",
        "Весы": "♎",
        "Скорпион": "♏",
        "Стрелец": "♐",
        "Козерог": "♑",
        "Водолей": "♒",
        "Рыбы": "♓"
    }
    for name, emoji in emoji_map.items():
        if name in sign_name:
            return emoji
    return "✨"

def calculate_age(birth_date):
    """Вычисляет возраст по дате рождения"""
    from datetime import datetime
    today = datetime.now()
    birth = datetime.strptime(birth_date, "%d.%m.%Y")
    age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    return age