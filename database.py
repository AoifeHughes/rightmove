import io
import json
import os
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt


class PropertyDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            documents_dir = os.path.expanduser("~/Documents")
            db_path = os.path.join(documents_dir, "properties.db")
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS properties (
                    id TEXT PRIMARY KEY,
                    data TEXT,
                    used INTEGER DEFAULT 0
                )
            """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS property_images (
                    property_id TEXT,
                    image_index INTEGER,
                    image_data BLOB,
                    FOREIGN KEY(property_id) REFERENCES properties(id),
                    PRIMARY KEY(property_id, image_index)
                )
            """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS property_plots (
                    property_id TEXT PRIMARY KEY,
                    plot_data BLOB,
                    FOREIGN KEY(property_id) REFERENCES properties(id)
                )
            """
            )
            conn.commit()

    def add_property(self, property_data: dict, images: list, plot_data: bytes = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Store property data
            cursor.execute(
                "INSERT OR REPLACE INTO properties (id, data) VALUES (?, ?)",
                (property_data["id"], json.dumps(property_data)),
            )
            print("Inserted property:", property_data["id"])
            # Store images
            for idx, image_data in enumerate(images):
                cursor.execute(
                    "INSERT OR REPLACE INTO property_images (property_id, image_index, image_data) VALUES (?, ?, ?)",
                    (property_data["id"], idx, image_data),
                )

            # Store plot
            if plot_data:
                cursor.execute(
                    "INSERT OR REPLACE INTO property_plots (property_id, plot_data) VALUES (?, ?)",
                    (property_data["id"], plot_data),
                )

            conn.commit()

    def get_random_unused_properties(self, count=10):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Get random unused properties
            cursor.execute(
                "SELECT data FROM properties WHERE used = 0 ORDER BY RANDOM() LIMIT ?",
                (count,),
            )
            results = cursor.fetchall()
            if results:
                properties = []
                for (data,) in results:
                    property_data = json.loads(data)
                    # Get images for this property
                    cursor.execute(
                        "SELECT image_data FROM property_images WHERE property_id = ? ORDER BY image_index",
                        (property_data["id"],),
                    )
                    images = [row[0] for row in cursor.fetchall()]

                    # Get plot for this property
                    cursor.execute(
                        "SELECT plot_data FROM property_plots WHERE property_id = ?",
                        (property_data["id"],),
                    )
                    plot_data = cursor.fetchone()
                    plot = plot_data[0] if plot_data else None

                    properties.append((property_data, images, plot))

                # Mark these properties as used
                cursor.execute(
                    "UPDATE properties SET used = 1 WHERE data IN ({})".format(
                        ",".join("?" * len(results))
                    ),
                    [result[0] for result in results],
                )
                conn.commit()
                return properties
            return []

    def reset_used_status(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE properties SET used = 0")
            conn.commit()

    def count_properties(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM properties")
            return cursor.fetchone()[0]

    def get_property_images(self, property_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT image_data FROM property_images WHERE property_id = ? ORDER BY image_index",
                (property_id,),
            )
            return [row[0] for row in cursor.fetchall()]

    def get_property_plot(self, property_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT plot_data FROM property_plots WHERE property_id = ?",
                (property_id,),
            )
            result = cursor.fetchone()
            return result[0] if result else None
