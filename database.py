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
                is_fake INTEGER DEFAULT 0,
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
                  city: str = None, is_fake: int = 0) -> bool:
        """Сохранить или обновить пользователя"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, name, gender, birthday, age, photo_id, bio, zodiac, 
                 city, is_fake, balance, registered_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, name, gender, birthday, age, photo_id, bio, zodiac,
                city, is_fake, balance, current_time, current_time
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
    
    def get_users_by_filters(self, exclude_user_id: str = None, gender: str = None, 
                            zodiac: str = None, city_filter: str = None) -> List[Dict]:
        """Получить пользователей с фильтрами"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM users WHERE 1=1'
        params = []
        
        if exclude_user_id:
            query += ' AND user_id != ?'
            params.append(exclude_user_id)
        
        if gender:
            query += ' AND gender = ?'
            params.append(gender)
        
        if zodiac:
            query += ' AND zodiac = ?'
            params.append(zodiac)
        
        if city_filter == "same_city" and exclude_user_id:
            # Получаем город текущего пользователя
            cursor.execute('SELECT city FROM users WHERE user_id = ?', (exclude_user_id,))
            user_city_row = cursor.fetchone()
            if user_city_row and user_city_row[0]:
                query += ' AND city = ?'
                params.append(user_city_row[0])
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_fake_users_count(self):
        """Возвращает количество фейковых анкет"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_fake = 1')
        result = cursor.fetchone()
        return result[0] if result else 0

    def delete_all_fake_users(self):
        """Удаляет все фейковые анкеты"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE is_fake = 1')
        self.conn.commit()
        return cursor.rowcount
    
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