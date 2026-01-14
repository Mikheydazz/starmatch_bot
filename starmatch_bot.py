import telebot
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from telebot import types
from telebot.handler_backends import State, StatesGroup
from telebot.custom_filters import StateFilter
import random
from datetime import datetime
import json
import os
from components import *
import logging

# Настраиваем логирование
logging.basicConfig(
    level=logging.WARNING,  # Только важные сообщения
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Уменьшаем уровень логирования для telebot
logging.getLogger('telebot').setLevel(logging.WARNING)

TOKEN = "7321100568:AAHawMKy6af-wmSl1G6RmT0dBsUAEaEyfks"
GROUP_ID = -1001928901997
MECHANIC_PRICE = 5
MATCH_PRICE = 1  # стоимость проверки совместимости

bot = telebot.TeleBot(TOKEN)

# Файлы для хранения данных
DATA_FILE = "users_data.json"
LIKES_FILE = "likes_data.json"

def safe_edit_message(chat_id, message_id, text=None, reply_markup=None, parse_mode=None):
    """Безопасно редактирует сообщение с обработкой ошибок"""
    try:
        if text:
            bot.edit_message_text(
                text,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
        elif reply_markup:
            bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup
            )
        return True
    except Exception as e:
        print(f"Ошибка редактирования сообщения: {e}")
        return False


# Загружаем данные
def load_data(filename, default={}):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default

def save_data(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Загружаем все данные (объединённые)
users_data = load_data(DATA_FILE)
likes_data = load_data(LIKES_FILE, {"likes": {}, "mutual": {}})

# Хранилище для временных данных
temp_data = {}

# Структура данных для каждого пользователя:
# users_data[user_id] = {
#     "balance": 10,
#     "registered_at": "2024-01-01 12:00:00",
#     "profile": {
#         "name": "Имя",
#         "gender": "Мужской",
#         "birthday": "29.06.2007",
#         "age": 17,
#         "photo_id": "xxx",
#         "bio": "О себе",
#         "zodiac": "Рак ♋"
#         "city": "Москва"  # НОВОЕ ПОЛЕ
#     }
# }

# Состояния для регистрации
class RegistrationStates(StatesGroup):
    waiting_name = State()
    waiting_gender = State()
    waiting_birthday = State()
    waiting_photo = State()
    waiting_bio = State()
    waiting_zodiac = State()
    waiting_city = State() 

# Состояния для просмотра анкет
class BrowseStates(StatesGroup):
    browsing = State()

# Состояния для матрицы
class MatchStates(StatesGroup):
    waiting_date1 = State()
    waiting_date2 = State()

# Зодиакальные знаки для выбора
ZODIAC_SIGNS = [
    "Овен ♈", "Телец ♉", "Близнецы ♊", "Рак ♋",
    "Лев ♌", "Дева ♍", "Весы ♎", "Скорпион ♏",
    "Стрелец ♐", "Козерог ♑", "Водолей ♒", "Рыбы ♓"
]

# Функция для обработки взаимных лайков
def check_mutual_like(user_id, target_id):
    """Проверяет взаимные лайки и отправляет уведомления"""
    # Инициализируем структуры данных, если их нет
    if "likes" not in likes_data:
        likes_data["likes"] = {}
    if "mutual" not in likes_data:
        likes_data["mutual"] = {}
    
    # Инициализируем списки лайков для пользователей
    if user_id not in likes_data["likes"]:
        likes_data["likes"][user_id] = []
    if target_id not in likes_data["likes"]:
        likes_data["likes"][target_id] = []
    
    # Добавляем лайк
    if target_id not in likes_data["likes"][user_id]:
        likes_data["likes"][user_id].append(target_id)
        save_data(LIKES_FILE, likes_data)
    
    # Проверяем взаимность
    if user_id in likes_data["likes"].get(target_id, []):
        # Удаляем из списков лайков и добавляем в взаимные
        if user_id in likes_data["likes"][target_id]:
            likes_data["likes"][target_id].remove(user_id)
        if target_id in likes_data["likes"][user_id]:
            likes_data["likes"][user_id].remove(target_id)
        
        # Добавляем в список взаимных лайков
        mutual_key = f"{min(user_id, target_id)}_{max(user_id, target_id)}"
        if mutual_key not in likes_data["mutual"]:
            likes_data["mutual"][mutual_key] = {
                "users": [user_id, target_id],
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        save_data(LIKES_FILE, likes_data)
        
        # Отправляем уведомления обоим пользователям
        send_mutual_like_notification(user_id, target_id)
        return True
    
    return False

def send_mutual_like_notification(user_id, target_id):
    """Отправляет уведомления о взаимном лайке"""
    user_profile = users_data[user_id]["profile"]
    target_profile = users_data[target_id]["profile"]
    
    # Клавиатура с кнопкой для просмотра контактов
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📞 Контакты", callback_data=f"show_contacts_{target_id}"),
        InlineKeyboardButton("👀 Профиль", callback_data=f"show_profile_{target_id}")
    )
    
    # Уведомление пользователю
    try:
        bot.send_message(
            user_id,
            f"💖 *У вас взаимная симпатия!*\n\n"
            f"Вы и {target_profile['name']} понравились друг другу!\n"
            f"Теперь вы можете связаться друг с другом.",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
    
    # Уведомление целевой пользователь
    try:
        keyboard_target = InlineKeyboardMarkup(row_width=2)
        keyboard_target.add(
            InlineKeyboardButton("📞 Контакты", callback_data=f"show_contacts_{user_id}"),
            InlineKeyboardButton("👀 Профиль", callback_data=f"show_profile_{user_id}")
        )
        
        bot.send_message(
            target_id,
            f"💖 *У вас взаимная симпатия!*\n\n"
            f"Вы и {user_profile['name']} понравились друг другу!\n"
            f"Теперь вы можете связаться друг с другом.",
            parse_mode="Markdown",
            reply_markup=keyboard_target
        )
    except Exception as e:
        print(f"Ошибка отправки уведомления пользователю {target_id}: {e}")

# Регистрация / старт
@bot.message_handler(commands=["start"])
def start(message: Message):
    user_id = str(message.from_user.id)
    
    if user_id in users_data:
        show_main_menu(user_id, message.chat.id)
    else:
        bot.send_message(
            message.chat.id,
            "✨ *Добро пожаловать в бот для знакомств!*\n\n"
            "Давайте создадим вашу анкету. Это займёт всего пару минут.\n\n"
            "Для начала, как вас зовут?",
            parse_mode="Markdown"
        )
        bot.set_state(user_id, RegistrationStates.waiting_name, message.chat.id)

# Регистрация: Имя
@bot.message_handler(state=RegistrationStates.waiting_name)
def get_name(message: Message):
    user_id = str(message.from_user.id)
    name = message.text.strip()
    
    if len(name) < 2:
        bot.send_message(message.chat.id, "❌ Имя должно содержать минимум 2 символа. Попробуйте снова:")
        return
    
    temp_data[user_id] = {"profile": {"name": name}}
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("👨 Мужской", callback_data="gender_m"),
        InlineKeyboardButton("👩 Женский", callback_data="gender_f")
    )
    
    bot.send_message(
        message.chat.id,
        f"Отлично, {name}! Теперь укажите ваш пол:",
        reply_markup=keyboard
    )
    
    bot.set_state(user_id, RegistrationStates.waiting_gender, message.chat.id)

# Регистрация: Пол (callback)
@bot.callback_query_handler(func=lambda call: call.data.startswith("gender_"), state=RegistrationStates.waiting_gender)
def get_gender(call: CallbackQuery):
    user_id = str(call.from_user.id)
    gender = "Мужской" if call.data == "gender_m" else "Женский"
    
    temp_data[user_id]["profile"]["gender"] = gender
    
    bot.edit_message_text(
        f"✅ Пол: {gender}\n\n"
        "📅 Теперь введите вашу дату рождения в формате:\n"
        "`ДД.ММ.ГГГГ`\n\n"
        "*Пример:* `29.06.2007`",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )
    
    bot.set_state(user_id, RegistrationStates.waiting_birthday, call.message.chat.id)
    bot.answer_callback_query(call.id)

# Регистрация: Дата рождения
@bot.message_handler(state=RegistrationStates.waiting_birthday)
def get_birthday(message: Message):
    user_id = str(message.from_user.id)
    birthday = message.text.strip()
    
    if not validate_date(birthday):
        bot.send_message(
            message.chat.id,
            "❌ *Неверный формат даты!*\n\n"
            "Пожалуйста, введите дату в формате:\n"
            "`ДД.ММ.ГГГГ`\n\n"
            "*Пример:* `15.04.1986`",
            parse_mode="Markdown"
        )
        return
    
    # Проверяем возраст (18+)
    try:
        age = calculate_age(birthday)
        if age < 18:
            bot.send_message(
                message.chat.id,
                "❌ Извините, бот предназначен для пользователей от 18 лет."
            )
            bot.delete_state(user_id, message.chat.id)
            return
    except:
        pass
    
    temp_data[user_id]["profile"]["birthday"] = birthday
    temp_data[user_id]["profile"]["age"] = age
    
    bot.send_message(
        message.chat.id,
        f"✅ Дата рождения: {birthday}\n"
        f"📊 Возраст: {age} лет\n\n"
        "📸 Теперь отправьте вашу фотографию.\n"
        "*Рекомендуется:* портретное фото, где хорошо видно лицо",
        parse_mode="Markdown"
    )
    
    bot.set_state(user_id, RegistrationStates.waiting_photo, message.chat.id)

# Регистрация: Фото
@bot.message_handler(content_types=['photo'], state=RegistrationStates.waiting_photo)
def get_photo(message: Message):
    user_id = str(message.from_user.id)
    
    # Сохраняем photo_id самой большой версии фото
    photo_id = message.photo[-1].file_id
    temp_data[user_id]["profile"]["photo_id"] = photo_id
    
    bot.send_message(
        message.chat.id,
        "✅ Фото сохранено!\n\n"
        "✏️ Теперь напишите краткую информацию о себе:\n"
        "*Пример:* Интересы, хобби, что ищете в отношениях\n\n"
        "*Максимум 500 символов*",
        parse_mode="Markdown"
    )
    
    bot.set_state(user_id, RegistrationStates.waiting_bio, message.chat.id)

@bot.message_handler(state=RegistrationStates.waiting_photo)
def wrong_photo_input(message: Message):
    bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте фотографию.")

# Регистрация: Биография
@bot.message_handler(state=RegistrationStates.waiting_bio)
def get_bio(message: Message):
    user_id = str(message.from_user.id)
    bio = message.text.strip()
    
    if len(bio) > 500:
        bot.send_message(message.chat.id, "❌ Биография слишком длинная (максимум 500 символов). Сократите:")
        return
    if len(bio) < 10:
        bot.send_message(message.chat.id, "❌ Биография слишком короткая. Расскажите немного больше о себе:")
        return
    
    temp_data[user_id]["profile"]["bio"] = bio
    
    # СПРАШИВАЕМ ГОРОД ПОСЛЕ БИОГРАФИИ
    bot.send_message(
        message.chat.id,
        "🏙️ *В каком городе вы находитесь?*\n\n"
        "Это поможет находить людей поблизости.\n"
        "Если не хотите указывать город, отправьте \"-\" или нажмите кнопку ниже.",
        parse_mode="Markdown"
    )
    
    # Добавляем кнопку для пропуска города
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🚫 Не указывать город", callback_data="skip_city"))
    
    bot.send_message(message.chat.id, "Или нажмите кнопку:", reply_markup=keyboard)
    
    bot.set_state(user_id, RegistrationStates.waiting_city, message.chat.id)

# Обработка города
@bot.callback_query_handler(func=lambda call: call.data == "skip_city", state=RegistrationStates.waiting_city)
def skip_city(call: CallbackQuery):
    user_id = str(call.from_user.id)
    temp_data[user_id]["profile"]["city"] = None
    
    bot.edit_message_text(
        "✅ Город не указан. Вы будете видеть анкеты из всех городов.\n\n"
        "Теперь определим ваш знак зодиака...",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )
    
    process_zodiac_selection(user_id, call.message.chat.id)
    bot.answer_callback_query(call.id)

@bot.message_handler(state=RegistrationStates.waiting_city)
def get_city(message: Message):
    user_id = str(message.from_user.id)
    city = message.text.strip()
    
    if city.lower() in ["-", "нет", "не указывать", "пропустить", "skip"]:
        city = None
        city_text = "не указан"
    else:
        # Очищаем и форматируем название города
        city = city.title().strip()
        if len(city) < 2:
            bot.send_message(message.chat.id, "❌ Название города слишком короткое. Попробуйте снова:")
            return
        city_text = city
    
    temp_data[user_id]["profile"]["city"] = city
    
    bot.send_message(
        message.chat.id,
        f"✅ Город: {city_text}\n\n"
        "Теперь определим ваш знак зодиака...",
        parse_mode="Markdown"
    )
    
    process_zodiac_selection(user_id, message.chat.id)

def process_zodiac_selection(user_id, chat_id):
    """Определяет знак зодиака и предлагает подтвердить или выбрать другой"""
    birthday = temp_data[user_id]["profile"]["birthday"]
    day, month, year = map(int, birthday.split('.'))
    zodiac = get_zodiac_sign(day, month)
    
    temp_data[user_id]["profile"]["zodiac"] = zodiac
    
    keyboard = InlineKeyboardMarkup(row_width=3)
    buttons = []
    
    for sign in ZODIAC_SIGNS:
        if sign == zodiac:
            text = f"✅ {sign}"
        else:
            text = sign
        buttons.append(InlineKeyboardButton(text, callback_data=f"zodiac_{sign.split()[0]}"))
    
    for i in range(0, len(buttons), 3):
        keyboard.add(*buttons[i:i+3])
    
    keyboard.add(InlineKeyboardButton("✅ Подтвердить", callback_data="zodiac_confirm"))
    
    bot.send_message(
        chat_id,
        f"♈ *Знак зодиака*\n\n"
        f"По вашей дате рождения ({birthday}) определен знак:\n"
        f"🎯 *{zodiac}*\n\n"
        "Если это неверно, выберите правильный знак ниже:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    
    bot.set_state(user_id, RegistrationStates.waiting_zodiac, chat_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("zodiac_"), state=RegistrationStates.waiting_zodiac)
def handle_zodiac(call: CallbackQuery):
    user_id = str(call.from_user.id)
    
    if call.data == "zodiac_confirm":
        complete_registration(user_id, call.message.chat.id)
    else:
        zodiac_name = call.data.replace("zodiac_", "")
        current_zodiac = temp_data[user_id]["profile"]["zodiac"]
        new_zodiac = None
        
        for sign in ZODIAC_SIGNS:
            if zodiac_name in sign:
                new_zodiac = sign
                break
        
        if new_zodiac == current_zodiac:
            bot.answer_callback_query(call.id)
            return
        
        temp_data[user_id]["profile"]["zodiac"] = new_zodiac
        
        keyboard = InlineKeyboardMarkup(row_width=3)
        buttons = []
        
        for sign in ZODIAC_SIGNS:
            if sign == new_zodiac:
                text = f"✅ {sign}"
            else:
                text = sign
            buttons.append(InlineKeyboardButton(text, callback_data=f"zodiac_{sign.split()[0]}"))
        
        for i in range(0, len(buttons), 3):
            keyboard.add(*buttons[i:i+3])
        
        keyboard.add(InlineKeyboardButton("✅ Подтвердить", callback_data="zodiac_confirm"))
        
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Ошибка обновления клавиатуры: {e}")
    
    bot.answer_callback_query(call.id)

def complete_registration(user_id, chat_id):
    """Завершает регистрацию и сохраняет профиль"""
    if user_id not in temp_data:
        bot.send_message(chat_id, "❌ Ошибка регистрации. Начните заново с /start")
        return
    
    # Создаем запись пользователя
    users_data[user_id] = {
        "balance": 10,  # Стартовый баланс
        "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "profile": temp_data[user_id]["profile"]
    }
    
    # Сохраняем данные в файл
    save_data(DATA_FILE, users_data)
    
    # Очищаем временные данные
    if user_id in temp_data:
        del temp_data[user_id]
    
    # Показываем успешную регистрацию
    profile = users_data[user_id]["profile"]
    city_text = profile.get('city', 'не указан')
    
    bot.send_message(
        chat_id,
        "🎉 *Регистрация завершена!*\n\n"
        f"👤 *Имя:* {profile['name']}\n"
        f"⚧ *Пол:* {profile['gender']}\n"
        f"🎂 *Возраст:* {profile['age']} лет\n"
        f"🏙️ *Город:* {city_text}\n"
        f"♈ *Знак зодиака:* {profile['zodiac']}\n"
        f"💰 *Баланс:* 10 монет\n\n"
        "Теперь вы можете смотреть анкеты других пользователей!",
        parse_mode="Markdown"
    )
    
    # Показываем главное меню
    show_main_menu(user_id, chat_id)
    
    # Сбрасываем состояние
    bot.delete_state(user_id, chat_id)

def show_main_menu(user_id, chat_id=None):
    """Показывает главное меню"""
    if chat_id is None:
        # Находим chat_id из данных (это упрощённо)
        # В реальном боте нужно хранить chat_id отдельно
        chat_id = user_id
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("👀 Смотреть анкеты", callback_data="browse_start"),
        InlineKeyboardButton("📊 Моя анкета", callback_data="my_profile")
    )
    keyboard.add(
        InlineKeyboardButton("💝 Проверить совместимость", callback_data="check_compatibility"),
        InlineKeyboardButton("💰 Баланс", callback_data="show_balance")
    )
    keyboard.add(
        InlineKeyboardButton("⚙️ Фильтры", callback_data="set_filters"),
        InlineKeyboardButton("❓ Помощь", callback_data="show_help")
    )
    
    bot.send_message(
        chat_id,
        "🏠 *Главное меню*\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# НОВЫЙ ОБРАБОТЧИК для взаимных лайков
@bot.callback_query_handler(func=lambda call: call.data == "show_mutual_likes")
def show_mutual_likes(call: CallbackQuery):
    user_id = str(call.from_user.id)
    
    # Находим все взаимные лайки для пользователя
    user_mutual_likes = []
    
    for mutual_key, data in likes_data.get("mutual", {}).items():
        if user_id in data["users"]:
            # Находим ID другого пользователя
            other_user_id = data["users"][0] if data["users"][1] == user_id else data["users"][1]
            user_mutual_likes.append(other_user_id)
    
    if not user_mutual_likes:
        bot.answer_callback_query(call.id, "❤️ У вас пока нет взаимных симпатий")
        return
    
    # Создаем клавиатуру с профилями
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    for other_user_id in user_mutual_likes[:10]:  # Ограничим 10 профилями
        other_profile = users_data.get(other_user_id, {}).get("profile", {})
        if other_profile:
            city_text = f" ({other_profile.get('city', '')})" if other_profile.get('city') else ""
            button_text = f"{other_profile.get('name', 'Пользователь')}{city_text}"
            keyboard.add(
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"show_mutual_profile_{other_user_id}"
                )
            )
    
    keyboard.add(InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    
    bot.edit_message_text(
        f"❤️ *Ваши взаимные симпатии*\n\n"
        f"Всего: {len(user_mutual_likes)} человек\n\n"
        f"Выберите профиль для просмотра:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    
    bot.answer_callback_query(call.id)

# Обработчик для просмотра профиля из взаимных лайков
@bot.callback_query_handler(func=lambda call: call.data.startswith("show_mutual_profile_"))
def show_mutual_profile(call: CallbackQuery):
    user_id = str(call.from_user.id)
    target_id = call.data.replace("show_mutual_profile_", "")
    
    if target_id not in users_data:
        bot.answer_callback_query(call.id, "❌ Профиль не найден")
        return
    
    user_info = users_data[target_id]
    profile = user_info["profile"]
    
    # Проверяем, есть ли взаимный лайк
    mutual_key = f"{min(user_id, target_id)}_{max(user_id, target_id)}"
    is_mutual = mutual_key in likes_data.get("mutual", {})
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    if is_mutual:
        keyboard.add(
            InlineKeyboardButton("📞 Контакты", callback_data=f"show_contacts_{target_id}"),
            InlineKeyboardButton("💝 Совместимость", callback_data=f"match_{target_id}")
        )
    
    keyboard.add(
        InlineKeyboardButton("⬅️ Назад к списку", callback_data="show_mutual_likes"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    )
    
    city_text = f"🏙️ *Город:* {profile.get('city', 'не указан')}\n" if profile.get('city') else ""
    
    caption = (
        f"👤 *{profile['name']}*\n"
        f"⚧ *Пол:* {profile['gender']}\n"
        f"🎂 *Возраст:* {profile['age']} лет\n"
        f"📅 *ДР:* {profile['birthday']}\n"
        f"{city_text}"
        f"♈ *Знак зодиака:* {profile['zodiac']}\n\n"
        f"📝 *О себе:*\n{profile['bio']}\n\n"
    )
    
    if is_mutual:
        caption += "💖 *Взаимная симпатия!* Вы можете связаться с этим пользователем."
    else:
        caption += "⚠️ *Нет взаимной симпатии*"
    
    if 'photo_id' in profile:
        bot.send_photo(
            call.message.chat.id,
            profile['photo_id'],
            caption=caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        bot.send_message(
            call.message.chat.id,
            caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    bot.answer_callback_query(call.id)

# Обработчик для показа контактов
@bot.callback_query_handler(func=lambda call: call.data.startswith("show_contacts_"))
def show_contacts(call: CallbackQuery):
    user_id = str(call.from_user.id)
    target_id = call.data.replace("show_contacts_", "")
    
    # Проверяем, есть ли взаимный лайк
    mutual_key = f"{min(user_id, target_id)}_{max(user_id, target_id)}"
    is_mutual = mutual_key in likes_data.get("mutual", {})
    
    if not is_mutual:
        bot.answer_callback_query(call.id, "❌ Нет взаимной симпатии")
        return
    
    # Получаем username или ID пользователя
    try:
        # Пытаемся получить информацию о пользователе
        target_user = bot.get_chat(target_id)
        username = f"@{target_user.username}" if target_user.username else f"ID: {target_id}"
        
        bot.send_message(
            call.message.chat.id,
            f"📞 *Контакты пользователя*\n\n"
            f"👤 Имя: {users_data[target_id]['profile']['name']}\n"
            f"🔗 Ссылка: {username}\n\n"
            f"💬 *Как начать общение:*\n"
            f"1. Нажмите на ссылку выше\n"
            f"2. Напишите приветственное сообщение\n"
            f"3. Будьте вежливы и уважительны\n\n"
            f"✨ Удачи в общении!",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Ошибка получения информации о пользователе: {e}")
        bot.send_message(
            call.message.chat.id,
            f"📞 *Контакты пользователя*\n\n"
            f"👤 Имя: {users_data[target_id]['profile']['name']}\n"
            f"🔗 ID: {target_id}\n\n"
            f"Чтобы связаться, скопируйте ID выше и используйте поиск в Telegram.",
            parse_mode="Markdown"
        )
    
    bot.answer_callback_query(call.id)

# Моя анкета
@bot.callback_query_handler(func=lambda call: call.data == "my_profile")
def show_my_profile(call: CallbackQuery):
    user_id = str(call.from_user.id)
    
    if user_id not in users_data:
        bot.answer_callback_query(call.id, "❌ Анкета не найдена! Начните с /start")
        return
    
    user_info = users_data[user_id]
    profile = user_info["profile"]
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✏️ Редактировать анкету", callback_data="edit_profile"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    )
    
    city_text = f"🏙️ *Город:* {profile.get('city', 'не указан')}\n" if profile.get('city') else ""
    
    caption = (
        f"👤 *{profile['name']}*\n"
        f"⚧ *Пол:* {profile['gender']}\n"
        f"🎂 *Возраст:* {profile['age']} лет\n"
        f"📅 *ДР:* {profile['birthday']}\n"
        f"{city_text}"
        f"♈ *Знак зодиака:* {profile['zodiac']}\n\n"
        f"📝 *О себе:*\n{profile['bio']}\n\n"
        f"💰 *Баланс:* {user_info['balance']} монет\n"
        f"❤️ *Взаимных симпатий:* {get_mutual_count(user_id)}"
    )
    
    if 'photo_id' in profile:
        bot.send_photo(
            call.message.chat.id,
            profile['photo_id'],
            caption=caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        bot.send_message(
            call.message.chat.id,
            caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    bot.answer_callback_query(call.id)

def get_mutual_count(user_id):
    """Возвращает количество взаимных симпатий"""
    count = 0
    for mutual_key, data in likes_data.get("mutual", {}).items():
        if user_id in data["users"]:
            count += 1
    return count

# Обработчик для показа профиля (общий)
@bot.callback_query_handler(func=lambda call: call.data.startswith("show_profile_"))
def show_profile_handler(call: CallbackQuery):
    user_id = str(call.from_user.id)
    target_id = call.data.replace("show_profile_", "")
    
    if target_id not in users_data:
        bot.answer_callback_query(call.id, "❌ Профиль не найден")
        return
    
    user_info = users_data[target_id]
    profile = user_info["profile"]
    
    city_text = f"🏙️ *Город:* {profile.get('city', 'не указан')}\n" if profile.get('city') else ""
    
    caption = (
        f"👤 *{profile['name']}*\n"
        f"⚧ *Пол:* {profile['gender']}\n"
        f"🎂 *Возраст:* {profile['age']} лет\n"
        f"📅 *ДР:* {profile['birthday']}\n"
        f"{city_text}"
        f"♈ *Знак зодиака:* {profile['zodiac']}\n\n"
        f"📝 *О себе:*\n{profile['bio']}"
    )
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    
    if 'photo_id' in profile:
        bot.send_photo(
            call.message.chat.id,
            profile['photo_id'],
            caption=caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        bot.send_message(
            call.message.chat.id,
            caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    bot.answer_callback_query(call.id)


# Начать просмотр анкет
# Начать просмотр анкет с учетом города
@bot.callback_query_handler(func=lambda call: call.data == "browse_start")
def start_browsing(call: CallbackQuery):
    user_id = str(call.from_user.id)
    
    if user_id not in users_data:
        bot.answer_callback_query(call.id, "❌ Сначала создайте анкету через /start")
        return
    
    user_city = users_data[user_id]["profile"].get("city")
    
    # Получаем список анкет (кроме своей)
    all_user_ids = list(users_data.keys())
    other_user_ids = [uid for uid in all_user_ids if uid != user_id]
    
    if not other_user_ids:
        bot.answer_callback_query(call.id, "😔 Пока нет других анкет")
        return
    
    # Сортируем анкеты: сначала из того же города, потом остальные
    if user_city:
        same_city_ids = []
        other_city_ids = []
        
        for uid in other_user_ids:
            if users_data[uid]["profile"].get("city") == user_city:
                same_city_ids.append(uid)
            else:
                other_city_ids.append(uid)
        
        # Перемешиваем внутри каждой группы для разнообразия
        random.shuffle(same_city_ids)
        random.shuffle(other_city_ids)
        
        other_user_ids = same_city_ids + other_city_ids
    else:
        # Если город не указан, просто перемешиваем все анкеты
        random.shuffle(other_user_ids)
    
    # Инициализируем очередь просмотра
    if 'browse_queue' not in temp_data.get(user_id, {}):
        temp_data[user_id] = temp_data.get(user_id, {})
    
    temp_data[user_id]['browse_queue'] = other_user_ids.copy()
    temp_data[user_id]['current_index'] = 0
    temp_data[user_id]['filter_gender'] = None
    temp_data[user_id]['filter_zodiac'] = None
    temp_data[user_id]['filter_city'] = None
    
    show_next_profile(user_id, call.message.chat.id)
    bot.answer_callback_query(call.id)

# def show_next_profile(user_id, chat_id, edit_message=False):
#     """Показывает следующую анкету"""
#     if user_id not in temp_data or 'browse_queue' not in temp_data[user_id]:
#         bot.send_message(chat_id, "❌ Ошибка. Начните просмотр заново.")
#         return
    
#     queue = temp_data[user_id]['browse_queue']
#     current_idx = temp_data[user_id].get('current_index', 0)
    
#     # Если дошли до конца
#     if current_idx >= len(queue):
#         keyboard = InlineKeyboardMarkup(row_width=2)
#         keyboard.add(
#             InlineKeyboardButton("🔄 Начать заново", callback_data="browse_start"),
#             InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
#         )
        
#         if edit_message and 'last_message_id' in temp_data[user_id]:
#             try:
#                 # Проверяем, что сообщение существует и является текстовым
#                 bot.edit_message_text(
#                     "🎉 *Вы просмотрели все анкеты!*\n\n"
#                     "Нажмите 'Начать заново', чтобы посмотреть снова.",
#                     chat_id=chat_id,
#                     message_id=temp_data[user_id]['last_message_id'],
#                     parse_mode="Markdown",
#                     reply_markup=keyboard
#                 )
#             except Exception as e:
#                 # Если не удалось отредактировать, отправляем новое сообщение
#                 print(f"Ошибка редактирования сообщения: {e}")
#                 msg = bot.send_message(
#                     chat_id,
#                     "🎉 *Вы просмотрели все анкеты!*\n\n"
#                     "Нажмите 'Начать заново', чтобы посмотреть снова.",
#                     parse_mode="Markdown",
#                     reply_markup=keyboard
#                 )
#                 temp_data[user_id]['last_message_id'] = msg.message_id
#         else:
#             msg = bot.send_message(
#                 chat_id,
#                 "🎉 *Вы просмотрели все анкеты!*\n\n"
#                 "Нажмите 'Начать заново', чтобы посмотреть снова.",
#                 parse_mode="Markdown",
#                 reply_markup=keyboard
#             )
#             temp_data[user_id]['last_message_id'] = msg.message_id
#         return
    
#     profile_id = queue[current_idx]
#     user_info = users_data[profile_id]
#     profile = user_info["profile"]
    
#     # Применяем фильтры
#     if temp_data[user_id].get('filter_gender') and profile['gender'] != temp_data[user_id]['filter_gender']:
#         temp_data[user_id]['current_index'] += 1
#         show_next_profile(user_id, chat_id, edit_message)
#         return
    
#     if temp_data[user_id].get('filter_zodiac') and profile['zodiac'] != temp_data[user_id]['filter_zodiac']:
#         temp_data[user_id]['current_index'] += 1
#         show_next_profile(user_id, chat_id, edit_message)
#         return
    
#     # Создаем клавиатуру для анкеты
#     keyboard = InlineKeyboardMarkup(row_width=2)
#     keyboard.add(
#         InlineKeyboardButton("💝 Совместимость", callback_data=f"match_{profile_id}"),
#         InlineKeyboardButton("❤️ Лайк", callback_data=f"like_{profile_id}")
#     )
#     keyboard.add(
#         InlineKeyboardButton("➡️ Дальше", callback_data="browse_next"),
#     )
#     keyboard.add(
#         InlineKeyboardButton("⚙️ Фильтры", callback_data="set_filters"),
#         InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
#     )
    
#     caption = (
#         f"👤 *{profile['name']}*\n"
#         f"⚧ *Пол:* {profile['gender']}\n"
#         f"🎂 *Возраст:* {profile['age']} лет\n"
#         f"♈ *Знак зодиака:* {profile['zodiac']}\n\n"
#         f"📝 *О себе:*\n{profile['bio']}\n\n"
#         f"Анкета {current_idx + 1} из {len(queue)}"
#     )
    
#     if edit_message and 'last_message_id' in temp_data[user_id]:
#         try:
#             # Пытаемся удалить предыдущее сообщение с фото
#             bot.delete_message(chat_id, temp_data[user_id]['last_message_id'])
#         except:
#             pass  # Если не удалось удалить, продолжаем
        
#         if 'photo_id' in profile:
#             try:
#                 msg = bot.send_photo(
#                     chat_id,
#                     profile['photo_id'],
#                     caption=caption,
#                     parse_mode="Markdown",
#                     reply_markup=keyboard
#                 )
#             except Exception as e:
#                 print(f"Ошибка отправки фото: {e}")
#                 msg = bot.send_message(
#                     chat_id,
#                     caption,
#                     parse_mode="Markdown",
#                     reply_markup=keyboard
#                 )
#         else:
#             msg = bot.send_message(
#                 chat_id,
#                 caption,
#                 parse_mode="Markdown",
#                 reply_markup=keyboard
#             )
#     else:
#         if 'photo_id' in profile:
#             msg = bot.send_photo(
#                 chat_id,
#                 profile['photo_id'],
#                 caption=caption,
#                 parse_mode="Markdown",
#                 reply_markup=keyboard
#             )
#         else:
#             msg = bot.send_message(
#                 chat_id,
#                 caption,
#                 parse_mode="Markdown",
#                 reply_markup=keyboard
#             )
    
#     if msg:
#         temp_data[user_id]['last_message_id'] = msg.message_id

def show_next_profile(user_id, chat_id, edit_message=False):
    """Показывает следующую анкету с учетом фильтров"""
    if user_id not in temp_data or 'browse_queue' not in temp_data[user_id]:
        bot.send_message(chat_id, "❌ Ошибка. Начните просмотр заново.")
        return
    
    queue = temp_data[user_id]['browse_queue']
    current_idx = temp_data[user_id].get('current_index', 0)
    
    # Пытаемся найти подходящую анкету
    profile_found = False
    profile_id = None
    user_info = None
    profile = None
    
    while current_idx < len(queue) and not profile_found:
        profile_id = queue[current_idx]
        user_info = users_data[profile_id]
        profile = user_info["profile"]
        
        # Применяем фильтры
        filter_passed = True
        
        # Фильтр по полу
        if temp_data[user_id].get('filter_gender') and profile['gender'] != temp_data[user_id]['filter_gender']:
            filter_passed = False
        
        # Фильтр по знаку зодиака
        if filter_passed and temp_data[user_id].get('filter_zodiac') and profile['zodiac'] != temp_data[user_id]['filter_zodiac']:
            filter_passed = False
        
        # Фильтр по городу
        if filter_passed and temp_data[user_id].get('filter_city'):
            if temp_data[user_id]['filter_city'] == "same_city":
                # Показывать только из своего города
                user_city = users_data[user_id]["profile"].get("city")
                if profile.get('city') != user_city:
                    filter_passed = False
            elif temp_data[user_id]['filter_city'] == "any_city":
                # Показывать из любого города (без фильтра)
                pass
        
        if filter_passed:
            profile_found = True
        else:
            current_idx += 1
    
    if not profile_found:
        # Если не нашли подходящих анкет
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("🔄 Начать заново", callback_data="browse_start"),
            InlineKeyboardButton("⚙️ Изменить фильтры", callback_data="set_filters"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        )
        
        response_text = "🎉 *Вы просмотрели все подходящие анкеты!*\n\n"
        if temp_data[user_id].get('filter_gender') or temp_data[user_id].get('filter_zodiac') or temp_data[user_id].get('filter_city'):
            response_text += "Попробуйте изменить фильтры, чтобы увидеть больше анкет."
        else:
            response_text += "Нажмите 'Начать заново', чтобы посмотреть снова."
        
        if edit_message and 'last_message_id' in temp_data[user_id]:
            try:
                bot.edit_message_text(
                    response_text,
                    chat_id=chat_id,
                    message_id=temp_data[user_id]['last_message_id'],
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except Exception as e:
                msg = bot.send_message(
                    chat_id,
                    response_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                temp_data[user_id]['last_message_id'] = msg.message_id
        else:
            msg = bot.send_message(
                chat_id,
                response_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            temp_data[user_id]['last_message_id'] = msg.message_id
        return
    
    # Обновляем индекс
    temp_data[user_id]['current_index'] = current_idx + 1
    
    # Отмечаем, из одного ли города
    user_city = users_data[user_id]["profile"].get("city")
    profile_city = profile.get('city')
    city_info = ""
    
    if user_city and profile_city:
        if user_city == profile_city:
            city_info = f"📍 *Из вашего города ({user_city})*\n\n"
        else:
            city_info = f"📍 *Город:* {profile_city}\n\n"
    elif profile_city:
        city_info = f"📍 *Город:* {profile_city}\n\n"
    
    # Создаем клавиатуру для анкеты
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("💝 Совместимость", callback_data=f"match_{profile_id}"),
        InlineKeyboardButton("❤️ Лайк", callback_data=f"like_{profile_id}")
    )
    keyboard.add(
        InlineKeyboardButton("➡️ Дальше", callback_data="browse_next"),
    )
    keyboard.add(
        InlineKeyboardButton("⚙️ Фильтры", callback_data="set_filters"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    )
    
    caption = (
        f"{city_info}"
        f"👤 *{profile['name']}*\n"
        f"⚧ *Пол:* {profile['gender']}\n"
        f"🎂 *Возраст:* {profile['age']} лет\n"
        f"♈ *Знак зодиака:* {profile['zodiac']}\n\n"
        f"📝 *О себе:*\n{profile['bio']}\n\n"
        f"Анкета {current_idx + 1} из {len(queue)}"
    )
    
    if edit_message and 'last_message_id' in temp_data[user_id]:
        try:
            bot.delete_message(chat_id, temp_data[user_id]['last_message_id'])
        except:
            pass
        
        if 'photo_id' in profile:
            try:
                msg = bot.send_photo(
                    chat_id,
                    profile['photo_id'],
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except Exception as e:
                msg = bot.send_message(
                    chat_id,
                    caption,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
        else:
            msg = bot.send_message(
                chat_id,
                caption,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
    else:
        if 'photo_id' in profile:
            msg = bot.send_photo(
                chat_id,
                profile['photo_id'],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            msg = bot.send_message(
                chat_id,
                caption,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
    
    if msg:
        temp_data[user_id]['last_message_id'] = msg.message_id


# Обработка действий с анкетами
@bot.callback_query_handler(func=lambda call: call.data.startswith(("match_", "like_", "skip_", "browse_next")))
def handle_profile_actions(call: CallbackQuery):
    user_id = str(call.from_user.id)
    
    if call.data == "browse_next":
        # Показываем следующую анкету
        temp_data[user_id]['current_index'] += 1
        try:
            show_next_profile(user_id, call.message.chat.id, edit_message=True)
        except Exception as e:
            print(f"Ошибка показа следующей анкеты: {e}")
            bot.answer_callback_query(call.id, "❌ Ошибка, начните заново")
            return
        bot.answer_callback_query(call.id)
    
    elif call.data.startswith("match_"):
        # Проверка совместимости
        target_id = call.data.replace("match_", "")
        
        if users_data[user_id]['balance'] < MATCH_PRICE:
            bot.answer_callback_query(call.id, f"❌ Недостаточно средств! Нужно: {MATCH_PRICE} монет")
            return
        
        # Списываем средства
        users_data[user_id]['balance'] -= MATCH_PRICE
        save_data(DATA_FILE, users_data)
        
        # Рассчитываем совместимость
        try:
            date1 = users_data[user_id]["profile"]['birthday']
            date2 = users_data[target_id]["profile"]['birthday']
            result = calculate_compatibility(date1, date2)
            
            response = (
                f"💝 *Совместимость с {users_data[target_id]['profile']['name']}*\n\n"
                f"📅 Ваша дата: `{date1}`\n"
                f"📅 Его/её дата: `{date2}`\n"
                f"🎯 *Общая совместимость:* `{result['percentage']:.1f}%`\n\n"
                f"📊 *Детали:*\n"
                f"• Матрица: `{result['details']['matrix_score']:.1f}%`\n"
                f"• Стихии: `{result['details']['elements_score']:.1f}%`\n"
                f"• Ключевые числа: `{result['details']['key_numbers_score']:.1f}%`\n\n"
                f"💰 *Списано:* {MATCH_PRICE} монет\n"
                f"💵 *Осталось:* {users_data[user_id]['balance']} монет"
            )
            
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, response, parse_mode="Markdown")
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Ошибка расчёта: {str(e)}")
    
    elif call.data.startswith("like_"):
        user_id = str(call.from_user.id)
        target_id = call.data.replace("like_", "")
        
        # Проверяем взаимный лайк
        is_mutual = check_mutual_like(user_id, target_id)
        
        if is_mutual:
            bot.answer_callback_query(call.id, "💖 Взаимная симпатия! Уведомление отправлено.")
        else:
            bot.answer_callback_query(call.id, "❤️ Лайк отправлен!")
        
        # Показываем следующую анкету
        temp_data[user_id]['current_index'] += 1
        try:
            show_next_profile(user_id, call.message.chat.id, edit_message=True)
        except Exception as e:
            print(f"Ошибка показа следующей анкеты: {e}")
    
# Настройка фильтров
@bot.callback_query_handler(func=lambda call: call.data == "set_filters")
def set_filters(call: CallbackQuery):
    user_id = str(call.from_user.id)
    user_city = users_data[user_id]["profile"].get("city") if user_id in users_data else None
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    # Фильтры по полу
    gender_filter = temp_data.get(user_id, {}).get('filter_gender')
    gender_buttons = [
        InlineKeyboardButton(
            f"{'✅ ' if gender_filter == 'Мужской' else ''}👨 Мужской",
            callback_data="filter_gender_m"
        ),
        InlineKeyboardButton(
            f"{'✅ ' if gender_filter == 'Женский' else ''}👩 Женский",
            callback_data="filter_gender_f"
        ),
        InlineKeyboardButton(
            "❌ Без фильтра" if gender_filter else "✅ Без фильтра",
            callback_data="filter_gender_none"
        )
    ]

    # Фильтры по городу (только если пользователь указал город)
    city_filter = temp_data.get(user_id, {}).get('filter_city')
    city_buttons = []
    
    if user_city:
        city_buttons.append(InlineKeyboardButton(
            f"{'✅ ' if city_filter == 'same_city' else ''}📍 Только {user_city}",
            callback_data="filter_city_same"
        ))
    
    city_buttons.append(InlineKeyboardButton(
        f"{'✅ ' if city_filter == 'any_city' or (not city_filter and not user_city) else ''}🌍 Любой город",
        callback_data="filter_city_any"
    ))
    
    city_buttons.append(InlineKeyboardButton(
        "❌ Без фильтра" if city_filter else "✅ Без фильтра",
        callback_data="filter_city_none"
    ))
    
    # Фильтры по знаку зодиака
    zodiac_filter = temp_data.get(user_id, {}).get('filter_zodiac')
    zodiac_buttons = []
    
    zodiac_buttons.append(InlineKeyboardButton(
        "❌ Без фильтра" if zodiac_filter else "✅ Без фильтра",
        callback_data="filter_zodiac_none"
    ))
    
    # Добавляем по 3 знака в ряд
    for i in range(0, len(ZODIAC_SIGNS), 3):
        row_signs = ZODIAC_SIGNS[i:i+3]
        row_buttons = []
        for sign in row_signs:
            is_selected = zodiac_filter == sign
            row_buttons.append(InlineKeyboardButton(
                f"{'✅ ' if is_selected else ''}{sign}",
                callback_data=f"filter_zodiac_{sign.split()[0]}"
            ))
        zodiac_buttons.extend(row_buttons)
    
     # Собираем клавиатуру
    keyboard.add(InlineKeyboardButton("👥 ПОЛ", callback_data="none"))
    for i in range(0, len(gender_buttons), 3):
        keyboard.add(*gender_buttons[i:i+3])
    
    if user_city:
        keyboard.add(InlineKeyboardButton("🏙️ ГОРОД", callback_data="none"))
        for i in range(0, len(city_buttons), 3):
            keyboard.add(*city_buttons[i:i+3])
    
    keyboard.add(InlineKeyboardButton("♈ ЗНАК ЗОДИАКА", callback_data="none"))
    for i in range(0, len(zodiac_buttons), 3):
        if i + 3 <= len(zodiac_buttons):
            keyboard.add(*zodiac_buttons[i:i+3])
    
    keyboard.add(
        InlineKeyboardButton("💾 Сохранить фильтры", callback_data="save_filters"),
        InlineKeyboardButton("↩️ Назад к анкетам", callback_data="back_to_browse")
    )
    
    current_filters = []
    if gender_filter:
        current_filters.append(f"Пол: {gender_filter}")
    if city_filter:
        if city_filter == "same_city" and user_city:
            current_filters.append(f"Город: только {user_city}")
        elif city_filter == "any_city":
            current_filters.append("Город: любой")
    if zodiac_filter:
        current_filters.append(f"Знак: {zodiac_filter}")
    
    filters_text = "Нет фильтров" if not current_filters else "\n".join(current_filters)
    
    try:
        bot.edit_message_text(
            f"⚙️ *Настройка фильтров*\n\n"
            f"Текущие фильтры:\n{filters_text}\n\n"
            "Выберите параметры фильтрации:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except Exception as e:
        bot.send_message(
            call.message.chat.id,
            f"⚙️ *Настройка фильтров*\n\n"
            f"Текущие фильтры:\n{filters_text}\n\n"
            "Выберите параметры фильтрации:",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    
    bot.answer_callback_query(call.id)

# Обновленный обработчик выбора фильтров с полной защитой
@bot.callback_query_handler(func=lambda call: call.data.startswith("filter_"))
def handle_filter_selection(call: CallbackQuery):
    user_id = str(call.from_user.id)
    
    try:
        # Инициализируем temp_data для пользователя, если его нет
        if user_id not in temp_data:
            temp_data[user_id] = {}
        
        # Инициализируем подструктуры, если их нет
        if call.data.startswith("filter_gender_"):
            gender_map = {
                "filter_gender_m": "Мужской",
                "filter_gender_f": "Женский",
                "filter_gender_none": None
            }
            temp_data[user_id]['filter_gender'] = gender_map.get(call.data)
        
        elif call.data.startswith("filter_city_"):
            if call.data == "filter_city_none":
                temp_data[user_id]['filter_city'] = None
            elif call.data == "filter_city_same":
                temp_data[user_id]['filter_city'] = "same_city"
            elif call.data == "filter_city_any":
                temp_data[user_id]['filter_city'] = "any_city"
        
        elif call.data.startswith("filter_zodiac_"):
            if call.data == "filter_zodiac_none":
                temp_data[user_id]['filter_zodiac'] = None
            else:
                zodiac_name = call.data.replace("filter_zodiac_", "")
                for sign in ZODIAC_SIGNS:
                    if zodiac_name in sign:
                        temp_data[user_id]['filter_zodiac'] = sign
                        break
        
        # Обновляем интерфейс фильтров
        try:
            set_filters(call)
        except Exception as e:
            print(f"Ошибка обновления фильтров: {e}")
            bot.answer_callback_query(call.id, "✅ Фильтр обновлён")
            
    except Exception as e:
        print(f"Критическая ошибка в handle_filter_selection: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка. Попробуйте снова.")

@bot.callback_query_handler(func=lambda call: call.data == "save_filters")
def save_filters(call: CallbackQuery):
    user_id = str(call.from_user.id)
    
    # Сбрасываем индекс просмотра при сохранении фильтров
    if user_id in temp_data and 'browse_queue' in temp_data[user_id]:
        temp_data[user_id]['current_index'] = 0
    
    bot.answer_callback_query(call.id, "✅ Фильтры сохранены!")
    # Возвращаемся к просмотру
    if user_id in temp_data and 'last_message_id' in temp_data[user_id]:
        show_next_profile(user_id, call.message.chat.id, edit_message=True)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_browse")
def back_to_browse(call: CallbackQuery):
    user_id = str(call.from_user.id)
    if user_id in temp_data and 'last_message_id' in temp_data[user_id]:
        try:
            show_next_profile(user_id, call.message.chat.id, edit_message=True)
        except Exception as e:
            print(f"Ошибка возврата к анкетам: {e}")
            bot.answer_callback_query(call.id, "❌ Ошибка, начните заново")
            return
    bot.answer_callback_query(call.id)

# Проверка совместимости (отдельная команда)
@bot.callback_query_handler(func=lambda call: call.data == "check_compatibility")
def check_compatibility_menu(call: CallbackQuery):
    user_id = str(call.from_user.id)
    
    if user_id not in users_data:
        bot.answer_callback_query(call.id, "❌ Сначала создайте анкету через /start")
        return
    
    bot.send_message(
        call.message.chat.id,
        f"💝 *Проверка совместимости по Матрице Судьбы*\n\n"
        f"Стоимость проверки: {MATCH_PRICE} монет\n"
        f"Ваш баланс: {users_data[user_id]['balance']} монет\n\n"
        "Введите первую дату рождения в формате:\n"
        "`ДД.ММ.ГГГГ`\n\n"
        "*Пример:* `15.04.1986`",
        parse_mode="Markdown"
    )
    
    bot.set_state(user_id, MatchStates.waiting_date1, call.message.chat.id)
    bot.answer_callback_query(call.id)

# Главное меню callback
@bot.callback_query_handler(func=lambda call: call.data in ["main_menu", "show_balance", "show_help", "edit_profile"])
def handle_main_menu(call: CallbackQuery):
    user_id = str(call.from_user.id)
    
    if call.data == "main_menu":
        show_main_menu(user_id, call.message.chat.id)
    elif call.data == "show_balance":
        if user_id in users_data:
            bot.answer_callback_query(
                call.id,
                f"💰 Баланс: {users_data[user_id]['balance']} монет",
                show_alert=True
            )
        else:
            bot.answer_callback_query(call.id, "❌ Сначала создайте анкету через /start")
    elif call.data == "show_help":
        help_text = (
            "🤖 *Бот для знакомств с Матрицей Судьбы*\n\n"
            "*Основные функции:*\n"
            "• 👀 *Смотреть анкеты* - просмотр анкет других пользователей\n"
            "• 💝 *Проверить совместимость* - расчет по Матрице Судьбы\n"
            "• 💰 *Баланс* - проверка баланса монет\n"
            "• ⚙️ *Фильтры* - настройка фильтров поиска\n\n"
            "*Как работает:*\n"
            "1. Создайте анкету с фото и информацией\n"
            "2. Смотрите анкеты других пользователей\n"
            "3. Проверяйте совместимость (стоимость: 1 монета)\n"
            "4. Ставьте лайки интересным людям\n\n"
            "*Знаки зодиака:*\n"
            "Вы можете фильтровать анкеты по знаку зодиака\n\n"
            "Для начала используйте /start"
        )
        bot.send_message(call.message.chat.id, help_text, parse_mode="Markdown")
    elif call.data == "edit_profile":
        bot.send_message(call.message.chat.id, "✏️ *Редактирование анкеты*\n\nДля редактирования анкеты удалите её и создайте заново с помощью /start", parse_mode="Markdown")
    
    bot.answer_callback_query(call.id)

# Функции для работы с матрицей (остаются из предыдущего кода)
def validate_date(date_str):
    """Проверяет корректность формата даты"""
    try:
        day, month, year = map(int, date_str.split('.'))
        
        if not (1 <= day <= 31):
            return False
        if not (1 <= month <= 12):
            return False
        if not (1900 <= year <= 2100):
            return False
            
        datetime(year, month, day)
        return True
    except:
        return False

# Обработка команд матрицы
@bot.message_handler(state=MatchStates.waiting_date1)
def get_date1_match(message: Message):
    """Получаем первую дату для матрицы"""
    user_id = str(message.from_user.id)
    date_str = message.text.strip()
    
    if not validate_date(date_str):
        bot.send_message(
            message.chat.id,
            "❌ *Неверный формат даты!*\n\n"
            "Пожалуйста, введите дату в формате:\n"
            "`ДД.ММ.ГГГГ`\n\n"
            "*Пример:* `15.04.1986`",
            parse_mode="Markdown"
        )
        return
    
    # Проверяем баланс
    if users_data[user_id]['balance'] < MATCH_PRICE:
        bot.send_message(message.chat.id, f"❌ Недостаточно средств! Нужно: {MATCH_PRICE} монет")
        bot.delete_state(user_id, message.chat.id)
        return
    
    # Списываем средства
    users_data[user_id]['balance'] -= MATCH_PRICE
    save_data(DATA_FILE, users_data)
    
    # Сохраняем первую дату
    temp_data[user_id] = temp_data.get(user_id, {})
    temp_data[user_id]['match_date1'] = date_str
    
    bot.send_message(
        message.chat.id,
        f"✅ Первая дата сохранена: `{date_str}`\n"
        f"💰 Списано: {MATCH_PRICE} монет\n"
        f"💵 Осталось: {users_data[user_id]['balance']} монет\n\n"
        "Теперь введите вторую дату рождения в том же формате:",
        parse_mode="Markdown"
    )
    
    bot.set_state(user_id, MatchStates.waiting_date2, message.chat.id)

@bot.message_handler(state=MatchStates.waiting_date2)
def get_date2_and_calculate_match(message: Message):
    """Получаем вторую дату и рассчитываем совместимость"""
    user_id = str(message.from_user.id)
    date_str = message.text.strip()
    
    if not validate_date(date_str):
        bot.send_message(
            message.chat.id,
            "❌ *Неверный формат даты!*\n\n"
            "Пожалуйста, введите дату в формате:\n"
            "`ДД.ММ.ГГГГ`",
            parse_mode="Markdown"
        )
        return
    
    date1 = temp_data[user_id]['match_date1']
    
    try:
        # Рассчитываем совместимость
        result = calculate_compatibility(date1, date_str)
        
        # Форматируем результат
        response = format_match_result(date1, date_str, result)
        
        # Отправляем результат
        bot.send_message(message.chat.id, response, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ *Произошла ошибка при расчёте:*\n`{str(e)}`\n\n"
            "Попробуйте ещё раз или обратитесь к администратору.",
            parse_mode="Markdown"
        )
        # Возвращаем средства при ошибке
        users_data[user_id]['balance'] += MATCH_PRICE
        save_data(DATA_FILE, users_data)
    
    # Сбрасываем состояние
    bot.delete_state(user_id, message.chat.id)
    # Показываем главное меню
    show_main_menu(user_id, message.chat.id)

def format_match_result(date1, date2, result):
    """Форматирует результат совместимости"""
    matrix_score = result['details']['matrix_score']
    
    # Определяем уровень совместимости по МАТРИЦЕ
    if matrix_score >= 85:
        level = "✨ *ИДЕАЛЬНАЯ*"
        emoji = "💖"
        advice = "Отличная совместимость во всех сферах жизни!"
    elif matrix_score >= 70:
        level = "✅ *ВЫСОКАЯ*"
        emoji = "💕"
        advice = "Хорошая база для гармоничных отношений."
    elif matrix_score >= 55:
        level = "⚠️ *СРЕДНЯЯ*"
        emoji = "💛"
        advice = "Есть потенциал, но нужна работа над отношениями."
    elif matrix_score >= 40:
        level = "🔶 *НИЗКАЯ*"
        emoji = "💔"
        advice = "Потребуются значительные усилия для гармонии."
    else:
        level = "❌ *КРИТИЧЕСКАЯ*"
        emoji = "⚡"
        advice = "Сложные отношения, нужна большая работа."
    
    return (
        f"{emoji} *РЕЗУЛЬТАТ СОВМЕСТИМОСТИ*\n\n"
        f"📅 *Дата 1:* `{date1}`\n"
        f"📅 *Дата 2:* `{date2}`\n"
        f"🎯 *Главный показатель (МАТРИЦА):* `{matrix_score:.1f}%`\n"
        f"🏆 *Уровень совместимости:* {level}\n\n"
        f"📊 *Детали:*\n"
        f"• Матрица: `{result['details']['matrix_score']:.1f}%`\n"
        f"• Стихии: `{result['details']['elements_score']:.1f}%`\n"
        f"• Ключевые числа: `{result['details']['key_numbers_score']:.1f}%`\n\n"
        f"💡 *Совет:* {advice}"
    )

# Команды для помощи
@bot.message_handler(commands=["help"])
def help_command(message: Message):
    help_text = """
🤖 *Доступные команды:*

*Основные:*
/start - регистрация и создание анкеты
/help - эта справка
/balance - проверить баланс

*Для просмотра анкет:*
Используйте кнопки в меню:
• 👀 Смотреть анкеты
• 💝 Проверить совместимость
• ⚙️ Фильтры

*Формат даты для проверки совместимости:*
ДД.ММ.ГГГГ
Пример: 29.06.2007 или 15.04.1986
"""
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=["balance"])
def balance_command(message: Message):
    user_id = str(message.from_user.id)
    
    if user_id in users_data:
        bot.send_message(
            message.chat.id,
            f"💰 *Ваш баланс:* {users_data[user_id]['balance']} монет",
            parse_mode="Markdown"
        )
    else:
        bot.send_message(message.chat.id, "❌ Сначала создайте анкету через /start")

# Запуск бота
if __name__ == "__main__":
    bot.add_custom_filter(StateFilter(bot))
    
    print("🤖 Бот для знакомств запущен!")
    print("📁 Данные сохраняются в users_data.json")
    print("✨ Основные функции:")
    print("  • Регистрация с фото и знаком зодиака")
    print("  • Просмотр анкет с фильтрами")
    print("  • Проверка совместимости по Матрице Судьбы")
    
    bot.polling(none_stop=True)