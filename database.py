import sqlite3
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

class Database:
    def __init__(self, db_file='bot_database.db'):
        self.db_file = db_file
        self._local = threading.local()
        self.init_database()
    
    def get_connection(self):
        """Получаем соединение с БД для текущего потока"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_file, 
                check_same_thread=False,
                timeout=10
            )
            self._local.conn.row_factory = sqlite3.Row  # Возвращаем словари
        return self._local.conn
    
    def init_database(self):
        """Инициализация всех таблиц"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 3,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                name TEXT NOT NULL,
                gender TEXT NOT NULL,
                birthday TEXT NOT NULL,
                age INTEGER NOT NULL,
                photo_id TEXT,
                bio TEXT NOT NULL,
                zodiac TEXT NOT NULL,
                city TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица лайков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id TEXT NOT NULL,
                to_user_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(from_user_id, to_user_id),
                FOREIGN KEY (from_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (to_user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # Таблица взаимных симпатий (оптимизированная версия)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mutual_likes (
                user1_id TEXT NOT NULL,
                user2_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user1_id, user2_id),
                FOREIGN KEY (user1_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (user2_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # Таблица платежей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        ''')
        
        # Индексы для быстрого поиска
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_gender ON users(gender)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_city ON users(city)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_zodiac ON users(zodiac)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_likes_from ON likes(from_user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_likes_to ON likes(to_user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mutual_user1 ON mutual_likes(user1_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mutual_user2 ON mutual_likes(user2_id)')
        
        conn.commit()
    
    # === Методы для пользователей ===
    def user_exists(self, user_id: str) -> bool:
        """Проверить, существует ли пользователь"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
        return cursor.fetchone() is not None
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """Получить пользователя по ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def save_user(self, user_id: str, name: str, gender: str, birthday: str, age: int,
                  bio: str, zodiac: str, balance: int = 3, photo_id: str = None, 
                  city: str = None) -> bool:
        """Сохранить или обновить пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, name, gender, birthday, age, photo_id, bio, zodiac, 
                 city, balance, registered_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, name, gender, birthday, age, photo_id, bio, zodiac,
                city, balance, current_time, current_time
            ))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка сохранения пользователя {user_id}: {e}")
            return False
    
    def update_user_balance(self, user_id: str, delta: int) -> bool:
        """Обновить баланс пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE users SET balance = balance + ?, updated_at = ? WHERE user_id = ?',
                (delta, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Ошибка обновления баланса пользователя {user_id}: {e}")
            return False
    
    def get_user_count(self) -> int:
        """Получить общее количество пользователей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        return cursor.fetchone()[0]
    
    def get_all_users(self, exclude_user_id: str = None) -> List[Dict]:
        """Получить всех пользователей (кроме указанного)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if exclude_user_id:
            cursor.execute('SELECT * FROM users WHERE user_id != ?', (exclude_user_id,))
        else:
            cursor.execute('SELECT * FROM users')
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_users_by_filters(self, exclude_user_id=None, gender=None, zodiac=None, city_filter=None):
        """Получает пользователей по фильтрам"""
        query = "SELECT * FROM users WHERE user_id != ? AND (is_hidden IS NULL OR is_hidden = 0)"
        params = [exclude_user_id]
        
        # Фильтр по полу
        if gender:
            query += " AND gender = ?"
            params.append(gender)
        
        # Фильтр по знаку зодиака
        if zodiac:
            query += " AND zodiac LIKE ?"
            params.append(f"%{zodiac}%")
        
        # Фильтр по городу
        if city_filter:
            if city_filter == "same_city":
                # Получаем город текущего пользователя
                current_user = self.get_user(exclude_user_id)
                if current_user and current_user.get('city'):
                    query += " AND city = ?"
                    params.append(current_user['city'])
        
        query += " ORDER BY RANDOM()"  # Случайный порядок
        self.cursor.execute(query, params)
        
        users = self.cursor.fetchall()
        result = []
        
        for user in users:
            user_dict = {
                'user_id': user[0],
                'name': user[1],
                'gender': user[2],
                'birthday': user[3],
                'age': user[4],
                'photo_id': user[5],
                'bio': user[6],
                'zodiac': user[7],
                'city': user[8],
                'balance': user[9]
            }
            result.append(user_dict)
        
        return result
    
    # === Методы для лайков ===
    def add_like(self, from_user_id: str, to_user_id: str) -> bool:
        """Добавить лайк и проверить взаимность, возвращает True если лайк взаимный"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Проверяем, существует ли уже взаимный лайк
            user1, user2 = sorted([from_user_id, to_user_id])
            cursor.execute(
                'SELECT 1 FROM mutual_likes WHERE user1_id = ? AND user2_id = ?',
                (user1, user2)
            )
            
            if cursor.fetchone():
                return True  # Уже есть взаимный лайк
            
            # Добавляем лайк
            cursor.execute(
                'INSERT OR IGNORE INTO likes (from_user_id, to_user_id) VALUES (?, ?)',
                (from_user_id, to_user_id)
            )
            
            # Проверяем взаимность (есть ли обратный лайк)
            cursor.execute(
                'SELECT 1 FROM likes WHERE from_user_id = ? AND to_user_id = ?',
                (to_user_id, from_user_id)
            )
            
            if cursor.fetchone():
                # Есть взаимность! Удаляем оба лайка и добавляем в mutual
                cursor.execute(
                    'DELETE FROM likes WHERE (from_user_id = ? AND to_user_id = ?) OR (from_user_id = ? AND to_user_id = ?)',
                    (from_user_id, to_user_id, to_user_id, from_user_id)
                )
                
                # Добавляем в взаимные симпатии
                cursor.execute(
                    'INSERT OR IGNORE INTO mutual_likes (user1_id, user2_id) VALUES (?, ?)',
                    (user1, user2)
                )
                
                conn.commit()
                return True  # Взаимный лайк создан
            
            conn.commit()
            return False  # Лайк отправлен, но нет взаимности
            
        except Exception as e:
            print(f"Ошибка добавления лайка от {from_user_id} к {to_user_id}: {e}")
            conn.rollback()
            return False
    
    def get_mutual_likes(self, user_id: str) -> List[Dict]:
        """Получить всех пользователей, с которыми есть взаимная симпатия"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.* FROM users u
            WHERE u.user_id IN (
                SELECT 
                    CASE 
                        WHEN user1_id = ? THEN user2_id 
                        ELSE user1_id 
                    END
                FROM mutual_likes 
                WHERE user1_id = ? OR user2_id = ?
            )
        ''', (user_id, user_id, user_id))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def is_mutual_like(self, user1_id: str, user2_id: str) -> bool:
        """Проверить, есть ли взаимная симпатия между двумя пользователями"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        user1, user2 = sorted([user1_id, user2_id])
        cursor.execute(
            'SELECT 1 FROM mutual_likes WHERE user1_id = ? AND user2_id = ?',
            (user1, user2)
        )
        
        return cursor.fetchone() is not None
    
    def get_like_count(self, user_id: str, direction: str = 'sent') -> int:
        """Получить количество отправленных или полученных лайков"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if direction == 'sent':
            cursor.execute('SELECT COUNT(*) FROM likes WHERE from_user_id = ?', (user_id,))
        else:  # 'received'
            cursor.execute('SELECT COUNT(*) FROM likes WHERE to_user_id = ?', (user_id,))
        
        return cursor.fetchone()[0]
    
    # === Методы для платежей ===
    def add_payment(self, user_id: str, amount: int, description: str = None) -> bool:
        """Добавить запись о платеже"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                'INSERT INTO payments (user_id, amount, description) VALUES (?, ?, ?)',
                (user_id, amount, description)
            )
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка добавления платежа для пользователя {user_id}: {e}")
            return False
    
    def get_user_payments(self, user_id: str) -> List[Dict]:
        """Получить историю платежей пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC',
            (user_id,)
        )
        
        return [dict(row) for row in cursor.fetchall()]
    
    # === Вспомогательные методы ===
    def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """Получить профиль пользователя в формате, совместимом со старым кодом"""
        user = self.get_user(user_id)
        if not user:
            return None
        
        return {
            "name": user.get("name"),
            "gender": user.get("gender"),
            "birthday": user.get("birthday"),
            "age": user.get("age"),
            "photo_id": user.get("photo_id"),
            "bio": user.get("bio"),
            "zodiac": user.get("zodiac"),
            "city": user.get("city")
        }
    
    def search_users(self, query: str, limit: int = 20) -> List[Dict]:
        """Поиск пользователей по имени или городу"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        search_term = f"%{query}%"
        cursor.execute('''
            SELECT * FROM users 
            WHERE name LIKE ? OR city LIKE ?
            LIMIT ?
        ''', (search_term, search_term, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_users(self, limit: int = 10) -> List[Dict]:
        """Получить недавно зарегистрированных пользователей"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM users 
            ORDER BY registered_at DESC 
            LIMIT ?
        ''', (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def close(self):
        """Закрыть соединение с БД"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            del self._local.conn

    # В class Database добавить следующие методы:

def create_reports_table(self):
    """Создает таблицу для жалоб"""
    self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reported_user_id TEXT NOT NULL,
            reporter_user_id TEXT NOT NULL,
            reason TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reported_user_id) REFERENCES users (user_id) ON DELETE CASCADE,
            FOREIGN KEY (reporter_user_id) REFERENCES users (user_id) ON DELETE CASCADE
        )
    ''')
    self.connection.commit()

def create_banned_users_table(self):
    """Создает таблицу для заблокированных пользователей"""
    self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id TEXT PRIMARY KEY,
            reason TEXT,
            banned_by TEXT,
            banned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        )
    ''')
    self.connection.commit()

def add_report(self, reported_user_id, reporter_user_id, reason=None):
    """Добавляет жалобу на пользователя"""
    # Проверяем, не жаловался ли уже этот пользователь
    self.cursor.execute('''
        SELECT id FROM reports 
        WHERE reported_user_id = ? AND reporter_user_id = ?
    ''', (reported_user_id, reporter_user_id))
    
    if self.cursor.fetchone():
        return False  # Уже жаловался
    
    self.cursor.execute('''
        INSERT INTO reports (reported_user_id, reporter_user_id, reason)
        VALUES (?, ?, ?)
    ''', (reported_user_id, reporter_user_id, reason))
    self.connection.commit()
    
    # Проверяем количество жалоб
    report_count = self.get_report_count(reported_user_id)
    
    if report_count >= 15:
        # Автоматически скрываем анкету
        self.hide_user_profile(reported_user_id)
    
    return True

def get_report_count(self, user_id):
    """Получает количество жалоб на пользователя"""
    self.cursor.execute('''
        SELECT COUNT(*) FROM reports WHERE reported_user_id = ?
    ''', (user_id,))
    return self.cursor.fetchone()[0]

def hide_user_profile(self, user_id):
    """Скрывает анкету пользователя (устанавливает флаг)"""
    self.cursor.execute('''
        UPDATE users SET is_hidden = 1 WHERE user_id = ?
    ''', (user_id,))
    self.connection.commit()

def unhide_user_profile(self, user_id):
    """Показывает анкету пользователя"""
    self.cursor.execute('''
        UPDATE users SET is_hidden = 0 WHERE user_id = ?
    ''', (user_id,))
    self.connection.commit()

def get_users_with_reports(self, limit=50):
    """Получает пользователей с жалобами, отсортированных по количеству жалоб"""
    self.cursor.execute('''
        SELECT 
            u.user_id, 
            u.name, 
            u.gender,
            u.age,
            COUNT(r.id) as report_count,
            GROUP_CONCAT(DISTINCT r.reason) as reasons
        FROM users u
        LEFT JOIN reports r ON u.user_id = r.reported_user_id
        WHERE u.is_hidden = 0 OR u.is_hidden IS NULL
        GROUP BY u.user_id
        HAVING report_count > 0
        ORDER BY report_count DESC
        LIMIT ?
    ''', (limit,))
    
    users = self.cursor.fetchall()
    result = []
    
    for user in users:
        user_dict = {
            'user_id': user[0],
            'name': user[1],
            'gender': user[2],
            'age': user[3],
            'report_count': user[4],
            'reasons': user[5].split(',') if user[5] else []
        }
        result.append(user_dict)
    
    return result

def get_user_reports_details(self, user_id):
    """Получает детальную информацию о жалобах на пользователя"""
    self.cursor.execute('''
        SELECT 
            r.id,
            r.reporter_user_id,
            u.name as reporter_name,
            r.reason,
            r.timestamp
        FROM reports r
        JOIN users u ON r.reporter_user_id = u.user_id
        WHERE r.reported_user_id = ?
        ORDER BY r.timestamp DESC
    ''', (user_id,))
    
    reports = self.cursor.fetchall()
    result = []
    
    for report in reports:
        report_dict = {
            'report_id': report[0],
            'reporter_id': report[1],
            'reporter_name': report[2],
            'reason': report[3],
            'timestamp': report[4]
        }
        result.append(report_dict)
    
    return result

def is_user_banned(self, user_id):
        """Проверяет, заблокирован ли пользователь"""
        self.cursor.execute('SELECT user_id FROM banned_users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone() is not None

def delete_reports_for_user(self, user_id):
    """Удаляет все жалобы на пользователя"""
    self.cursor.execute('DELETE FROM reports WHERE reported_user_id = ?', (user_id,))
    self.connection.commit()
    return self.cursor.rowcount

def ban_user(self, user_id, reason=None, banned_by="admin"):
    """Блокирует пользователя"""
    try:
        self.cursor.execute('''
            INSERT OR REPLACE INTO banned_users (user_id, reason, banned_by)
            VALUES (?, ?, ?)
        ''', (user_id, reason, banned_by))
        
        # Скрываем анкету
        self.hide_user_profile(user_id)
        
        # Очищаем жалобы
        self.delete_reports_for_user(user_id)
        
        self.connection.commit()
        return True
    except:
        return False

def unban_user(self, user_id):
    """Разблокирует пользователя"""
    try:
        self.cursor.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
        
        # Показываем анкету
        self.unhide_user_profile(user_id)
        
        self.connection.commit()
        return True
    except:
        return False

def is_user_banned(self, user_id):
    """Проверяет, заблокирован ли пользователь"""
    self.cursor.execute('SELECT user_id FROM banned_users WHERE user_id = ?', (user_id,))
    return self.cursor.fetchone() is not None

def get_banned_users(self):
    """Получает список заблокированных пользователей"""
    self.cursor.execute('''
        SELECT u.user_id, u.name, b.reason, b.banned_at, b.banned_by
        FROM banned_users b
        JOIN users u ON b.user_id = u.user_id
        ORDER BY b.banned_at DESC
    ''')
    
    users = self.cursor.fetchall()
    result = []
    
    for user in users:
        user_dict = {
            'user_id': user[0],
            'name': user[1],
            'reason': user[2],
            'banned_at': user[3],
            'banned_by': user[4]
        }
        result.append(user_dict)
    
    return result

# В методе __init__ класса Database добавьте:
def __init__(self, db_name):
    self.connection = sqlite3.connect(db_name, check_same_thread=False)
    self.cursor = self.connection.cursor()
    self.create_tables()  # Существующий метод
    self.create_reports_table()  # Добавить эту строку
    self.create_banned_users_table()  # И эту
    
# В методе get_users_by_filters добавьте фильтр по скрытым анкетам:
def get_users_by_filters(self, exclude_user_id=None, gender=None, zodiac=None, city_filter=None):
    """Получает пользователей по фильтрам (ИСКЛЮЧАЯ скрытые анкеты)"""
    query = "SELECT * FROM users WHERE user_id != ? AND (is_hidden IS NULL OR is_hidden = 0)"
    params = [exclude_user_id]
    
    # ... остальной код метода без изменений ...