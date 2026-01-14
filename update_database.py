import sqlite3
import os

def update_database(db_name='bot_database.db'):
    """Обновляет структуру базы данных"""
    
    if not os.path.exists(db_name):
        print(f"❌ База данных {db_name} не найдена!")
        return False
    
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        # 1. Добавляем поле is_hidden в таблицу users
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN is_hidden INTEGER DEFAULT 0")
            print("✅ Добавлено поле is_hidden в таблицу users")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("ℹ️ Поле is_hidden уже существует")
            else:
                print(f"⚠️ Ошибка добавления поля is_hidden: {e}")
        
        # 2. Создаем таблицу reports
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reported_user_id TEXT NOT NULL,
                reporter_user_id TEXT NOT NULL,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Создана таблица reports")
        
        # 3. Создаем таблицу banned_users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id TEXT PRIMARY KEY,
                reason TEXT,
                banned_by TEXT,
                banned_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Создана таблица banned_users")
        
        conn.commit()
        conn.close()
        
        print("✅ База данных успешно обновлена!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка обновления базы данных: {e}")
        return False

if __name__ == "__main__":
    update_database()