import sqlite3
import os

def update_existing_database(db_path='bot_database.db'):
    """Обновляет существующую базу данных, добавляя новые таблицы и поля"""
    
    if not os.path.exists(db_path):
        print(f"❌ Файл базы данных не найден: {db_path}")
        return False
    
    print(f"🔄 Обновление базы данных: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Проверяем и добавляем поле is_hidden в таблицу users
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN is_hidden INTEGER DEFAULT 0")
            print("✅ Добавлено поле 'is_hidden' в таблицу 'users'")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("ℹ️ Поле 'is_hidden' уже существует в таблице 'users'")
            else:
                print(f"⚠️ Ошибка при добавлении поля 'is_hidden': {e}")
        
        # 2. Создаем таблицу reports (если не существует)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reported_user_id TEXT NOT NULL,
                reporter_user_id TEXT NOT NULL,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(reported_user_id, reporter_user_id)
            )
        ''')
        print("✅ Таблица 'reports' создана или уже существует")
        
        # 3. Создаем таблицу banned_users (если не существует)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id TEXT PRIMARY KEY,
                reason TEXT,
                banned_by TEXT,
                banned_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Таблица 'banned_users' создана или уже существует")
        
        # 4. Создаем индекс для ускорения поиска жалоб
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_reported_user ON reports(reported_user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_reporter_user ON reports(reporter_user_id)')
            print("✅ Индексы для таблицы 'reports' созданы")
        except Exception as e:
            print(f"⚠️ Ошибка создания индексов: {e}")
        
        # 5. Проверяем структуру таблицы users
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        print("\n📊 Структура таблицы 'users':")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        conn.commit()
        conn.close()
        
        print(f"\n✅ База данных успешно обновлена: {db_path}")
        return True
        
    except Exception as e:
        print(f"❌ Критическая ошибка при обновлении базы данных: {e}")
        return False

if __name__ == "__main__":
    update_existing_database()