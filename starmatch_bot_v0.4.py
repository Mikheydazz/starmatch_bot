import telebot
import time
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
from database import Database
import threading
import requests
from io import BytesIO

# Настраиваем логирование
logging.basicConfig(
    level=logging.WARNING,  # Только важные сообщения
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Уменьшаем уровень логирования для telebot
logging.getLogger('telebot').setLevel(logging.WARNING)

TOKEN = "8532351328:AAHzg51PtkeG8VNEN-QD3siT5O9vxTHx4-I"
GROUP_ID = -1001928901997
MECHANIC_PRICE = 5
MATCH_PRICE = 0  # стоимость проверки совместимости

REQUIRED_CHANNEL = "@StarrMatch"  # Или ID: -1001234567890
CHANNEL_INVITE_LINK = "https://t.me/StarrMatch"  # Ссылка для вступления
CHANNEL_NAME = "StarMatch"
CHANNEL_IS_NEEDED = False

# Кэш для хранения результатов проверки (чтобы не проверять каждый раз)
subscription_cache = {}
CACHE_DURATION = 3600  # 1 час в секундах

# Настройки платежей
PAYMENT_PROVIDER_TOKEN = "YOUR_PAYMENT_PROVIDER_TOKEN"  # Получите у @BotFather
ADMIN_USER_ID = '1734217491'  # Ваш Telegram ID для уведомлений
ADMINS = {1734217491, 5503413808}  # Telegram ID

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

bot = telebot.TeleBot(TOKEN)

# Инициализация базы данных
db = Database('bot_database.db', photos_dir='user_photos')

# Хранилище для временных данных
temp_data = {}
temp_data_lock = threading.Lock()  # Для безопасного доступа к temp_data

# Пакеты монет для покупки
COIN_PACKAGES = {
    "small": {
        "coins": 50,
        "price": 1,  # в рублях
        "label": "💰 50 монет",
        "description": "50 монет для проверки совместимости"
    },
    "medium": {
        "coins": 120,
        "price": 199,
        "label": "💰 120 монет",
        "description": "120 монет (экономия 20%)"
    },
    "large": {
        "coins": 300,
        "price": 399,
        "label": "💰 300 монет",
        "description": "300 монет (экономия 33%)"
    },
    "premium": {
        "coins": 1000,
        "price": 999,
        "label": "💰 1000 монет",
        "description": "1000 монет (максимальная экономия)"
    }
}

# === НАСТРОЙКА БОТ-МЕНЮ (квадратик справа снизу) ===
def setup_bot_menu():
    """Настраивает меню команд бота"""
    menu_commands = [
        types.BotCommand("start", "🚀 Начать/перезапустить бота"),
        types.BotCommand("balance", "💰 Проверить баланс"),
        types.BotCommand("myprofile", "👤 Моя анкета"),
        types.BotCommand("help", "❓ Помощь и инструкции"),
        types.BotCommand("browse", "👀 Начать просмотр анкет"),
        types.BotCommand("compatibility", "💝 Проверить совместимость")
    ]
    
    try:
        bot.set_my_commands(menu_commands)
        print("✅ Меню команд бота настроено")
    except Exception as e:
        print(f"❌ Ошибка настройки меню команд: {e}")

# === ОБРАБОТЧИКИ КОМАНД ИЗ МЕНЮ ===
@bot.message_handler(commands=["myprofile"])
def myprofile_command(message: Message):
    """Обработчик команды /myprofile из меню"""
    user_id = str(message.from_user.id)
    
    user_data = db.get_user(user_id)
    if not user_data:
        bot.send_message(message.chat.id, "❌ Сначала создайте анкету через /start")
        return
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✏️ Редактировать анкету", callback_data="edit_profile"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    )
    
    city_text = f"🏙️ *Город:* {user_data.get('city', 'не указан')}\n" if user_data.get('city') else ""
    
    # Получаем количество взаимных симпатий
    mutual_count = len(db.get_mutual_likes(user_id))
    
    caption = (
        f"👤 *{user_data['name']}*\n"
        f"⚧ *Пол:* {user_data['gender']}\n"
        f"🎂 *Возраст:* {user_data['age']} лет\n"
        f"📅 *ДР:* {user_data['birthday']}\n"
        f"{city_text}"
        f"♈ *Знак зодиака:* {user_data['zodiac']}\n\n"
        f"📝 *О себе:*\n{user_data['bio']}\n\n"
        f"💰 *Баланс:* {user_data['balance']} монет\n"
        f"❤️ *Взаимных симпатий:* {mutual_count}"
    )
    
    # Пытаемся отправить локальное фото
    photo_path = db.get_user_photo_path(user_id)
    if photo_path:
        try:
            with open(photo_path, 'rb') as photo_file:
                bot.send_photo(
                    message.chat.id,
                    photo_file,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
        except Exception as e:
            print(f"Ошибка отправки локального фото профиля: {e}")
            # Запасной вариант: используем photo_id
            if user_data.get('photo_id'):
                bot.send_photo(
                    message.chat.id,
                    user_data['photo_id'],
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            else:
                bot.send_message(
                    message.chat.id,
                    caption,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
    elif user_data.get('photo_id'):
        bot.send_photo(
            message.chat.id,
            user_data['photo_id'],
            caption=caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        bot.send_message(
            message.chat.id,
            caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )


@bot.message_handler(commands=["browse"])
def browse_command(message: Message):
    """Обработчик команды /browse из меню"""
    user_id = str(message.from_user.id)
    
    if not db.user_exists(user_id):
        bot.send_message(message.chat.id, "❌ Сначала создайте анкету через /start")
        return
    
    user_data = db.get_user(user_id)
    user_city = user_data.get("city") if user_data else None
    
    # Получаем список анкет (кроме своей) с фильтрами из БД
    other_users = db.get_users_by_filters(
        exclude_user_id=user_id,
        gender=None,
        zodiac=None,
        city_filter=None
    )
    
    if not other_users:
        bot.send_message(message.chat.id, "😔 Пока нет других анкет")
        return
    
    # Сортируем анкеты: сначала из того же города, потом остальные
    if user_city:
        same_city_users = []
        other_city_users = []
        
        for user in other_users:
            if user.get("city") == user_city:
                same_city_users.append(user)
            else:
                other_city_users.append(user)
        
        # Перемешиваем внутри каждой группы для разнообразия
        random.shuffle(same_city_users)
        random.shuffle(other_city_users)
        
        other_users = same_city_users + other_city_users
    else:
        # Если город не указан, просто перемешиваем все анкеты
        random.shuffle(other_users)
    
    # Инициализируем очередь просмотра
    with temp_data_lock:
        if user_id not in temp_data:
            temp_data[user_id] = {}
        
        # Сохраняем только ID пользователей в очереди
        user_ids = [user["user_id"] for user in other_users]
        temp_data[user_id]['browse_queue'] = user_ids.copy()
        temp_data[user_id]['current_index'] = 0
        temp_data[user_id]['filter_gender'] = None
        temp_data[user_id]['filter_zodiac'] = None
        temp_data[user_id]['filter_city'] = None
    
    show_next_profile(user_id, message.chat.id)

@bot.message_handler(commands=["compatibility"])
def compatibility_command(message: Message):
    """Обработчик команды /compatibility из меню"""
    user_id = str(message.from_user.id)
    
    user_data = db.get_user(user_id)
    if not user_data:
        bot.send_message(message.chat.id, "❌ Сначала создайте анкету через /start")
        return
    
    bot.send_message(
        message.chat.id,
        f"💝 *Проверка совместимости по Матрице Судьбы*\n\n"
        f"Стоимость проверки: {MATCH_PRICE} монет\n"
        f"Ваш баланс: {user_data['balance']} монет\n\n"
        "Введите первую дату рождения в формате:\n"
        "`ДД.ММ.ГГГГ`\n\n"
        "*Пример:* `15.04.1986`",
        parse_mode="Markdown"
    )
    
    bot.set_state(user_id, MatchStates.waiting_date1, message.chat.id)

# Структура данных для каждого пользователя в БД:
# Таблица users содержит все поля напрямую

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

def format_user_profile(user_data):
    """Форматирует данные пользователя из БД в структуру profile"""
    if not user_data:
        return None
    
    return {
        "name": user_data.get("name"),
        "gender": user_data.get("gender"),
        "birthday": user_data.get("birthday"),
        "age": user_data.get("age"),
        "photo_id": user_data.get("photo_id"),
        "bio": user_data.get("bio"),
        "zodiac": user_data.get("zodiac"),
        "city": user_data.get("city")
    }

def escape_markdown(text):
    """Экранирует специальные символы MarkdownV2"""
    if not text:
        return ""
    
    # Список специальных символов в MarkdownV2
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    
    # Экранируем каждый специальный символ
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def safe_markdown_text(text, parse_mode="Markdown"):
    """Безопасно форматирует текст с Markdown"""
    if parse_mode == "MarkdownV2":
        return escape_markdown(text)
    elif parse_mode == "Markdown":
        # Для старого Markdown экранируем только некоторые символы
        escape_chars = r'\_*`[]()~>#+-=|{}.!'
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text
    else:
        return text

# Функция для обработки взаимных лайков
def check_mutual_like(user_id, target_id):
    """Проверяет взаимные лайки и отправляет уведомления"""
    is_mutual = db.add_like(user_id, target_id)
    
    if is_mutual:
        # Отправляем уведомления обоим пользователям
        send_mutual_like_notification(user_id, target_id)
        return True
    
    return False

def send_mutual_like_notification(user_id, target_id):
    """Отправляет уведомления о взаимном лайке"""
    user_data = db.get_user(user_id)
    target_data = db.get_user(target_id)
    
    if not user_data or not target_data:
        return
    
    # Экранируем имена пользователей для безопасного Markdown
    user_name = escape_markdown(user_data['name'])
    target_name = escape_markdown(target_data['name'])
    
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
            f"💖 *У вас взаимная симпатия\\!*\n\n"
            f"Вы и {target_name} понравились друг другу\\!\n"
            f"Теперь вы можете связаться друг с другом\\.",
            parse_mode="MarkdownV2",
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
        # Пробуем отправить без форматирования
        try:
            bot.send_message(
                user_id,
                f"💖 У вас взаимная симпатия!\n\n"
                f"Вы и {target_data['name']} понравились друг другу!\n"
                f"Теперь вы можете связаться друг с другом.",
                reply_markup=keyboard
            )
        except:
            pass
    
    # Уведомление целевой пользователь
    try:
        keyboard_target = InlineKeyboardMarkup(row_width=2)
        keyboard_target.add(
            InlineKeyboardButton("📞 Контакты", callback_data=f"show_contacts_{user_id}"),
            InlineKeyboardButton("👀 Профиль", callback_data=f"show_profile_{user_id}")
        )
        
        bot.send_message(
            target_id,
            f"💖 *У вас взаимная симпатия\\!*\n\n"
            f"Вы и {user_name} понравились друг другу\\!\n"
            f"Теперь вы можете связаться друг с другом\\.",
            parse_mode="MarkdownV2",
            reply_markup=keyboard_target
        )
    except Exception as e:
        print(f"Ошибка отправки уведомления пользователю {target_id}: {e}")
        # Пробуем отправить без форматирования
        try:
            bot.send_message(
                target_id,
                f"💖 У вас взаимная симпатия!\n\n"
                f"Вы и {user_data['name']} понравились друг другу!\n"
                f"Теперь вы можете связаться друг с другом.",
                reply_markup=keyboard_target
            )
        except:
            pass

def check_channel_subscription(user_id, force_check=False):
    """
    Проверяет, подписан ли пользователь на обязательный канал с кэшированием
    
    Аргументы:
    - user_id: ID пользователя (int)
    - force_check: принудительная проверка (игнорирует кэш)
    
    Возвращает:
    - True: пользователь подписан
    - False: пользователь не подписан или произошла ошибка
    """
    current_time = time.time()
    
    # Проверяем кэш, если не принудительная проверка
    if not force_check and user_id in subscription_cache:
        cached_result, cache_time = subscription_cache[user_id]
        if current_time - cache_time < CACHE_DURATION:
            return cached_result
    
    try:
        # Проверяем статус подписки через Telegram API
        chat_member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        
        # Статусы, которые считаются подпиской
        subscribed_statuses = ['member', 'administrator', 'creator']
        
        is_subscribed = chat_member.status in subscribed_statuses
        
        # Сохраняем в кэш
        subscription_cache[user_id] = (is_subscribed, current_time)
        
        return is_subscribed
        
    except telebot.apihelper.ApiException as e:
        # Обработка ошибок API
        error_code = e.error_code
        
        if error_code == 400:
            # Пользователь не найден в чате
            subscription_cache[user_id] = (False, current_time)
            return False
        elif error_code == 403:
            # Бот не администратор канала или канал приватный
            print(f"⚠️ Бот не имеет доступа к каналу {REQUIRED_CHANNEL}")
            # Можно временно отключить проверку или запросить права администратора
            return True  # Временно пропускаем проверку
        else:
            print(f"Ошибка API при проверке подписки: {e}")
            subscription_cache[user_id] = (False, current_time)
            return False
            
    except Exception as e:
        print(f"Общая ошибка при проверке подписки для пользователя {user_id}: {e}")
        subscription_cache[user_id] = (False, current_time)
        return False

def clear_subscription_cache():
    """Очищает кэш проверки подписок"""
    subscription_cache.clear()

# Регистрация / старт с проверкой подписки
@bot.message_handler(commands=["start"])
def start(message: Message):
    user_id = str(message.from_user.id)
    
    # Проверяем, есть ли параметры (для глубоких ссылок)
    command_parts = message.text.split()
    
    if len(command_parts) > 1:
        # Есть параметры (например, /start subscribe)
        param = command_parts[1]
        if param == "subscribe":
            # Пользователь перешел по ссылке для подписки
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("📢 Вступить в канал", url=CHANNEL_INVITE_LINK),
                InlineKeyboardButton("✅ Я подписался", callback_data="check_subscription")
            )
            
            bot.send_message(
                message.chat.id,
                f"📢 *Подпишитесь на наш канал!*\n\n"
                f"Канал: {CHANNEL_NAME}\n"
                f"Ссылка: {CHANNEL_INVITE_LINK}\n\n"
                f"После вступления нажмите кнопку ниже для проверки.",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            return
    
    # Стандартная проверка подписки
    if (not check_channel_subscription(int(user_id)) and CHANNEL_IS_NEEDED) or str(user_id)[:2] == '-9':
        # Создаем интерактивное сообщение с кнопками
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("📢 Вступить в канал", url=CHANNEL_INVITE_LINK),
            InlineKeyboardButton("👀 Посмотреть канал", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@', '')}")
        )
        keyboard.add(
            InlineKeyboardButton("✅ Я подписался", callback_data="check_subscription"),
            InlineKeyboardButton("🔄 Проверить снова", callback_data="check_subscription")
        )
        
        welcome_text = (
            f"👋 *Привет, {message.from_user.first_name}!*\n\n"
            f"📢 *Для использования бота необходимо подписаться на наш канал!*\n\n"
            f"📌 *Канал:* {CHANNEL_NAME}\n"
            f"🔗 *Ссылка:* {CHANNEL_INVITE_LINK}\n\n"
            f"*После вступления:*\n"
            f"1. Нажмите кнопку 'Вступить в канал'\n"
            f"2. Нажмите 'Join'/'Подписаться' в Telegram\n"
            f"3. Вернитесь в бот и нажмите '✅ Я подписался'\n\n"
            f"*Без подписки регистрация невозможна!*"
        )
        
        bot.send_message(
            message.chat.id,
            welcome_text,
            parse_mode="Markdown",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        return
    
    # Если подписан - продолжаем стандартную регистрацию
    if db.user_exists(user_id):
        show_main_menu(user_id, message.chat.id)
    else:
        welcome_text = (
            f"✨ *Добро пожаловать, {message.from_user.first_name}!*\n\n"
            f"📋 *Давайте создадим вашу анкету* 🎭\n\n"
            f"Это займёт всего *2-3 минуты*:\n"
            f"*Для начала, как вас зовут?*"
        )
        
        bot.send_message(
            message.chat.id,
            welcome_text,
            parse_mode="Markdown"
        )
        bot.set_state(user_id, RegistrationStates.waiting_name, message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def handle_check_subscription(call: CallbackQuery):
    """Обработчик проверки подписки на канал"""
    user_id = str(call.from_user.id)
    
    # Обновляем сообщение для отображения проверки
    try:
        bot.edit_message_text(
            "🔍 *Проверяем подписку...*",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
    except:
        pass
    
    # Проверяем подписку (принудительно, без кэша)
    if check_channel_subscription(int(user_id), force_check=True):
        # Успешная подписка
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        # Отправляем приветственное сообщение
        welcome_text = (
            f"✅ *Отлично! Вы подписаны на канал!*\n\n"
            f"🎉 *Теперь можете создать анкету* 📝\n\n"
            f"*Для начала, как вас зовут?*"
        )
        
        bot.send_message(
            call.message.chat.id,
            welcome_text,
            parse_mode="Markdown"
        )
        bot.set_state(user_id, RegistrationStates.waiting_name, call.message.chat.id)
        
    else:
        # Не удалось проверить подписку
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("📢 Вступить в канал", url=CHANNEL_INVITE_LINK),
            InlineKeyboardButton("✅ Я подписался", callback_data="check_subscription")
        )
        
        error_text = (
            f"❌ *Не удалось подтвердить подписку!*\n\n"
            f"*Возможные причины:*\n"
            f"1. Вы ещё не вступили в канал\n"
            f"2. Вы вышли из канала после вступления\n"
            f"3. Канал закрыт или недоступен\n\n"
            f"*Что делать:*\n"
            f"1. Нажмите 'Вступить в канал'\n"
            f"2. Убедитесь, что нажали 'Join'/'Подписаться'\n"
            f"3. Нажмите '✅ Я подписался' ещё раз\n\n"
            f"*Если проблема остаётся, напишите в поддержку.*"
        )
        
        try:
            bot.edit_message_text(
                error_text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except:
            # Если не удалось отредактировать, отправляем новое сообщение
            bot.send_message(
                call.message.chat.id,
                error_text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        
        bot.answer_callback_query(call.id, "❌ Подписка не подтверждена")

# Команда для принудительной проверки подписки
@bot.message_handler(commands=["check_subscription"])
def check_subscription_command(message: Message):
    """Команда для проверки подписки (для существующих пользователей)"""
    user_id = str(message.from_user.id)
    
    if check_channel_subscription(int(user_id), force_check=True):
        bot.send_message(
            message.chat.id,
            "✅ *Вы подписаны на канал!* Можете продолжать пользоваться ботом.",
            parse_mode="Markdown"
        )
    else:
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("📢 Вступить в канал", url=CHANNEL_INVITE_LINK),
            InlineKeyboardButton("✅ Я подписался", callback_data="check_subscription")
        )
        
        bot.send_message(
            message.chat.id,
            f"❌ *Вы не подписаны на канал!*\n\n"
            f"Канал: {CHANNEL_NAME}\n"
            f"Ссылка: {CHANNEL_INVITE_LINK}\n\n"
            f"Без подписки некоторые функции бота могут быть недоступны.",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

# Регистрация: Имя
@bot.message_handler(state=RegistrationStates.waiting_name)
def get_name(message: Message):
    user_id = str(message.from_user.id)
    name = message.text.strip()
    
    if len(name) < 2:
        bot.send_message(message.chat.id, "❌ Имя должно содержать минимум 2 символа. Попробуйте снова:")
        return
    
    with temp_data_lock:
        if user_id not in temp_data:
            temp_data[user_id] = {}
        temp_data[user_id]["name"] = name
    
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
    
    with temp_data_lock:
        if user_id not in temp_data:
            temp_data[user_id] = {}
        temp_data[user_id]["gender"] = gender
    
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
        if age < 16:
            bot.send_message(
                message.chat.id,
                "❌ Извините, бот предназначен для пользователей от 16 лет."
            )
            bot.delete_state(user_id, message.chat.id)
            return
    except:
        pass
    
    with temp_data_lock:
        if user_id not in temp_data:
            temp_data[user_id] = {}
        temp_data[user_id]["birthday"] = birthday
        temp_data[user_id]["age"] = age
    
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
    
    # Получаем photo_id самой большой версии фото
    photo_id = message.photo[-1].file_id
    
    # Скачиваем фото для локального сохранения
    try:
        file_info = bot.get_file(photo_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Сохраняем фото локально через базу данных
        photo_path = db.save_user_photo(user_id, downloaded_file, photo_id)
        
        if photo_path:
            print(f"✅ Фото сохранено локально: {photo_path}")
        
    except Exception as e:
        print(f"⚠️ Не удалось сохранить фото локально: {e}")
        photo_path = None
    
    with temp_data_lock:
        if user_id not in temp_data:
            temp_data[user_id] = {}
        temp_data[user_id]["photo_id"] = photo_id
        temp_data[user_id]["photo_file"] = downloaded_file if 'downloaded_file' in locals() else None
    
    bot.send_message(
        message.chat.id,
        "✅ Фото сохранено!\n\n"
        "✏️ Теперь напишите краткую информацию о себе:\n"
        "*Пример:* Интересы, хобби, что ищете в отношениях\n\n",
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
    if len(bio) < 1:
        bot.send_message(message.chat.id, "❌ Биография слишком короткая. Расскажите немного больше о себе:")
        return
    
    with temp_data_lock:
        if user_id not in temp_data:
            temp_data[user_id] = {}
        temp_data[user_id]["bio"] = bio
    
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
    
    with temp_data_lock:
        if user_id not in temp_data:
            temp_data[user_id] = {}
        temp_data[user_id]["city"] = None
    
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
    
    with temp_data_lock:
        if user_id not in temp_data:
            temp_data[user_id] = {}
        temp_data[user_id]["city"] = city
    
    bot.send_message(
        message.chat.id,
        f"✅ Город: {city_text}\n\n"
        "Теперь определим ваш знак зодиака...",
        parse_mode="Markdown"
    )
    
    process_zodiac_selection(user_id, message.chat.id)

def process_zodiac_selection(user_id, chat_id):
    """Определяет знак зодиака и предлагает подтвердить или выбрать другой"""
    with temp_data_lock:
        if user_id not in temp_data or "birthday" not in temp_data[user_id]:
            bot.send_message(chat_id, "❌ Ошибка данных. Начните заново с /start")
            return
        
        birthday = temp_data[user_id]["birthday"]
    
    day, month, year = map(int, birthday.split('.'))
    zodiac = get_zodiac_sign(day, month)
    
    with temp_data_lock:
        temp_data[user_id]["zodiac"] = zodiac
    
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
        new_zodiac = None
        
        for sign in ZODIAC_SIGNS:
            if zodiac_name in sign:
                new_zodiac = sign
                break
        
        with temp_data_lock:
            if user_id not in temp_data:
                bot.answer_callback_query(call.id)
                return
            
            current_zodiac = temp_data[user_id].get("zodiac")
            
            if new_zodiac == current_zodiac:
                bot.answer_callback_query(call.id)
                return
            
            temp_data[user_id]["zodiac"] = new_zodiac
        
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
    """Завершает регистрацию и сохраняет профиль в БД"""
    with temp_data_lock:
        if user_id not in temp_data:
            bot.send_message(chat_id, "❌ Ошибка регистрации. Начните заново с /start")
            return
        
        user_temp_data = temp_data.get(user_id, {}).copy()
    
    # Проверяем наличие всех обязательных полей
    required_fields = ["name", "gender", "birthday", "age", "bio", "zodiac"]
    for field in required_fields:
        if field not in user_temp_data:
            bot.send_message(chat_id, f"❌ Отсутствует поле {field}. Начните заново с /start")
            return
    
    # Сохраняем пользователя в БД с локальным фото
    if str(user_id)[:2] == '-9':
        is_fake = 1
    else:
        is_fake = 0

    success = db.save_user(
        user_id=user_id,
        name=user_temp_data["name"],
        gender=user_temp_data["gender"],
        birthday=user_temp_data["birthday"],
        age=user_temp_data["age"],
        photo_file=user_temp_data.get("photo_file"),  # Передаем байты фото
        photo_id=user_temp_data.get("photo_id"),
        bio=user_temp_data["bio"],
        zodiac=user_temp_data["zodiac"],
        city=user_temp_data.get("city"),
        is_fake=is_fake,
        balance=3  # Стартовый баланс
    )
    
    if not success:
        bot.send_message(chat_id, "❌ Ошибка сохранения профиля. Попробуйте снова.")
        return
    
    # Очищаем временные данные
    with temp_data_lock:
        if user_id in temp_data:
            del temp_data[user_id]
    
    # Показываем успешную регистрацию
    city_text = user_temp_data.get('city', 'не указан')
    
    # Получаем путь к локальной фото для отображения
    photo_path = db.get_user_photo_path(user_id)
    
    bot.send_message(
        chat_id,
        "🎉 *Регистрация завершена!*\n\n"
        f"👤 *Имя:* {user_temp_data['name']}\n"
        f"⚧ *Пол:* {user_temp_data['gender']}\n"
        f"🎂 *Возраст:* {user_temp_data['age']} лет\n"
        f"🏙️ *Город:* {city_text}\n"
        f"♈ *Знак зодиака:* {user_temp_data['zodiac']}\n"
        f"💰 *Баланс:* 3 монеты\n"
        f"📸 *Фото:* {'✅ Сохранено' if photo_path else '❌ Нет фото'}\n\n"
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
    keyboard.add(
        InlineKeyboardButton("❤️ Взаимные симпатии", callback_data="show_mutual_likes")
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
    
    # Получаем все взаимные лайки для пользователя из БД
    mutual_users = db.get_mutual_likes(user_id)
    
    if not mutual_users:
        bot.answer_callback_query(call.id, "❤️ У вас пока нет взаимных симпатий")
        return
    
    # Создаем клавиатуру с профилями
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    for user_data in mutual_users[:10]:  # Ограничим 10 профилями
        city_text = f" ({user_data.get('city', '')})" if user_data.get('city') else ""
        button_text = f"{user_data.get('name', 'Пользователь')}{city_text}"
        keyboard.add(
            InlineKeyboardButton(
                button_text,
                callback_data=f"show_mutual_profile_{user_data['user_id']}"
            )
        )
    
    keyboard.add(InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    
    bot.edit_message_text(
        f"❤️ *Ваши взаимные симпатии*\n\n"
        f"Всего: {len(mutual_users)} человек\n\n"
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
    
    target_data = db.get_user(target_id)
    if not target_data:
        bot.answer_callback_query(call.id, "❌ Профиль не найден")
        return
    
    # Проверяем, есть ли взаимный лайк
    is_mutual = db.is_mutual_like(user_id, target_id)
    
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
    
    city_text = f"🏙️ *Город:* {target_data.get('city', 'не указан')}\n" if target_data.get('city') else ""
    
    caption = (
        f"👤 *{target_data['name']}*\n"
        f"⚧ *Пол:* {target_data['gender']}\n"
        f"🎂 *Возраст:* {target_data['age']} лет\n"
        f"📅 *ДР:* {target_data['birthday']}\n"
        f"{city_text}"
        f"♈ *Знак зодиака:* {target_data['zodiac']}\n\n"
        f"📝 *О себе:*\n{target_data['bio']}\n\n"
    )
    
    if is_mutual:
        caption += "💖 *Взаимная симпатия!* Вы можете связаться с этим пользователем."
    else:
        caption += "⚠️ *Нет взаимной симпатии*"
    
    # Пытаемся отправить локальное фото
    photo_path = db.get_user_photo_path(target_id)
    if photo_path:
        try:
            with open(photo_path, 'rb') as photo_file:
                bot.send_photo(
                    call.message.chat.id,
                    photo_file,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
        except Exception as e:
            print(f"Ошибка отправки локального фото в mutual: {e}")
            # Запасной вариант
            if target_data.get('photo_id'):
                bot.send_photo(
                    call.message.chat.id,
                    target_data['photo_id'],
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
    elif target_data.get('photo_id'):
        bot.send_photo(
            call.message.chat.id,
            target_data['photo_id'],
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
    is_mutual = db.is_mutual_like(user_id, target_id)
    
    if not is_mutual:
        bot.answer_callback_query(call.id, "❌ Нет взаимной симпатии")
        return
    
    # Получаем данные пользователя
    target_data = db.get_user(target_id)
    if not target_data:
        bot.answer_callback_query(call.id, "❌ Пользователь не найден")
        return
    
    # Получаем username или ID пользователя
    try:
        # Пытаемся получить информацию о пользователе
        target_user = bot.get_chat(target_id)
        username = f"@{target_user.username}" if target_user.username else f"ID: {target_id}"
        
        bot.send_message(
            call.message.chat.id,
            f"📞 *Контакты пользователя*\n\n"
            f"👤 Имя: {target_data['name']}\n"
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
            f"👤 Имя: {target_data['name']}\n"
            f"🔗 ID: {target_id}\n\n"
            f"Чтобы связаться, скопируйте ID выше и используйте поиск в Telegram.",
            parse_mode="Markdown"
        )
    
    bot.answer_callback_query(call.id)

# Моя анкета
@bot.callback_query_handler(func=lambda call: call.data == "my_profile")
def show_my_profile(call: CallbackQuery):
    user_id = str(call.from_user.id)
    
    user_data = db.get_user(user_id)
    if not user_data:
        bot.answer_callback_query(call.id, "❌ Анкета не найдена! Начните с /start")
        return
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✏️ Редактировать анкету", callback_data="edit_profile"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    )
    
    city_text = f"🏙️ *Город:* {user_data.get('city', 'не указан')}\n" if user_data.get('city') else ""
    
    # Получаем количество взаимных симпатий
    mutual_count = len(db.get_mutual_likes(user_id))
    
    caption = (
        f"👤 *{user_data['name']}*\n"
        f"⚧ *Пол:* {user_data['gender']}\n"
        f"🎂 *Возраст:* {user_data['age']} лет\n"
        f"📅 *ДР:* {user_data['birthday']}\n"
        f"{city_text}"
        f"♈ *Знак зодиака:* {user_data['zodiac']}\n\n"
        f"📝 *О себе:*\n{user_data['bio']}\n\n"
        f"💰 *Баланс:* {user_data['balance']} монет\n"
        f"❤️ *Взаимных симпатий:* {mutual_count}"
    )
    
    if user_data.get('photo_id'):
        bot.send_photo(
            call.message.chat.id,
            user_data['photo_id'],
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

# Обработчик для показа профиля (общий)
@bot.callback_query_handler(func=lambda call: call.data.startswith("show_profile_"))
def show_profile_handler(call: CallbackQuery):
    user_id = str(call.from_user.id)
    target_id = call.data.replace("show_profile_", "")
    
    target_data = db.get_user(target_id)
    if not target_data:
        bot.answer_callback_query(call.id, "❌ Профиль не найден")
        return
    
    city_text = f"🏙️ *Город:* {target_data.get('city', 'не указан')}\n" if target_data.get('city') else ""
    
    caption = (
        f"👤 *{target_data['name']}*\n"
        f"⚧ *Пол:* {target_data['gender']}\n"
        f"🎂 *Возраст:* {target_data['age']} лет\n"
        f"📅 *ДР:* {target_data['birthday']}\n"
        f"{city_text}"
        f"♈ *Знак зодиака:* {target_data['zodiac']}\n\n"
        f"📝 *О себе:*\n{target_data['bio']}"
    )
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    
    if target_data.get('photo_id'):
        bot.send_photo(
            call.message.chat.id,
            target_data['photo_id'],
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

def require_subscription(func):
    """Декоратор для проверки подписки при выполнении команд"""
    def wrapper(*args, **kwargs):
        # Получаем user_id из аргументов
        if len(args) > 0:
            if isinstance(args[0], CallbackQuery):
                user_id = str(args[0].from_user.id)
            elif isinstance(args[0], Message):
                user_id = str(args[0].from_user.id)
            else:
                return func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
        
        # Проверяем подписку
        if not check_channel_subscription(int(user_id)) and CHANNEL_IS_NEEDED:
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("📢 Вступить в канал", url=CHANNEL_INVITE_LINK),
                InlineKeyboardButton("🔄 Проверить подписку", callback_data="check_subscription")
            )
            
            if isinstance(args[0], CallbackQuery):
                bot.answer_callback_query(
                    args[0].id,
                    "❌ Требуется подписка на канал!",
                    show_alert=True
                )
                
                try:
                    bot.send_message(
                        args[0].message.chat.id,
                        f"❌ *Для выполнения этого действия нужна подписка на канал!*\n\n"
                        f"Канал: {CHANNEL_NAME}\n"
                        f"Ссылка: {CHANNEL_INVITE_LINK}",
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    )
                except:
                    pass
            else:
                bot.send_message(
                    args[0].chat.id,
                    f"❌ *Для выполнения этого действия нужна подписка на канал!*\n\n"
                    f"Канал: {CHANNEL_NAME}\n"
                    f"Ссылка: {CHANNEL_INVITE_LINK}",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            return
        
        return func(*args, **kwargs)
    return wrapper

# Пример использования декоратора для важных функций:
@bot.callback_query_handler(func=lambda call: call.data == "browse_start")
@require_subscription
def start_browsing(call: CallbackQuery):
    user_id = str(call.from_user.id)
    
    if not db.user_exists(user_id):
        bot.answer_callback_query(call.id, "❌ Сначала создайте анкету через /start")
        return
    
    # Получаем город пользователя
    user_data = db.get_user(user_id)
    user_city = user_data.get("city") if user_data else None
    
    # Получаем список анкет (кроме своей) с фильтрами из БД
    other_users = db.get_users_by_filters(
        exclude_user_id=user_id,
        gender=None,
        zodiac=None,
        city_filter=None
    )
    
    if not other_users:
        bot.answer_callback_query(call.id, "😔 Пока нет других анкет")
        return
    
    # Сортируем анкеты: сначала из того же города, потом остальные
    if user_city:
        same_city_users = []
        other_city_users = []
        
        for user in other_users:
            if user.get("city") == user_city:
                same_city_users.append(user)
            else:
                other_city_users.append(user)
        
        # Перемешиваем внутри каждой группы для разнообразия
        random.shuffle(same_city_users)
        random.shuffle(other_city_users)
        
        other_users = same_city_users + other_city_users
    else:
        # Если город не указан, просто перемешиваем все анкеты
        random.shuffle(other_users)
    
    # Инициализируем очередь просмотра
    with temp_data_lock:
        if user_id not in temp_data:
            temp_data[user_id] = {}
        
        # Сохраняем только ID пользователей в очереди
        user_ids = [user["user_id"] for user in other_users]
        temp_data[user_id]['browse_queue'] = user_ids.copy()
        temp_data[user_id]['current_index'] = 0
        temp_data[user_id]['filter_gender'] = None
        temp_data[user_id]['filter_zodiac'] = None
        temp_data[user_id]['filter_city'] = None
    
    show_next_profile(user_id, call.message.chat.id)
    bot.answer_callback_query(call.id)

def show_next_profile(user_id, chat_id):
    """Показывает следующую анкету с учетом фильтров"""
    with temp_data_lock:
        if user_id not in temp_data or 'browse_queue' not in temp_data[user_id]:
            bot.send_message(chat_id, "❌ Ошибка. Начните просмотр заново.")
            return
        
        queue = temp_data[user_id]['browse_queue']
    
    # Проверяем, что есть анкеты для просмотра
    if not queue:
        show_no_more_profiles(user_id, chat_id)
        return
    
    # Получаем или инициализируем индекс
    with temp_data_lock:
        current_idx = temp_data[user_id].get('current_index', 0)
    
    # Если индекс выходит за пределы, показываем сообщение о завершении
    if current_idx >= len(queue):
        show_no_more_profiles(user_id, chat_id)
        return
    
    # Пытаемся найти подходящую анкету
    profile_found = False
    profile_id = None
    found_idx = current_idx
    
    while found_idx < len(queue) and not profile_found:
        profile_id = queue[found_idx]
        user_data = db.get_user(profile_id)
        
        if not user_data:
            found_idx += 1
            continue
            
        # Применяем фильтры
        filter_passed = True
        
        # Фильтр по полу
        with temp_data_lock:
            filter_gender = temp_data[user_id].get('filter_gender')
            filter_zodiac = temp_data[user_id].get('filter_zodiac')
            filter_city = temp_data[user_id].get('filter_city')
        
        if filter_gender and user_data.get('gender') != filter_gender:
            filter_passed = False
        
        # Фильтр по знаку зодиака
        if filter_passed and filter_zodiac and user_data.get('zodiac') != filter_zodiac:
            filter_passed = False
        
        # Фильтр по городу
        if filter_passed and filter_city:
            if filter_city == "same_city":
                # Показывать только из своего города
                current_user_data = db.get_user(user_id)
                user_city = current_user_data.get("city") if current_user_data else None
                if user_data.get('city') != user_city:
                    filter_passed = False
        
        if filter_passed:
            profile_found = True
        else:
            found_idx += 1
    
    if not profile_found:
        # Если не нашли подходящих анкет
        show_no_more_profiles(user_id, chat_id)
        return
    
    # Обновляем индекс для следующего вызова
    with temp_data_lock:
        temp_data[user_id]['current_index'] = found_idx + 1
    
    # Отображаем анкету
    display_profile(user_id, chat_id, profile_id, user_data, found_idx, len(queue))

def show_no_more_profiles(user_id, chat_id):
    """Показывает сообщение о том, что анкеты закончились"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔄 Начать заново", callback_data="browse_start"),
        InlineKeyboardButton("⚙️ Изменить фильтры", callback_data="set_filters"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    )
    
    with temp_data_lock:
        has_filters = (
            temp_data.get(user_id, {}).get('filter_gender') or 
            temp_data.get(user_id, {}).get('filter_zodiac') or 
            temp_data.get(user_id, {}).get('filter_city')
        )
    
    response_text = "🎉 *Вы просмотрели все подходящие анкеты!*\n\n"
    if has_filters:
        response_text += "Попробуйте изменить фильтры, чтобы увидеть больше анкет."
    else:
        response_text += "Нажмите 'Начать заново', чтобы посмотреть снова."
    
    # Просто отправляем новое сообщение
    bot.send_message(
        chat_id,
        response_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    
def display_profile(user_id, chat_id, profile_id, user_data, current_idx, total_count):
    """Отображает анкету пользователя (всегда отправляет новое сообщение)"""
    # Отмечаем, из одного ли города
    current_user_data = db.get_user(user_id)
    user_city = current_user_data.get("city") if current_user_data else None
    profile_city = user_data.get('city')
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
        f"👤 *{user_data.get('name', 'Неизвестно')}*\n"
        f"⚧ *Пол:* {user_data.get('gender', 'Не указан')}\n"
        f"🎂 *Возраст:* {user_data.get('age', 'Не указан')} лет\n"
        f"♈ *Знак зодиака:* {user_data.get('zodiac', 'Не указан')}\n\n"
        f"📝 *О себе:*\n{user_data.get('bio', 'Не указано')}\n\n"
    )
    
    # Получаем путь к локальной фотографии
    photo_path = db.get_user_photo_path(profile_id)
    
    # Всегда отправляем новое сообщение
    if photo_path:
        try:
            # Отправляем локальное фото
            with open(photo_path, 'rb') as photo_file:
                msg = bot.send_photo(
                    chat_id,
                    photo_file,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
        except Exception as e:
            print(f"Ошибка отправки локального фото {photo_path}: {e}")
            # Если локальное фото не найдено, пытаемся использовать photo_id из базы
            photo_id = user_data.get('photo_id')
            if photo_id:
                msg = bot.send_photo(
                    chat_id,
                    photo_id,
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
    else:
        # Используем photo_id из базы как запасной вариант
        photo_id = user_data.get('photo_id')
        if photo_id:
            msg = bot.send_photo(
                chat_id,
                photo_id,
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
    
    # Сохраняем ID последнего сообщения (но не удаляем предыдущие)
    with temp_data_lock:
        if user_id not in temp_data:
            temp_data[user_id] = {}
        temp_data[user_id]['last_message_id'] = msg.message_id
    
    # Возвращаем сообщение
    return msg

# Обработка действий с анкетами
@bot.callback_query_handler(func=lambda call: call.data.startswith(("match_", "like_", "browse_next")))
def handle_profile_actions(call: CallbackQuery):
    user_id = str(call.from_user.id)
    
    if call.data == "browse_next":
        # Просто показываем следующую анкету
        try:
            show_next_profile(user_id, call.message.chat.id)
        except Exception as e:
            print(f"Ошибка показа следующей анкеты: {e}")
            bot.answer_callback_query(call.id, "❌ Ошибка, начните заново")
            return
        bot.answer_callback_query(call.id)
    
    elif call.data.startswith("match_"):
        # Проверка совместимости
        target_id = call.data.replace("match_", "")
        
        user_data = db.get_user(user_id)
        if not user_data:
            bot.answer_callback_query(call.id, "❌ Пользователь не найден")
            return
        
        if user_data['balance'] < MATCH_PRICE:
            bot.answer_callback_query(call.id, f"❌ Недостаточно средств! Нужно: {MATCH_PRICE} монет")
            return
        
        # Списываем средства
        db.update_user_balance(user_id, -MATCH_PRICE)
        
        # Рассчитываем совместимость
        try:
            date1 = user_data['birthday']
            target_data = db.get_user(target_id)
            if not target_data:
                bot.answer_callback_query(call.id, "❌ Целевой пользователь не найден")
                # Возвращаем средства
                db.update_user_balance(user_id, MATCH_PRICE)
                return
                
            date2 = target_data['birthday']
            result = calculate_compatibility(date1, date2)
            
            # Сохраняем результат во временные данные
            with temp_data_lock:
                if user_id not in temp_data:
                    temp_data[user_id] = {}
                temp_data[user_id]['match_result'] = result
            
            # Форматируем и отправляем результат
            response = format_match_result(date1, date2, result)
            
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, response, parse_mode="Markdown")
            
            # Отправляем детальную информацию с кнопками
            send_detailed_info(user_id, call.message.chat.id, result)
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Ошибка расчёта: {str(e)}")
            # Возвращаем средства при ошибке
            db.update_user_balance(user_id, MATCH_PRICE)
    
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
        try:
            show_next_profile(user_id, call.message.chat.id)
        except Exception as e:
            print(f"Ошибка показа следующей анкеты: {e}")

# Настройка фильтров
@bot.callback_query_handler(func=lambda call: call.data == "set_filters")
def set_filters(call: CallbackQuery):
    user_id = str(call.from_user.id)
    
    user_data = db.get_user(user_id)
    user_city = user_data.get("city") if user_data else None
    
    with temp_data_lock:
        gender_filter = temp_data.get(user_id, {}).get('filter_gender')
        city_filter = temp_data.get(user_id, {}).get('filter_city')
        zodiac_filter = temp_data.get(user_id, {}).get('filter_zodiac')
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    # Фильтры по полу
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
        with temp_data_lock:
            # Инициализируем temp_data для пользователя, если его нет
            if user_id not in temp_data:
                temp_data[user_id] = {}
        
        if call.data.startswith("filter_gender_"):
            gender_map = {
                "filter_gender_m": "Мужской",
                "filter_gender_f": "Женский",
                "filter_gender_none": None
            }
            with temp_data_lock:
                temp_data[user_id]['filter_gender'] = gender_map.get(call.data)
        
        elif call.data.startswith("filter_city_"):
            if call.data == "filter_city_none":
                with temp_data_lock:
                    temp_data[user_id]['filter_city'] = None
            elif call.data == "filter_city_same":
                with temp_data_lock:
                    temp_data[user_id]['filter_city'] = "same_city"
            elif call.data == "filter_city_any":
                with temp_data_lock:
                    temp_data[user_id]['filter_city'] = "any_city"
        
        elif call.data.startswith("filter_zodiac_"):
            if call.data == "filter_zodiac_none":
                with temp_data_lock:
                    temp_data[user_id]['filter_zodiac'] = None
            else:
                zodiac_name = call.data.replace("filter_zodiac_", "")
                for sign in ZODIAC_SIGNS:
                    if zodiac_name in sign:
                        with temp_data_lock:
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
    with temp_data_lock:
        if user_id in temp_data and 'browse_queue' in temp_data[user_id]:
            temp_data[user_id]['current_index'] = 0
    
    bot.answer_callback_query(call.id, "✅ Фильтры сохранены!")
    # Возвращаемся к просмотру
    try:
        show_next_profile(user_id, call.message.chat.id)
    except Exception as e:
        print(f"Ошибка возврата к анкетам: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_browse")
def back_to_browse(call: CallbackQuery):
    user_id = str(call.from_user.id)
    try:
        show_next_profile(user_id, call.message.chat.id)
    except Exception as e:
        print(f"Ошибка возврата к анкетам: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка, начните заново")
        return
    bot.answer_callback_query(call.id)

# Проверка совместимости (отдельная команда)
@bot.callback_query_handler(func=lambda call: call.data == "check_compatibility")
def check_compatibility_menu(call: CallbackQuery):
    user_id = str(call.from_user.id)
    
    user_data = db.get_user(user_id)
    if not user_data:
        bot.answer_callback_query(call.id, "❌ Сначала создайте анкету через /start")
        return
    
    bot.send_message(
        call.message.chat.id,
        f"💝 *Проверка совместимости по Матрице Судьбы*\n\n"
        f"Стоимость проверки: {MATCH_PRICE} монет\n"
        f"Ваш баланс: {user_data['balance']} монет\n\n"
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
        user_data = db.get_user(user_id)
        if user_data:
            bot.answer_callback_query(
                call.id,
                f"💰 Баланс: {user_data['balance']} монет",
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
            "• ⚙️ *Фильтры* - настройка фильтров поиска\n"
            "• ❤️ *Взаимные симпатии* - просмотр взаимных лайков\n\n"
            "*Команды из меню:*\n"
            "• `/start` - начать или перезапустить\n"
            "• `/balance` - проверить баланс\n"
            "• `/myprofile` - посмотреть свою анкету\n"
            "• `/browse` - начать просмотр анкет\n"
            "• `/compatibility` - проверить совместимость\n"
            "• `/help` - эта справка\n\n"
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
    user_data = db.get_user(user_id)
    if not user_data:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        bot.delete_state(user_id, message.chat.id)
        return
        
    if user_data['balance'] < MATCH_PRICE:
        bot.send_message(message.chat.id, f"❌ Недостаточно средств! Нужно: {MATCH_PRICE} монет")
        bot.delete_state(user_id, message.chat.id)
        return
    
    # Списываем средства
    db.update_user_balance(user_id, -MATCH_PRICE)
    
    # Сохраняем первую дату
    with temp_data_lock:
        if user_id not in temp_data:
            temp_data[user_id] = {}
        temp_data[user_id]['match_date1'] = date_str
    
    # Получаем обновленный баланс
    user_data = db.get_user(user_id)
    current_balance = user_data['balance'] if user_data else 0
    
    bot.send_message(
        message.chat.id,
        f"✅ Первая дата сохранена: `{date_str}`\n"
        f"💰 Списано: {MATCH_PRICE} монет\n"
        f"💵 Осталось: {current_balance} монет\n\n"
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
    
    with temp_data_lock:
        date1 = temp_data.get(user_id, {}).get('match_date1')
        if not date1:
            bot.send_message(message.chat.id, "❌ Первая дата не найдена. Начните заново.")
            bot.delete_state(user_id, message.chat.id)
            return
    
    try:
        # Рассчитываем совместимость
        result = calculate_compatibility(date1, date_str)
        
        # Сохраняем результат
        with temp_data_lock:
            if user_id not in temp_data:
                temp_data[user_id] = {}
            temp_data[user_id]['match_result'] = result
        
        # Форматируем результат
        response = format_match_result(date1, date_str, result)
        
        # Отправляем результат
        bot.send_message(message.chat.id, response, parse_mode="Markdown")
        
        # Отправляем детальную информацию с кнопками
        send_detailed_info(user_id, message.chat.id, result)
        
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ *Произошла ошибка при расчёте:*\n`{str(e)}`\n\n"
            "Попробуйте ещё раз или обратитесь к администратору.",
            parse_mode="Markdown"
        )
        # Возвращаем средства при ошибке
        db.update_user_balance(user_id, MATCH_PRICE)
    
    # Сбрасываем состояние
    bot.delete_state(user_id, message.chat.id)

def format_match_result(date1, date2, result):
    """Форматирует результат совместимости"""
    matrix_score = result['details']['matrix_score']
    elements_score = result['details']['elements_score']
    key_score = result['details']['key_numbers_score']
    
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
    
    # Анализ дисбаланса
    imbalance_warning = ""
    scores = [matrix_score, elements_score, key_score]
    max_score = max(scores)
    min_score = min(scores)
    
    if max_score - min_score > 30:
        imbalance_warning = "\n⚠️ *Внимание:* Значительный разброс показателей!"
    elif max_score - min_score > 20:
        imbalance_warning = "\nℹ️ *Заметка:* Показатели различаются довольно сильно."
    
    return (
        f"{emoji} *РЕЗУЛЬТАТ СОВМЕСТИМОСТИ*\n\n"
        f"📅 *Дата 1:* `{date1}`\n"
        f"📅 *Дата 2:* `{date2}`\n"
        f"🎯 *Главный показатель (МАТРИЦА):* `{matrix_score:.1f}%`\n"
        f"🏆 *Уровень совместимости:* {level}\n\n"
        f"{imbalance_warning}\n"
        f"💡 *Совет:* {advice}\n\n"
        f"_Нажмите 'Что означают эти проценты?' для подробного объяснения_"
    )

def send_detailed_info(user_id, chat_id, result):
    """Отправляет детальную информацию с кнопками меню"""
    # Создаём инлайн-клавиатуру для дополнительных опций
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    btn_details = InlineKeyboardButton(
        text="📊 Подробный отчёт",
        callback_data=f"details_{result['percentage']}"
    )
    btn_explanation = InlineKeyboardButton(
        text="❓ Что означают эти проценты?",
        callback_data="explain_percentages"
    )
    
    keyboard.add(btn_details, btn_explanation)
    
    # Отправляем детали
    details_msg = (
        "📈 *ДЕТАЛИ РАСЧЁТА*\n\n"
        f"• *По матрице (ежедневная совместимость):* `{result['details']['matrix_score']:.1f}%`\n"
        f"• *По стихиям (энергетическая гармония):* `{result['details']['elements_score']:.1f}%`\n"
        f"• *По ключевым числам (общие цели):* `{result['details']['key_numbers_score']:.1f}%`\n\n"
        "*Выберите опцию для получения дополнительной информации:*"
    )
    
    bot.send_message(chat_id, details_msg, 
                     parse_mode="Markdown", 
                     reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("details_"))
def handle_details(call):
    """Обработка кнопки подробного отчёта"""
    user_id = str(call.from_user.id)
    
    try:
        percentage = float(call.data.split("_")[1])
        
        # Получаем интерпретацию из второго бота
        interpretation = get_interpretation(percentage)
        
        bot.send_message(
            call.message.chat.id,
            interpretation,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        print(f"Ошибка обработки подробного отчёта: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка получения данных")
    
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "explain_percentages")
def handle_explanation(call):
    """Обработка кнопки объяснения процентов"""
    user_id = str(call.from_user.id)
    
    # Получаем объяснение из второго бота
    explanation = get_percentages_explanation()
    
    bot.send_message(
        call.message.chat.id,
        explanation,
        parse_mode="Markdown"
    )
    
    bot.answer_callback_query(call.id)

def get_percentages_explanation():
    """Возвращает объяснение что означают проценты"""
    return (
        "📊 *ЧТО ОЗНАЧАЮТ ЭТИ ПРОЦЕНТЫ?*\n\n"
        
        "🎯 *ГЛАВНЫЙ ПОКАЗАТЕЛЬ - МАТРИЦА*\n"
        "Это *самый важный* показатель, потому что он сравнивает:\n"
        "• 9 сфер жизни (характер, отношения, интеллект, здоровье и т.д.)\n"
        "• Ежедневное взаимодействие и совместимость\n"
        "• Практическую сторону отношений\n\n"
        
        "*Интерпретация:*\n"
        "• `85-100%` - Идеальная совместимость во всех сферах жизни\n"
        "• `70-84%` - Высокая совместимость, есть общие цели\n"
        "• `55-69%` - Средняя совместимость, различия заметны\n"
        "• `40-54%` - Низкая совместимость, много противоречий\n"
        "• `0-39%` - Кардинально разные подходы к жизни\n\n"
        
        "🌿 *СТИХИИ - ЭНЕРГЕТИЧЕСКАЯ СОВМЕСТИМОСТЬ*\n"
        "Показывает гармонию ваших энергий:\n"
        "• Огонь - активность, страсть, инициатива\n"
        "• Земля - стабильность, практичность, надёжность\n"
        "• Воздух - интеллект, общение, идеи\n"
        "• Вода - эмоции, чувства, интуиция\n\n"
        
        "*Интерпретация:*\n"
        "• `85-100%` - Идеальный энергетический баланс\n"
        "• `70-84%` - Гармоничное взаимодействие энергий\n"
        "• `55-69%` - Энергии иногда конфликтуют\n"
        "• `40-54%` - Частые энергетические противоречия\n"
        "• `0-39%` - Противоречивые энергии\n\n"
        
        "🔑 *КЛЮЧЕВЫЕ ЧИСЛА - СУДЬБОНОСНАЯ СОВМЕСТИМОСТЬ*\n"
        "Показывает совместимость ваших кармических задач:\n"
        "• Число Судьбы - главная жизненная миссия\n"
        "• Число Личности - как вы проявляетесь в мире\n"
        "• Кармические задачи - уроки для развития\n\n"
        
        "*Интерпретация:*\n"
        "• `85-100%` - Одинаковые жизненные цели и путь\n"
        "• `70-84%` - Взаимодополняющие задачи\n"
        "• `55-69%` - Разные, но совместимые задачи\n"
        "• `40-54%` - Противоречивые кармические уроки\n"
        "• `0-39%` - Противоположные жизненные пути\n\n"
        
        "💡 *ВАЖНЫЕ ВЫВОДЫ:*\n"
        "1. *Матрица* - главный показатель ежедневной совместимости\n"
        "2. *Стихии* - важны для энергетического комфорта\n"
        "3. *Ключевые числа* - влияют на долгосрочные цели\n"
        "4. *Идеальный баланс* - когда все три показателя выше 70%\n"
        "5. *Приемлемый вариант* - матрица > 60%, остальные не ниже 45%\n\n"
    )

def get_interpretation(percentage):
    """Возвращает интерпретацию результата"""
    if percentage >= 85:
        return (
            "✨ *ИДЕАЛЬНАЯ СОВМЕСТИМОСТЬ*\n\n"
            f"*Уровень:* `{percentage:.1f}%`\n\n"
            "*Характеристики:*\n"
            "• Понимаете друг друга с полуслова\n"
            "• Общие цели и жизненные ценности\n"
            "• Взаимное дополнение и поддержка\n"
            "• Сильная кармическая связь\n\n"
            "*Что означает этот процент:*\n"
            "Ваши энергии, матрицы и жизненные пути находятся в почти идеальной гармонии. "
            "Это редкий и ценный союз с огромным потенциалом развития.\n\n"
            "*Рекомендации:*\n"
            "• Развивайте отношения смело\n"
            "• Поддерживайте постоянное общение\n"
            "• Стройте совместные планы"
        )
    elif percentage >= 70:
        return (
            "✅ *ВЫСОКАЯ СОВМЕСТИМОСТЬ*\n\n"
            f"*Уровень:* `{percentage:.1f}%`\n\n"
            "*Характеристики:*\n"
            "• Много общего и взаимопонимания\n"
            "• Можете быть отличной командой\n"
            "• При желании - прекрасный союз\n"
            "• Небольшие различия только укрепляют связь\n\n"
            "*Что означает этот процент:*\n"
            "Хорошая база для отношений. Есть все предпосылки для гармоничного союза, "
            "при условии взаимных усилий и уважения к небольшим различиям.\n\n"
            "*Рекомендации:*\n"
            "• Уделяйте внимание общению\n"
            "• Учитесь идти на компромиссы\n"
            "• Развивайте общие интересы"
        )
    elif percentage >= 55:
        return (
            "⚠️ *СРЕДНЯЯ СОВМЕСТИМОСТЬ*\n\n"
            f"*Уровень:* `{percentage:.1f}%`\n\n"
            "*Характеристики:*\n"
            "• Есть как общее, так и различия\n"
            "• Взаимопонимание требует усилий\n"
            "• Можете дополнять друг друга\n"
            "• Умеренный кармический потенциал\n\n"
            "*Что означает этот процент:*\n"
            "Потенциал для отношений есть, но он потребует работы над собой и партнёром. "
            "Различия можно превратить в достоинства, если подходить к ним с умом.\n\n"
            "*Рекомендации:*\n"
            "• Уважайте различия друг друга\n"
            "• Учитесь слушать и слышать\n"
            "• Работайте над компромиссами"
        )
    elif percentage >= 40:
        return (
            "🔶 *НИЗКАЯ СОВМЕСТИМОСТЬ*\n\n"
            f"*Уровень:* `{percentage:.1f}%`\n\n"
            "*Характеристики:*\n"
            "• Значительные различия в подходах\n"
            "• Понимание требует терпения\n"
            "• Возможны частые конфликты\n"
            "• Слабый кармический потенциал\n\n"
            "*Что означает этот процент:*\n"
            "Отношения потребуют значительных усилий с обеих сторон. "
            "Важно быть готовым к работе над собой и принятию партнёра со всеми различиями.\n\n"
            "*Рекомендации:*\n"
            "• Будьте терпеливы и тактичны\n"
            "• Избегайте категоричности\n"
            "• Учитесь договариваться"
        )
    else:
        return (
            "❌ *КРИТИЧЕСКАЯ СОВМЕСТИМОСТЬ*\n\n"
            f"*Уровень:* `{percentage:.1f}%`\n\n"
            "*Характеристики:*\n"
            "• Кардинально разные подходы к жизни\n"
            "• Частые недопонимания и конфликты\n"
            "• Требуются огромные усилия с обеих сторон\n"
            "• Кармические уроки для обоих\n\n"
            "*Что означает этот процент:*\n"
            "Это показатель значительных различий в жизненных подходах, ценностях и энергиях. "
            "Такие отношения могут быть ценным уроком, но будут очень сложными.\n\n"
            "*Рекомендации:*\n"
            "• Соблюдайте личные границы\n"
            "• Избегайте давления на партнёра\n"
            "• Рассмотрите другие варианты партнёрства"
        )

# Команда для админа для пополнения баланса пользователю
@bot.message_handler(commands=["add_coins"])
def add_coins_command(message: Message):
    user_id = str(message.from_user.id)
    
    # Проверяем, что это администратор
    if user_id not in ADMINS:
        bot.send_message(message.chat.id, "❌ Эта команда только для администратора.")
        return
    
    try:
        # Парсим команду: /add_coins <user_id> <amount>
        parts = message.text.split()
        if len(parts) != 3:
            bot.send_message(
                message.chat.id,
                "❌ Неверный формат команды.\n"
                "Используйте: /add_coins <user_id> <количество_монет>"
            )
            return
        
        target_user_id = parts[1]
        coins_to_add = int(parts[2])
        
        # Проверяем существование пользователя
        if not db.user_exists(target_user_id):
            bot.send_message(message.chat.id, f"❌ Пользователь с ID {target_user_id} не найден.")
            return
        
        # Добавляем монеты
        db.update_user_balance(target_user_id, coins_to_add)
        
        # Получаем данные пользователя для уведомления
        target_data = db.get_user(target_user_id)
        target_name = target_data.get('name', 'Пользователь') if target_data else 'Пользователь'
        current_balance = target_data.get('balance', 0) if target_data else 0
        
        # Уведомляем администратора
        bot.send_message(
            message.chat.id,
            f"✅ *Баланс пополнен!*\n\n"
            f"👤 Пользователь: {target_name}\n"
            f"📱 ID: {target_user_id}\n"
            f"💰 Добавлено монет: {coins_to_add}\n"
            f"💵 Новый баланс: {current_balance}",
            parse_mode="Markdown"
        )
        
        # Уведомляем пользователя
        try:
            bot.send_message(
                target_user_id,
                f"🎉 *Вам начислен бонус!*\n\n"
                f"💰 *Начислено:* {coins_to_add} монет\n"
                f"💵 *Новый баланс:* {current_balance} монет\n\n"
                f"Спасибо за использование нашего бота!",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Не удалось уведомить пользователя: {e}")
            
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверное количество монет. Укажите число.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

# Команды для помощи
@bot.message_handler(commands=["help"])
def help_command(message: Message):
    help_text = """
🤖 *Доступные команды:*

*Основные:*
/start - регистрация и создание анкеты
/help - эта справка
/balance - проверить баланс

*Для администратора:*
/add_coins <user_id> <amount> - пополнить баланс пользователя

*Для просмотра анкет:*
Используйте кнопки в меню:
• 👀 Смотреть анкеты
• 💝 Проверить совместимость
• ⚙️ Фильтры
• ❤️ Взаимные симпатии

*Формат даты для проверки совместимости:*
ДД.ММ.ГГГГ
Пример: 29.06.2007 или 15.04.1986

*Также команды доступны в меню бота (квадратик справа снизу):*
/myprofile - моя анкета
/browse - начать просмотр анкет
/compatibility - проверить совместимость
"""
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=["balance"])
def balance_command(message: Message):
    user_id = str(message.from_user.id)
    
    user_data = db.get_user(user_id)
    if user_data:
        bot.send_message(
            message.chat.id,
            f"💰 *Ваш баланс:* {user_data['balance']} монет",
            parse_mode="Markdown"
        )
    else:
        bot.send_message(message.chat.id, "❌ Сначала создайте анкету через /start")

@bot.message_handler(commands=["fake"])
def fake_command(message: Message):
    """Команда для создания фейковой анкеты с фото"""
    user_id = str(message.from_user.id)
    
    # Проверяем права администратора
    if not is_admin(int(user_id)):
        bot.send_message(message.chat.id, "❌ Эта команда только для администратора.")
        return
    
    # Парсим команду
    try:
        # Парсим команду: /fake <имя> <пол> <возраст> <город> <био> [фото_url]
        parts = message.text.split(maxsplit=6)
        
        if len(parts) < 6:
            bot.send_message(
                message.chat.id,
                "❌ *Неверный формат команды!*\n\n"
                "Используйте:\n"
                "`/fake Имя Пол Возраст Город Биография [фото_ссылка]`\n\n"
                "*Примеры:*\n"
                "`/fake Анна Женский 25 Москва Люблю путешествия и книги`\n"
                "`/fake Максим Мужской 30 Санкт-Петербург Активный образ жизни https://example.com/photo.jpg`\n\n"
                "*Параметры:*\n"
                "• Имя - любое имя (без пробелов)\n"
                "• Пол: Мужской или Женский\n"
                "• Возраст: число от 18 до 99\n"
                "• Город: название города\n"
                "• Биография: текст о себе\n"
                "• [фото_ссылка]: опционально, URL фотографии",
                parse_mode="Markdown"
            )
            return
        
        # Извлекаем параметры
        name = parts[1]
        gender = parts[2]
        age_str = parts[3]
        city = parts[4]
        bio = parts[5]
        photo_url = parts[6] if len(parts) > 6 else None
        
        # Валидация параметров
        if gender not in ["Мужской", "Женский"]:
            bot.send_message(message.chat.id, "❌ Пол должен быть 'Мужской' или 'Женский'")
            return
        
        try:
            age = int(age_str)
            if age < 18 or age > 99:
                bot.send_message(message.chat.id, "❌ Возраст должен быть от 18 до 99 лет")
                return
        except ValueError:
            bot.send_message(message.chat.id, "❌ Возраст должен быть числом")
            return
        
        if len(bio) > 500:
            bot.send_message(message.chat.id, "❌ Биография слишком длинная (макс 500 символов)")
            return
        
        # Генерируем случайную дату рождения для указанного возраста
        from datetime import datetime, timedelta
        import random
        
        current_year = datetime.now().year
        birth_year = current_year - age
        birth_month = random.randint(1, 12)
        birth_day = random.randint(1, 28)
        
        birthday = f"{birth_day:02d}.{birth_month:02d}.{birth_year}"
        
        # Генерируем знак зодиака по дате рождения
        zodiac = get_zodiac_sign(birth_day, birth_month)
        
        # Генерируем уникальный ID для фейкового пользователя
        fake_user_id = f"-9{random.randint(10000000, 99999999)}"
        
        # Проверяем, не существует ли уже такого ID
        while db.user_exists(fake_user_id):
            fake_user_id = f"-9{random.randint(10000000, 99999999)}"
        
        # Обрабатываем фото
        photo_file_bytes = None
        photo_id = None
        
        if photo_url:
            try:
                # Загружаем фото по URL
                response = requests.get(photo_url, timeout=10)
                if response.status_code == 200:
                    photo_file_bytes = response.content
                    
                    # Отправляем фото в чат, чтобы получить photo_id для запасного варианта
                    photo_data = BytesIO(photo_file_bytes)
                    photo_data.name = 'photo.jpg'
                    
                    sent_photo = bot.send_photo(message.chat.id, photo_data)
                    photo_id = sent_photo.photo[-1].file_id if sent_photo.photo else None
                    
                    # Удаляем служебное сообщение
                    try:
                        bot.delete_message(message.chat.id, sent_photo.message_id)
                    except:
                        pass
                else:
                    bot.send_message(message.chat.id, f"❌ Не удалось загрузить фото. Код ошибки: {response.status_code}")
                    return
                    
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Ошибка при загрузке фото: {str(e)}")
                return
        
        # Если фото не указано, используем случайное фото по умолчанию
        if not photo_file_bytes:
            # Списки путей к локальным фото-заглушкам
            default_photos_local = {
                "Мужской": ["default_male1.jpg", "default_male2.jpg"],
                "Женский": ["default_female1.jpg", "default_female2.jpg"]
            }
            
            # Загружаем локальное фото-заглушку
            gender_key = gender
            if gender_key in default_photos_local:
                photo_filename = random.choice(default_photos_local[gender_key])
                photo_path = os.path.join("default_photos", photo_filename)
                
                if os.path.exists(photo_path):
                    with open(photo_path, 'rb') as f:
                        photo_file_bytes = f.read()
                else:
                    print(f"⚠️ Локальное фото-заглушка не найдено: {photo_path}")
        
        # Создаем фейковый профиль в базе данных с локальным фото
        success = db.save_user(
            user_id=fake_user_id,
            name=name,
            gender=gender,
            birthday=birthday,
            age=age,
            photo_file=photo_file_bytes,  # Байты фото для локального сохранения
            photo_id=photo_id,  # Telegram file_id как запасной вариант
            bio=bio,
            zodiac=zodiac,
            city=city,
            is_fake=1,
            balance=random.randint(0, 10)
        )
        
        if success:
            # Получаем путь к сохраненному фото для отображения
            saved_photo_path = db.get_user_photo_path(fake_user_id)
            
            # Отправляем подтверждение администратору
            if saved_photo_path and os.path.exists(saved_photo_path):
                with open(saved_photo_path, 'rb') as photo_file:
                    bot.send_photo(
                        message.chat.id,
                        photo_file,
                        caption=(
                            f"✅ *Фейковая анкета создана!*\n\n"
                            f"👤 *Имя:* {name}\n"
                            f"⚧ *Пол:* {gender}\n"
                            f"🎂 *Возраст:* {age} лет\n"
                            f"📅 *ДР:* {birthday}\n"
                            f"♈ *Знак зодиака:* {zodiac}\n"
                            f"🏙️ *Город:* {city}\n"
                            f"📝 *О себе:* {bio}\n"
                            f"🆔 *ID:* `{fake_user_id}`\n"
                            f"💰 *Баланс:* {random.randint(0, 10)} монет\n"
                            f"📸 *Фото:* ✅ Локально сохранено\n\n"
                            f"*Анкета будет доступна другим пользователям для просмотра.*"
                        ),
                        parse_mode="Markdown"
                    )
            else:
                bot.send_message(
                    message.chat.id,
                    f"✅ *Фейковая анкета создана!*\n\n"
                    f"👤 *Имя:* {name}\n"
                    f"⚧ *Пол:* {gender}\n"
                    f"🎂 *Возраст:* {age} лет\n"
                    f"📅 *ДР:* {birthday}\n"
                    f"♈ *Знак зодиака:* {zodiac}\n"
                    f"🏙️ *Город:* {city}\n"
                    f"📝 *О себе:* {bio}\n"
                    f"🆔 *ID:* `{fake_user_id}`\n"
                    f"💰 *Баланс:* {random.randint(0, 10)} монет\n"
                    f"📸 *Фото:* {'✅ Telegram ID' if photo_id else '❌ Нет фото'}\n\n"
                    f"*Анкета будет доступна другим пользователям для просмотра.*",
                    parse_mode="Markdown"
                )
            
            print(f"🔄 Админ {user_id} создал фейковую анкету: {fake_user_id} ({name})")
            
        else:
            bot.send_message(message.chat.id, "❌ Ошибка при создании анкеты в базе данных")
            
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ *Ошибка создания фейковой анкеты:*\n```{str(e)}```",
            parse_mode="Markdown"
        )
        print(f"Ошибка в команде /fake: {e}")
@bot.message_handler(commands=["fake_bulk"])
def fake_bulk_command(message: Message):
    """Создание нескольких фейковых анкет одной командой"""
    user_id = str(message.from_user.id)
    
    # Проверяем права администратора
    if not is_admin(int(user_id)):
        bot.send_message(message.chat.id, "❌ Эта команда только для администратора.")
        return
    
    try:
        # Парсим команду: /fake_bulk <количество> [фото_url]
        parts = message.text.split(maxsplit=2)
        
        if len(parts) < 2:
            bot.send_message(
                message.chat.id,
                "❌ *Неверный формат команды!*\n\n"
                "Используйте:\n"
                "`/fake_bulk <количество> [фото_ссылка]`\n\n"
                "*Примеры:*\n"
                "`/fake_bulk 10` - создаст 10 фейковых анкет\n"
                "`/fake_bulk 5 https://example.com/photo.jpg` - создаст 5 анкет с указанной фотографией",
                parse_mode="Markdown"
            )
            return
        
        count = int(parts[1])
        bulk_photo_url = parts[2] if len(parts) > 2 else None
        
        if count < 1 or count > 50:
            bot.send_message(message.chat.id, "❌ Количество должно быть от 1 до 50")
            return
        
        # Загружаем общее фото, если указано
        bulk_photo_id = None
        if bulk_photo_url:
            try:
                status_msg = bot.send_message(message.chat.id, "🔄 Загружаю общую фотографию...")
                
                import requests
                from io import BytesIO
                
                response = requests.get(bulk_photo_url, timeout=10)
                if response.status_code == 200:
                    photo_data = BytesIO(response.content)
                    photo_data.name = 'photo.jpg'
                    
                    sent_photo = bot.send_photo(message.chat.id, photo_data)
                    bulk_photo_id = sent_photo.photo[-1].file_id if sent_photo.photo else None
                    
                    # Удаляем служебные сообщения
                    try:
                        bot.delete_message(message.chat.id, status_msg.message_id)
                        bot.delete_message(message.chat.id, sent_photo.message_id)
                    except:
                        pass
                else:
                    bot.send_message(message.chat.id, f"❌ Не удалось загрузить общую фотографию")
                    return
                    
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Ошибка при загрузке фото: {str(e)}")
                return
        
        # Отправляем подтверждение начала процесса
        msg = bot.send_message(
            message.chat.id,
            f"🔄 *Создание {count} фейковых анкет...*",
            parse_mode="Markdown"
        )
        
        # Списки для генерации случайных данных
        male_names = ["Алексей", "Дмитрий", "Сергей", "Андрей", "Максим", "Иван", "Артем", "Михаил", "Роман", "Николай"]
        female_names = ["Анна", "Елена", "Мария", "Ольга", "Наталья", "Ирина", "Светлана", "Татьяна", "Екатерина", "Юлия"]
        cities = ["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань", "Нижний Новгород", "Челябинск", "Самара", "Омск", "Ростов-на-Дону"]
        hobbies = [
    {
        "base": "путешествия",
        "acc": "путешествия",
        "inst": "путешествиями"
    },
    {
        "base": "книги",
        "acc": "книги",
        "inst": "книгами"
    },
    {
        "base": "спорт",
        "acc": "спорт",
        "inst": "спортом"
    },
    {
        "base": "кино",
        "acc": "кино",
        "inst": "кино"
    },
    {
        "base": "музыка",
        "acc": "музыку",
        "inst": "музыкой"
    },
    {
        "base": "готовка",
        "acc": "готовку",
        "inst": "готовкой"
    },
    {
        "base": "фотография",
        "acc": "фотографию",
        "inst": "фотографией"
    },
    {
        "base": "искусство",
        "acc": "искусство",
        "inst": "искусством"
    },
    {
        "base": "прогулки",
        "acc": "прогулки",
        "inst": "прогулками"
    },
    {
        "base": "танцы",
        "acc": "танцы",
        "inst": "танцами"
    }
]
        
        # Списки ID случайных фото (добавьте свои file_id)
        default_photos = {
            "Мужской": [
                "AgACAgIAAxkBAAICBmlpBYyJ6wl8qot0EjoYERiRQdLlAAIdEGsbDrtJS55UJQ4fDF1tAQADAgADeAADOAQ",
                "AgACAgIAAxkBAAICBGlpBXt6y-HCXTvHNPx6Pv6HHbCKAAIcEGsbDrtJS1FIdxkNmVFQAQADAgADeQADOAQ",
            ],
            "Женский": [
                "AgACAgIAAxkBAAICCGlpBZ-ALRnL37FVmof6Q_9INqI9AAIeEGsbDrtJSxHBoGSCrfJsAQADAgADeQADOAQ",
                "AgACAgIAAxkBAAICAmlpBVYqmVlYP1ITM-rTYSDWECQ3AAIbEGsbDrtJS_KF-rT8rL4AAQEAAwIAA3gAAzgE",
            ]
        }
        
        created_count = 0
        errors = []
        
        for i in range(count):
            try:
                # Случайно выбираем пол
                if random.choice([True, False]):
                    gender = "Мужской"
                    name = random.choice(male_names)
                else:
                    gender = "Женский"
                    name = random.choice(female_names)
                
                # Случайный возраст
                age = random.randint(18, 45)
                
                # Случайный город
                city = random.choice(cities)
                
                # Генерируем био
                hobby1 = random.choice(hobbies)
                hobby2 = random.choice([h for h in hobbies if h != hobby1])

                bios = [
                    "Люблю жизнь и людей",
                    "В поиске своего человека",
                    "Просто живу и радуюсь мелочам",
                    "Люблю уют и спокойствие",
                    "За простоту и искренность",
                    "Ценю честность и юмор",
                    "Нравится узнавать новое",
                    "Люблю хорошие разговоры",
                    "Иногда интроверт, иногда нет",
                    "Сложно описать себя в двух словах",

                    # --- с хобби ---
                    f"Увлекаюсь {hobby1['inst']}",
                    f"Люблю {hobby1['acc']}",
                    f"Интересуюсь {hobby1['inst']} и {hobby2['inst']}",
                    f"{hobby1['base'].capitalize()} — моя отдушина",
                    f"Свободное время — это {hobby1['base']}",
                    f"Люблю {hobby1['acc']}, иногда {hobby2['acc']}",
                    f"Если не знаю, чем заняться — выбираю {hobby1['acc']}",
                    f"{hobby1['base'].capitalize()} и хорошие люди рядом",

                    # --- тёплые ---
                    "Люблю тёплые вечера и душевные разговоры",
                    "Важно чувствовать себя на своём месте",
                    "Ценю заботу и внимание",
                    "Люблю, когда рядом спокойно",
                    "Хочется простого человеческого счастья",
                    "Нравится, когда можно быть собой",
                    "Про тепло, искренность и доверие",

                    # --- ирония ---
                    "Не умею писать био, но стараюсь",
                    "Сюда обычно пишут что-то умное",
                    "Люблю вкусно поесть и хорошо поспать",
                    "Могу поддержать разговор и шутку",
                    "Ищу не идеал, а человека",
                    "Если ты читаешь это — привет 🙂",
                    "Анкета есть, осталось знакомство",

                    # --- с эмодзи ---
                    f"Люблю {hobby1['acc']} 💫",
                    f"{hobby1['base'].capitalize()} и хорошее настроение ☀️",
                    "За уют и тёплый чай ☕",
                    "Люблю простые радости ✨",
                    "Немного романтик 🌙",
                    "В поиске вдохновения 🌿",

                    # --- минимализм ---
                    "🙂",
                    "✨",
                    "Пока без описания",
                    "Сложно описать",
                    "Позже допишу",
                    "-",
                    "",

                    # --- длиннее ---
                    f"Люблю {hobby1['acc']}, ценю спокойствие и хорошие разговоры",
                    f"{hobby1['base'].capitalize()} помогает отвлечься и перезагрузиться",
                    f"Интересуюсь {hobby1['inst']}, иногда {hobby2['inst']}, остальное — по настроению",
                    "Люблю, когда день заканчивается чем-то приятным",
                    "Ищу человека, с которым будет легко",
                ]


                if random.randint(1, 100) < 50:
                    bio = random.choice(bios)
                else:
                    bio = ''
                
                # Генерируем дату рождения
                current_year = datetime.now().year
                birth_year = current_year - age
                birth_month = random.randint(1, 12)
                birth_day = random.randint(1, 28)
                birthday = f"{birth_day:02d}.{birth_month:02d}.{birth_year}"
                
                # Знак зодиака
                zodiac = get_zodiac_sign(birth_day, birth_month)
                
                # Выбираем фото
                if bulk_photo_id:
                    # Используем общее фото для всех анкет
                    photo_id = bulk_photo_id
                else:
                    # Выбираем случайное фото по полу
                    gender_key = gender
                    if gender_key in default_photos and default_photos[gender_key]:
                        photo_id = random.choice(default_photos[gender_key])
                    else:
                        photo_id = "AgACAgIAAxkBAAICAmlpBVYqmVlYP1ITM-rTYSDWECQ3AAIbEGsbDrtJS_KF-rT8rL4AAQEAAwIAA3gAAzgE"
                
                # Генерируем уникальный ID
                fake_user_id = f"-9{random.randint(10000000, 99999999)}"
                while db.user_exists(fake_user_id):
                    fake_user_id = f"-9{random.randint(10000000, 99999999)}"
                
                # Сохраняем в базу
                success = db.save_user(
                    user_id=fake_user_id,
                    name=f"{name}",
                    gender=gender,
                    birthday=birthday,
                    age=age,
                    photo_id=photo_id,
                    bio=bio,
                    zodiac=zodiac,
                    city=city,
                    is_fake=1,
                    balance=random.randint(0, 10)
                )
                
                if success:
                    created_count += 1
                else:
                    errors.append(f"Ошибка при сохранении анкеты #{i+1}")
                
                # Обновляем статус каждые 5 созданных анкет
                if (i + 1) % 5 == 0:
                    try:
                        bot.edit_message_text(
                            f"🔄 *Создание фейковых анкет...*\n\n"
                            f"📊 *Прогресс:* {i+1}/{count}\n"
                            f"✅ *Успешно:* {created_count}",
                            chat_id=message.chat.id,
                            message_id=msg.message_id,
                            parse_mode="Markdown"
                        )
                    except:
                        pass
                
                # Небольшая задержка, чтобы не перегружать базу
                time.sleep(0.1)
                
            except Exception as e:
                errors.append(f"Ошибка при создании анкеты #{i+1}: {str(e)}")
        
        # Отправляем отчет
        result_text = f"✅ *Создание фейковых анкет завершено!*\n\n"
        result_text += f"📊 *Результат:*\n"
        result_text += f"• Успешно создано: {created_count}/{count}\n"
        result_text += f"• Использовано фото: {'Да' if bulk_photo_id else 'Нет'}\n"
        
        if errors:
            result_text += f"• Ошибок: {len(errors)}\n"
            if len(errors) <= 5:  # Показываем только первые 5 ошибок
                result_text += "\n*Последние ошибки:*\n"
                for error in errors[-5:]:
                    result_text += f"• {error}\n"
        
        # Показываем пример созданной анкеты
        if created_count > 0:
            result_text += f"\n📝 *Пример созданной анкеты:*\n"
            result_text += f"Имя: {name}\n"
            result_text += f"Пол: {gender}\n"
            result_text += f"Возраст: {age}\n"
            result_text += f"Город: {city}\n"
            result_text += f"Био: {bio}\n"
        
        bot.edit_message_text(
            result_text,
            chat_id=message.chat.id,
            message_id=msg.message_id,
            parse_mode="Markdown"
        )
        
        # Логируем создание
        print(f"🔄 Админ {user_id} создал {created_count} фейковых анкет с фото")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Количество должно быть числом")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

@bot.message_handler(commands=["fake_clean"])
def fake_clean_command(message: Message):
    """Удаление всех фейковых анкет"""
    user_id = str(message.from_user.id)
    
    # Проверяем права администратора
    if not is_admin(int(user_id)):
        bot.send_message(message.chat.id, "❌ Эта команда только для администратора.")
        return
    
    # Запрашиваем подтверждение
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Да, удалить все фейки", callback_data="delete_all_fakes"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_delete")
    )
    
    # Сначала получаем количество фейковых анкет
    fake_count = db.get_fake_users_count()
    
    bot.send_message(
        message.chat.id,
        f"⚠️ *ВНИМАНИЕ!*\n\n"
        f"Вы собираетесь удалить *ВСЕ* фейковые анкеты.\n\n"
        f"📊 *Статистика:*\n"
        f"• Фейковых анкет найдено: {fake_count}\n\n"
        f"*Это действие необратимо!*\n"
        f"Подтвердите удаление:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == "delete_all_fakes")
def delete_all_fakes_callback(call: CallbackQuery):
    """Обработчик удаления всех фейковых анкет"""
    user_id = str(call.from_user.id)
    
    if not is_admin(int(user_id)):
        bot.answer_callback_query(call.id, "❌ Нет прав", show_alert=True)
        return
    
    try:
        # Получаем количество перед удалением
        before_count = db.get_fake_users_count()
        
        # Удаляем фейковые анкеты
        deleted_count = db.delete_all_fake_users()
        
        # Отправляем результат
        bot.edit_message_text(
            f"✅ *Фейковые анкеты удалены!*\n\n"
            f"📊 *Результат:*\n"
            f"• Удалено анкет: {deleted_count}\n"
            f"• Осталось фейков: 0",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )
        
        print(f"🔄 Админ {user_id} удалил {deleted_count} фейковых анкет")
        
    except Exception as e:
        bot.edit_message_text(
            f"❌ *Ошибка при удалении:*\n```{str(e)}```",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: call.data == "cancel_delete")
def cancel_delete_callback(call: CallbackQuery):
    """Отмена удаления"""
    bot.edit_message_text(
        "❌ *Удаление отменено*",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )
    bot.answer_callback_query(call.id)

    
@bot.message_handler(content_types=['photo'])
def get_photo_id(message):
    photo_id = message.photo[-1].file_id
    bot.send_message(message.chat.id, f"Photo ID: `{photo_id}`", parse_mode="Markdown")

# Запуск бота
if __name__ == "__main__":
    # Настраиваем меню команд
    setup_bot_menu()
    
    # Очищаем потерянные фото при запуске
    try:
        orphaned_count = db.cleanup_orphaned_photos()
        if orphaned_count > 0:
            print(f"🧹 Очищено потерянных фото: {orphaned_count}")
    except Exception as e:
        print(f"⚠️ Ошибка при очистке фото: {e}")
    
    bot.add_custom_filter(StateFilter(bot))
    
    print("🤖 Бот для знакомств запущен!")
    print("📁 Данные сохраняются в базе данных SQLite")
    print("📸 Фотографии сохраняются локально в папке 'user_photos'")
    print("✨ Основные функции:")
    print("  • Регистрация с локальным сохранением фото")
    print("  • Просмотр анкет с фильтрами")
    print("  • Проверка совместимости по Матрице Судьбы")
    print("  • Система лайков и взаимных симпатий")
    
    # Проверяем, работает ли база данных
    try:
        user_count = db.get_user_count()
        fake_count = db.get_fake_users_count()
        print(f"  • Пользователей в базе: {user_count}")
        print(f"  • Фейковых анкет: {fake_count}")
    except Exception as e:
        print(f"  ⚠️ Ошибка подключения к базе данных: {e}")
    
    bot.polling(none_stop=True)

