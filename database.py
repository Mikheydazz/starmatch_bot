import sqlite3
import threading
import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any

class Database:
    def __init__(self, db_file='bot_database.db', photos_dir='photos'):
        self.db_file = db_file
        self.photos_dir = photos_dir
        self._local = threading.local()
        
        # Создаем папку для фотографий
        os.makedirs(photos_dir, exist_ok=True)
        
        self.init_database()
    
    def get_connection(self):
        """Получаем соединение с БД для текущего потока"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_file, 
                check_same_thread=False,
                timeout=10
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def init_database(self):
        """Инициализация всех таблиц"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей (обновленная)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                balance INTEGER DEFAULT 3,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                name TEXT NOT NULL,
                gender TEXT NOT NULL,
                birthday TEXT NOT NULL,
                age INTEGER NOT NULL,
                photo_id TEXT,  -- Telegram file_id (для совместимости)
                photo_path TEXT,  -- Локальный путь к фото
                bio TEXT NOT NULL,
                zodiac TEXT NOT NULL,
                city TEXT,
                is_fake INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # ... остальные таблицы без изменений ...
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
        
        # Таблица взаимных симпатий
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
        
        # Индексы
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
    
    # === Дополнительные методы ===
    
    # === Новые методы для работы с фотографиями ===
    
    def save_user_photo(self, user_id: str, photo_file: bytes, photo_id: str = None) -> str:
        """
        Сохранить фотографию пользователя локально.
        Возвращает путь к сохраненному файлу.
        """
        try:
            # Генерируем имя файла
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{user_id}_{timestamp}.jpg"
            filepath = os.path.join(self.photos_dir, filename)
            
            # Сохраняем файл
            with open(filepath, 'wb') as f:
                f.write(photo_file)
            
            # Обновляем запись в базе
            conn = self.get_connection()
            cursor = conn.cursor()
            
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                UPDATE users 
                SET photo_path = ?, photo_id = ?, updated_at = ?
                WHERE user_id = ?
            ''', (filepath, photo_id, current_time, user_id))
            
            # Если пользователя еще нет, создаем запись
            if cursor.rowcount == 0:
                # Создаем минимальную запись пользователя
                cursor.execute('''
                    INSERT INTO users (user_id, name, photo_path, photo_id, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, f"User_{user_id[:8]}", filepath, photo_id, current_time))
            
            conn.commit()
            return filepath
            
        except Exception as e:
            print(f"Ошибка сохранения фото пользователя {user_id}: {e}")
            return None
    
    def get_user_photo_path(self, user_id: str) -> Optional[str]:
        """Получить путь к фотографии пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT photo_path FROM users WHERE user_id = ?', 
            (user_id,)
        )
        row = cursor.fetchone()
        return row[0] if row and row[0] else None
    
    def get_user_photo_file(self, user_id: str) -> Optional[bytes]:
        """Получить фотографию пользователя как байты"""
        photo_path = self.get_user_photo_path(user_id)
        if not photo_path or not os.path.exists(photo_path):
            return None
        
        try:
            with open(photo_path, 'rb') as f:
                return f.read()
        except Exception as e:
            print(f"Ошибка чтения фото пользователя {user_id}: {e}")
            return None
    
    def delete_user_photo(self, user_id: str) -> bool:
        """Удалить фотографию пользователя"""
        try:
            photo_path = self.get_user_photo_path(user_id)
            
            # Удаляем файл
            if photo_path and os.path.exists(photo_path):
                os.remove(photo_path)
            
            # Обновляем запись в базе
            conn = self.get_connection()
            cursor = conn.cursor()
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                UPDATE users 
                SET photo_path = NULL, photo_id = NULL, updated_at = ?
                WHERE user_id = ?
            ''', (current_time, user_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Ошибка удаления фото пользователя {user_id}: {e}")
            return False

    def get_all_photo_paths(self) -> List[str]:
        """Получить все пути к фотографиям (для обслуживания)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT photo_path FROM users WHERE photo_path IS NOT NULL')
        return [row[0] for row in cursor.fetchall() if row[0]]
    
    def cleanup_orphaned_photos(self) -> int:
        """Удалить фото, которые не привязаны к пользователям"""
        try:
            # Получаем все фото из базы
            db_photos = set(self.get_all_photo_paths())
            
            # Получаем все файлы в папке photos
            actual_photos = set()
            for root, dirs, files in os.walk(self.photos_dir):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                        actual_photos.add(os.path.join(root, file))
            
            # Находим фото, которых нет в базе
            orphaned = actual_photos - db_photos
            
            # Удаляем их
            for photo_path in orphaned:
                try:
                    os.remove(photo_path)
                except Exception as e:
                    print(f"Ошибка удаления фото {photo_path}: {e}")
            
            return len(orphaned)
            
        except Exception as e:
            print(f"Ошибка очистки фото: {e}")
            return 0
    
    def save_user(self, user_id: str, name: str, gender: str, birthday: str, age: int,
                  bio: str, zodiac: str, balance: int = 3, 
                  photo_file: bytes = None, photo_id: str = None,
                  city: str = None, is_fake: int = 0) -> bool:
        """Сохранить или обновить пользователя с фотографией"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Если есть фото, сохраняем его
            photo_path = None
            if photo_file:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{user_id}_{timestamp}.jpg"
                photo_path = os.path.join(self.photos_dir, filename)
                
                # Сохраняем файл
                with open(photo_path, 'wb') as f:
                    f.write(photo_file)
            
            # Проверяем, существует ли пользователь
            cursor.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,))
            user_exists = cursor.fetchone() is not None
            
            if user_exists:
                # Обновляем существующего пользователя
                update_fields = []
                params = []
                
                if photo_path:
                    update_fields.append('photo_path = ?')
                    params.append(photo_path)
                
                if photo_id:
                    update_fields.append('photo_id = ?')
                    params.append(photo_id)
                
                update_fields.append('name = ?')
                params.append(name)
                update_fields.append('gender = ?')
                params.append(gender)
                update_fields.append('birthday = ?')
                params.append(birthday)
                update_fields.append('age = ?')
                params.append(age)
                update_fields.append('bio = ?')
                params.append(bio)
                update_fields.append('zodiac = ?')
                params.append(zodiac)
                update_fields.append('city = ?')
                params.append(city)
                update_fields.append('is_fake = ?')
                params.append(is_fake)
                update_fields.append('updated_at = ?')
                params.append(current_time)
                
                query = f'''
                    UPDATE users 
                    SET {', '.join(update_fields)}
                    WHERE user_id = ?
                '''
                params.append(user_id)
                
                cursor.execute(query, params)
            else:
                # Создаем нового пользователя
                cursor.execute('''
                    INSERT INTO users 
                    (user_id, name, gender, birthday, age, photo_id, photo_path, bio, zodiac, 
                     city, is_fake, balance, registered_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id, name, gender, birthday, age, photo_id, photo_path, bio, zodiac,
                    city, is_fake, balance, current_time, current_time
                ))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Ошибка сохранения пользователя {user_id}: {e}")
            if 'conn' in locals():
                conn.rollback()
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
        """Получить профиль пользователя с поддержкой локальных фото"""
        user = self.get_user(user_id)
        if not user:
            return None
        
        # Проверяем наличие локальной фотографии
        photo_id = user.get("photo_id")
        photo_path = user.get("photo_path")
        
        # Если есть локальный путь и файл существует, используем его
        if photo_path and os.path.exists(photo_path):
            photo = photo_path
        elif photo_id:
            # Иначе используем Telegram file_id (для совместимости)
            photo = photo_id
        else:
            photo = None
        
        return {
            "name": user.get("name"),
            "gender": user.get("gender"),
            "birthday": user.get("birthday"),
            "age": user.get("age"),
            "photo_id": photo_id,  # Для обратной совместимости
            "photo": photo,  # Основное поле для фото (путь или file_id)
            "photo_path": photo_path,  # Локальный путь
            "bio": user.get("bio"),
            "zodiac": user.get("zodiac"),
            "city": user.get("city"),
            "balance": user.get("balance", 3),
            "is_fake": user.get("is_fake", 0)
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