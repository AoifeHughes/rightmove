import sqlite3
from pathlib import Path
import json

class PropertyDatabase:
    def __init__(self, db_path="properties.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS properties (
                    id TEXT PRIMARY KEY,
                    data TEXT,
                    images_dir TEXT,
                    used INTEGER DEFAULT 0
                )
            ''')
            conn.commit()

    def add_property(self, property_data: dict, images_dir: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO properties (id, data, images_dir) VALUES (?, ?, ?)',
                (property_data['id'], json.dumps(property_data), str(images_dir))
            )
            conn.commit()

    def get_random_unused_properties(self, count=10):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT data, images_dir FROM properties WHERE used = 0 ORDER BY RANDOM() LIMIT ?',
                (count,)
            )
            results = cursor.fetchall()
            if results:
                # Mark these properties as used
                property_data = [(json.loads(data), Path(images_dir)) for data, images_dir in results]
                cursor.execute(
                    'UPDATE properties SET used = 1 WHERE data IN ({})'.format(
                        ','.join('?' * len(results))
                    ),
                    [result[0] for result in results]
                )
                conn.commit()
                return property_data
            return []

    def reset_used_status(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE properties SET used = 0')
            conn.commit()

    def count_properties(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM properties')
            return cursor.fetchone()[0]
