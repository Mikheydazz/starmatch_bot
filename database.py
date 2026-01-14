import sqlite3
import threading
from datetime import datetime
import json

class Database:
    def __init__(self, db_name='bot_database.db'):
        self.db_name = db_name
        self.lock = threading.Lock()
        self.init_database()
    
    def get_connection(self):
        """Создает и возвращает соединение с базой данных"""
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Инициализирует все таблицы в базе данных"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Создаем таблицу пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    gender TEXT NOT NULL,
                    birthday TEXT NOT NULL,
                    age INTEGER NOT NULL,
                    photo_id TEXT,
                    bio TEXT NOT NULL,
                    zodiac TEXT NOT NULL,
                    city TEXT,
                    balance INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_hidden INTEGER DEFAULT 0
                )
            ''')
            
            # Создаем таблицу лайков
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS likes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    liked_user_id TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, liked_user_id)
                )
            ''')
            
            # Создаем таблицу жалоб
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reported_user_id TEXT NOT NULL,
                    reporter_user_id TEXT NOT NULL,
                    reason TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Создаем таблицу заблокированных пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS banned_users (
                    user_id TEXT PRIMARY KEY,
                    reason TEXT,
                    banned_by TEXT,
                    banned_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            print("✅ База данных инициализирована")
    
    def check_column_exists(self, table, column):
        """Проверяет существование столбца в таблице"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("PRAGMA table_info(?)", (table,))
            columns = [col[1] for col in cursor.fetchall()]
            
            conn.close()
            return column in columns
    
    # ===== ОСНОВНЫЕ МЕТОДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ =====
    
    def save_user(self, user_id, name, gender, birthday, age, photo_id, bio, zodiac, city=None, balance=0):
        """Сохраняет нового пользователя или обновляет существующего"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO users 
                    (user_id, name, gender, birthday, age, photo_id, bio, zodiac, city, balance)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, name, gender, birthday, age, photo_id, bio, zodiac, city, balance))
                
                conn.commit()
                conn.close()
                return True
            except sqlite3.Error as e:
                print(f"❌ Ошибка сохранения пользователя: {e}")
                return False
    
    def get_user(self, user_id):
        """Получает данные пользователя по ID"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                
                conn.close()
                
                if row:
                    return dict(row)
                return None
            except sqlite3.Error as e:
                print(f"❌ Ошибка получения пользователя: {e}")
                return None
    
    def user_exists(self, user_id):
        """Проверяет существование пользователя"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM users WHERE user_id = ?", (user_id,))
                count = cursor.fetchone()[0]
                
                conn.close()
                return count > 0
            except sqlite3.Error as e:
                print(f"❌ Ошибка проверки пользователя: {e}")
                return False
    
    def update_user_balance(self, user_id, amount):
        """Обновляет баланс пользователя"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (amount, user_id)
                )
                
                conn.commit()
                conn.close()
                return True
            except sqlite3.Error as e:
                print(f"❌ Ошибка обновления баланса: {e}")
                return False
    
    def get_user_count(self):
        """Получает общее количество пользователей"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM users")
                count = cursor.fetchone()[0]
                
                conn.close()
                return count
            except sqlite3.Error as e:
                print(f"❌ Ошибка получения количества пользователей: {e}")
                return 0
    
    # ===== МЕТОДЫ ДЛЯ ЛАЙКОВ =====
    
    def add_like(self, user_id, liked_user_id):
        """Добавляет лайк и проверяет взаимность"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                # Проверяем, не лайкал ли уже
                cursor.execute(
                    "SELECT COUNT(*) FROM likes WHERE user_id = ? AND liked_user_id = ?",
                    (user_id, liked_user_id)
                )
                if cursor.fetchone()[0] > 0:
                    conn.close()
                    return False  # Уже лайкал
                
                # Добавляем лайк
                cursor.execute(
                    "INSERT INTO likes (user_id, liked_user_id) VALUES (?, ?)",
                    (user_id, liked_user_id)
                )
                
                # Проверяем взаимность
                cursor.execute(
                    "SELECT COUNT(*) FROM likes WHERE user_id = ? AND liked_user_id = ?",
                    (liked_user_id, user_id)
                )
                is_mutual = cursor.fetchone()[0] > 0
                
                conn.commit()
                conn.close()
                return is_mutual
            except sqlite3.Error as e:
                print(f"❌ Ошибка добавления лайка: {e}")
                return False
    
    def is_mutual_like(self, user_id, target_id):
        """Проверяет взаимный лайк"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT 
                        (SELECT COUNT(*) FROM likes WHERE user_id = ? AND liked_user_id = ?) as user_likes_target,
                        (SELECT COUNT(*) FROM likes WHERE user_id = ? AND liked_user_id = ?) as target_likes_user
                ''', (user_id, target_id, target_id, user_id))
                
                row = cursor.fetchone()
                is_mutual = row['user_likes_target'] > 0 and row['target_likes_user'] > 0
                
                conn.close()
                return is_mutual
            except sqlite3.Error as e:
                print(f"❌ Ошибка проверки взаимного лайка: {e}")
                return False
    
    def get_mutual_likes(self, user_id):
        """Получает список взаимных лайков"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT u.* FROM users u
                    JOIN likes l1 ON u.user_id = l1.user_id
                    JOIN likes l2 ON l1.user_id = l2.liked_user_id AND l1.liked_user_id = l2.user_id
                    WHERE l1.liked_user_id = ? AND l2.liked_user_id = ?
                ''', (user_id, user_id))
                
                rows = cursor.fetchall()
                mutual_likes = [dict(row) for row in rows]
                
                conn.close()
                return mutual_likes
            except sqlite3.Error as e:
                print(f"❌ Ошибка получения взаимных лайков: {e}")
                return []
    
    def get_likes_count(self, user_id):
        """Получает количество лайков пользователя"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT COUNT(*) FROM likes WHERE liked_user_id = ?",
                    (user_id,)
                )
                count = cursor.fetchone()[0]
                
                conn.close()
                return count
            except sqlite3.Error as e:
                print(f"❌ Ошибка получения количества лайков: {e}")
                return 0
    
    # ===== МЕТОДЫ ДЛЯ ЖАЛОБ =====
    
    def add_report(self, reported_user_id, reporter_user_id, reason=None):
        """Добавляет жалобу на пользователя"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                # Проверяем, не жаловался ли уже
                cursor.execute(
                    "SELECT COUNT(*) FROM reports WHERE reported_user_id = ? AND reporter_user_id = ?",
                    (reported_user_id, reporter_user_id)
                )
                if cursor.fetchone()[0] > 0:
                    conn.close()
                    return False  # Уже жаловался
                
                # Добавляем жалобу
                cursor.execute(
                    "INSERT INTO reports (reported_user_id, reporter_user_id, reason) VALUES (?, ?, ?)",
                    (reported_user_id, reporter_user_id, reason)
                )
                
                conn.commit()
                conn.close()
                return True
            except sqlite3.Error as e:
                print(f"❌ Ошибка добавления жалобы: {e}")
                return False
    
    def get_report_count(self, user_id):
        """Получает количество жалоб на пользователя"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT COUNT(*) FROM reports WHERE reported_user_id = ?",
                    (user_id,)
                )
                count = cursor.fetchone()[0]
                
                conn.close()
                return count
            except sqlite3.Error as e:
                print(f"❌ Ошибка получения количества жалоб: {e}")
                return 0
    
    def get_user_reports_details(self, user_id):
        """Получает детали жалоб на пользователя"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT r.*, u.name as reporter_name 
                    FROM reports r
                    LEFT JOIN users u ON r.reporter_user_id = u.user_id
                    WHERE r.reported_user_id = ?
                    ORDER BY r.timestamp DESC
                ''', (user_id,))
                
                rows = cursor.fetchall()
                reports = [dict(row) for row in rows]
                
                conn.close()
                return reports
            except sqlite3.Error as e:
                print(f"❌ Ошибка получения деталей жалоб: {e}")
                return []
    
    def delete_reports_for_user(self, user_id):
        """Удаляет все жалобы на пользователя"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT COUNT(*) FROM reports WHERE reported_user_id = ?",
                    (user_id,)
                )
                count_before = cursor.fetchone()[0]
                
                cursor.execute(
                    "DELETE FROM reports WHERE reported_user_id = ?",
                    (user_id,)
                )
                
                conn.commit()
                conn.close()
                return count_before
            except sqlite3.Error as e:
                print(f"❌ Ошибка удаления жалоб: {e}")
                return 0
    
    def get_users_with_reports(self, limit=50):
        """Получает пользователей с жалобами"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT u.*, COUNT(r.id) as report_count, 
                           GROUP_CONCAT(DISTINCT r.reason) as reasons
                    FROM users u
                    LEFT JOIN reports r ON u.user_id = r.reported_user_id
                    GROUP BY u.user_id
                    HAVING report_count > 0
                    ORDER BY report_count DESC
                    LIMIT ?
                ''', (limit,))
                
                rows = cursor.fetchall()
                users = []
                
                for row in rows:
                    user = dict(row)
                    if user['reasons']:
                        user['reasons'] = user['reasons'].split(',')
                    else:
                        user['reasons'] = []
                    users.append(user)
                
                conn.close()
                return users
            except sqlite3.Error as e:
                print(f"❌ Ошибка получения пользователей с жалобами: {e}")
                return []
    
    # ===== МЕТОДЫ ДЛЯ БАНА =====
    
    def ban_user(self, user_id, reason, banned_by="admin"):
        """Блокирует пользователя"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                # Проверяем, не забанен ли уже
                cursor.execute(
                    "SELECT COUNT(*) FROM banned_users WHERE user_id = ?",
                    (user_id,)
                )
                if cursor.fetchone()[0] > 0:
                    # Обновляем существующую запись
                    cursor.execute(
                        "UPDATE banned_users SET reason = ?, banned_by = ?, banned_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                        (reason, banned_by, user_id)
                    )
                else:
                    # Добавляем новую запись
                    cursor.execute(
                        "INSERT INTO banned_users (user_id, reason, banned_by) VALUES (?, ?, ?)",
                        (user_id, reason, banned_by)
                    )
                
                conn.commit()
                conn.close()
                return True
            except sqlite3.Error as e:
                print(f"❌ Ошибка блокировки пользователя: {e}")
                return False
    
    def unban_user(self, user_id):
        """Разблокирует пользователя"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute(
                    "DELETE FROM banned_users WHERE user_id = ?",
                    (user_id,)
                )
                
                conn.commit()
                conn.close()
                return True
            except sqlite3.Error as e:
                print(f"❌ Ошибка разблокировки пользователя: {e}")
                return False
    
    def is_user_banned(self, user_id):
        """Проверяет, заблокирован ли пользователь"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT COUNT(*) FROM banned_users WHERE user_id = ?",
                    (user_id,)
                )
                count = cursor.fetchone()[0]
                
                conn.close()
                return count > 0
            except sqlite3.Error as e:
                print(f"❌ Ошибка проверки блокировки: {e}")
                return False
    
    def get_banned_users(self):
        """Получает список заблокированных пользователей"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT b.*, u.name 
                    FROM banned_users b
                    LEFT JOIN users u ON b.user_id = u.user_id
                    ORDER BY b.banned_at DESC
                ''')
                
                rows = cursor.fetchall()
                banned_users = [dict(row) for row in rows]
                
                conn.close()
                return banned_users
            except sqlite3.Error as e:
                print(f"❌ Ошибка получения заблокированных пользователей: {e}")
                return []
    
    # ===== МЕТОДЫ ДЛЯ ФИЛЬТРАЦИИ И ПОИСКА =====
    
    def get_all_users(self, exclude_user_id=None, limit=100):
        """Получает всех пользователей (без учета скрытых)"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                query = "SELECT * FROM users WHERE 1=1"
                params = []
                
                if exclude_user_id:
                    query += " AND user_id != ?"
                    params.append(exclude_user_id)
                
                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                users = [dict(row) for row in rows]
                
                conn.close()
                return users
            except sqlite3.Error as e:
                print(f"❌ Ошибка получения всех пользователей: {e}")
                return []
    
    def get_users_by_filters(self, exclude_user_id=None, gender=None, zodiac=None, city_filter=None, limit=100):
        """Получает пользователей по фильтрам с учетом скрытых профилей и блокировок"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                # Проверяем существование столбца is_hidden
                cursor.execute("PRAGMA table_info(users)")
                columns = [col[1] for col in cursor.fetchall()]
                
                # Начинаем запрос
                query = """
                    SELECT u.* FROM users u
                    WHERE u.user_id != ?
                    AND u.user_id NOT IN (SELECT user_id FROM banned_users)
                """
                params = [exclude_user_id]
                
                # Добавляем проверку на is_hidden только если столбец существует
                if 'is_hidden' in columns:
                    query += " AND (u.is_hidden IS NULL OR u.is_hidden = 0)"
                
                # Добавляем фильтры
                if gender:
                    query += " AND u.gender = ?"
                    params.append(gender)
                
                if zodiac:
                    query += " AND u.zodiac = ?"
                    params.append(zodiac)
                
                if city_filter == "same_city":
                    # Получаем город текущего пользователя
                    cursor.execute("SELECT city FROM users WHERE user_id = ?", (exclude_user_id,))
                    user_city = cursor.fetchone()
                    if user_city and user_city[0]:
                        query += " AND u.city = ?"
                        params.append(user_city[0])
                
                query += " ORDER BY u.created_at DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                users = [dict(row) for row in rows]
                
                conn.close()
                return users
            except sqlite3.Error as e:
                print(f"❌ Ошибка получения пользователей по фильтрам: {e}")
                return []
            
    
    
    def get_users_by_filters_safe(self, exclude_user_id=None, gender=None, zodiac=None, city_filter=None, limit=100):
        """Безопасная версия get_users_by_filters с обработкой ошибок"""
        try:
            return self.get_users_by_filters(exclude_user_id, gender, zodiac, city_filter, limit)
        except sqlite3.OperationalError as e:
            if "no such column: is_hidden" in str(e):
                print("⚠️ Столбец is_hidden не найден, используем упрощенный запрос")
                # Используем упрощенный запрос без is_hidden
                return self.get_all_users(exclude_user_id, limit)
            else:
                raise e
    
    # ===== МЕТОДЫ ДЛЯ СКРЫТИЯ/ПОКАЗА ПРОФИЛЕЙ =====
    
    def hide_user_profile(self, user_id):
        """Скрывает профиль пользователя"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                # Проверяем существование столбца
                if not self.check_column_exists('users', 'is_hidden'):
                    # Добавляем столбец если его нет
                    cursor.execute("ALTER TABLE users ADD COLUMN is_hidden INTEGER DEFAULT 0")
                
                cursor.execute(
                    "UPDATE users SET is_hidden = 1 WHERE user_id = ?",
                    (user_id,)
                )
                
                conn.commit()
                conn.close()
                return True
            except sqlite3.Error as e:
                print(f"❌ Ошибка скрытия профиля: {e}")
                return False
    
    def unhide_user_profile(self, user_id):
        """Показывает скрытый профиль"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                # Проверяем существование столбца
                if not self.check_column_exists('users', 'is_hidden'):
                    # Если столбца нет, нечего обновлять
                    conn.close()
                    return True
                
                cursor.execute(
                    "UPDATE users SET is_hidden = 0 WHERE user_id = ?",
                    (user_id,)
                )
                
                conn.commit()
                conn.close()
                return True
            except sqlite3.Error as e:
                print(f"❌ Ошибка показа профиля: {e}")
                return False
    
    def is_profile_hidden(self, user_id):
        """Проверяет, скрыт ли профиль"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                # Проверяем существование столбца
                if not self.check_column_exists('users', 'is_hidden'):
                    conn.close()
                    return False
                
                cursor.execute(
                    "SELECT is_hidden FROM users WHERE user_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()
                
                conn.close()
                
                if result:
                    return result[0] == 1
                return False
            except sqlite3.Error as e:
                print(f"❌ Ошибка проверки скрытия профиля: {e}")
                return False
    
    # ===== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =====
    
    def cleanup_old_data(self, days=30):
        """Очищает старые данные (жалобы старше X дней)"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                cursor.execute(
                    "DELETE FROM reports WHERE timestamp < datetime('now', '-? days')",
                    (days,)
                )
                
                deleted_count = cursor.rowcount
                conn.commit()
                conn.close()
                
                return deleted_count
            except sqlite3.Error as e:
                print(f"❌ Ошибка очистки старых данных: {e}")
                return 0
    
    def get_database_stats(self):
        """Получает статистику базы данных"""
        with self.lock:
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                stats = {}
                
                # Количество пользователей
                cursor.execute("SELECT COUNT(*) FROM users")
                stats['total_users'] = cursor.fetchone()[0]
                
                # Количество лайков
                cursor.execute("SELECT COUNT(*) FROM likes")
                stats['total_likes'] = cursor.fetchone()[0]
                
                # Количество жалоб
                cursor.execute("SELECT COUNT(*) FROM reports")
                stats['total_reports'] = cursor.fetchone()[0]
                
                # Количество заблокированных
                cursor.execute("SELECT COUNT(*) FROM banned_users")
                stats['total_banned'] = cursor.fetchone()[0]
                
                conn.close()
                return stats
            except sqlite3.Error as e:
                print(f"❌ Ошибка получения статистики: {e}")
                return {}
    
    def backup_database(self, backup_name=None):
        """Создает резервную копию базы данных"""
        import shutil
        import time
        
        if not backup_name:
            backup_name = f"backup_{int(time.time())}.db"
        
        try:
            shutil.copy2(self.db_name, backup_name)
            return backup_name
        except Exception as e:
            print(f"❌ Ошибка создания резервной копии: {e}")
            return None

# Тестирование базы данных при прямом запуске
if __name__ == "__main__":
    db = Database('test_database.db')
    
    # Тестовые данные
    test_user = {
        'user_id': '12345',
        'name': 'Тестовый пользователь',
        'gender': 'Мужской',
        'birthday': '01.01.1990',
        'age': 34,
        'photo_id': 'test_photo',
        'bio': 'Тестовая биография',
        'zodiac': 'Овен ♈',
        'city': 'Москва',
        'balance': 100
    }
    
    # Сохраняем тестового пользователя
    success = db.save_user(**test_user)
    print(f"✅ Сохранение пользователя: {'Успешно' if success else 'Ошибка'}")
    
    # Получаем пользователя
    user = db.get_user('12345')
    print(f"✅ Получение пользователя: {'Найден' if user else 'Не найден'}")
    if user:
        print(f"   Имя: {user['name']}")
        print(f"   Баланс: {user['balance']}")
    
    # Тест лайков
    db.save_user(user_id='67890', name='Второй пользователь', gender='Женский',
                 birthday='01.01.1995', age=29, photo_id='photo2',
                 bio='Вторая биография', zodiac='Телец ♉', city='Санкт-Петербург', balance=50)
    
    # Добавляем лайк
    is_mutual = db.add_like('12345', '67890')
    print(f"✅ Добавление лайка (взаимность: {is_mutual})")
    
    # Добавляем ответный лайк
    is_mutual = db.add_like('67890', '12345')
    print(f"✅ Ответный лайк (взаимность: {is_mutual})")
    
    # Проверяем взаимность
    is_mutual_now = db.is_mutual_like('12345', '67890')
    print(f"✅ Проверка взаимности: {'Да' if is_mutual_now else 'Нет'}")
    
    # Получаем статистику
    stats = db.get_database_stats()
    print(f"📊 Статистика базы данных: {stats}")
    
    # Удаляем тестовую базу
    import os
    if os.path.exists('test_database.db'):
        os.remove('test_database.db')
        print("✅ Тестовая база данных удалена")