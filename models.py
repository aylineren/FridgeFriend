"""
FridgeFriend — OOP modeļu slānis
Visas datubāzes darbības tiek veiktas caur šīm klasēm.
"""
import os
import secrets
import sqlite3
import string
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

DB_PATH = os.environ.get('FF_DB', 'fridgefriend.db')
UPLOAD_FOLDER = os.path.join('static', 'uploads', 'avatars')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


# Datubaze
class Database:
    """Centralizēts SQLite savienojuma pārvaldnieks (Singleton).""" 
    _instance = None

    def __init__(self, path=DB_PATH):
        self.path = path

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def execute(self, sql, params=()):
        with self.connect() as conn:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid

    def fetchone(self, sql, params=()):
        conn = self.connect()
        try:
            return conn.execute(sql, params).fetchone()
        finally:
            conn.close()

    def fetchall(self, sql, params=()):
        conn = self.connect()
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def init_schema(self):
        conn = self.connect()
        c = conn.cursor()
        c.executescript('''
        users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    UNIQUE NOT NULL,
            email         TEXT    UNIQUE NOT NULL,
            password_hash TEXT    NOT NULL,
            display_name  TEXT,
            bio           TEXT,
            profile_pic   TEXT,
            is_admin      INTEGER DEFAULT 0,
            created_at    TEXT    DEFAULT CURRENT_TIMESTAMP
        );
        ingredients (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL,
            emoji    TEXT,
            category TEXT
        );
        recipes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT    NOT NULL,
            emoji        TEXT    DEFAULT "🍽️",
            time_minutes INTEGER DEFAULT 15,
            cost_eur     REAL    DEFAULT 1.0,
            difficulty   TEXT    DEFAULT "Viegli",
            serves       TEXT    DEFAULT "1 porcija",
            tip          TEXT,
            description  TEXT,
            created_by   INTEGER,
            is_official  INTEGER DEFAULT 1,
            is_public    INTEGER DEFAULT 1,
            created_at   TEXT    DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
        );
        recipe_ingredients (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id       INTEGER NOT NULL,
            ingredient_name TEXT,
            emoji           TEXT,
            amount          TEXT,
            is_optional     INTEGER DEFAULT 0,
            FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        );
        recipe_steps (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id   INTEGER NOT NULL,
            step_number INTEGER,
            description TEXT,
            FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        );
        user_fridge (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            ingredient_name TEXT    NOT NULL,
            emoji           TEXT    DEFAULT "🛒",
            expiry_date     TEXT,
            added_date      TEXT    DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        user_favorites (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            recipe_id INTEGER NOT NULL,
            saved_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, recipe_id),
            FOREIGN KEY(user_id)   REFERENCES users(id)   ON DELETE CASCADE,
            FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        );
        recipe_likes (
            user_id   INTEGER NOT NULL,
            recipe_id INTEGER NOT NULL,
            PRIMARY KEY(user_id, recipe_id),
            FOREIGN KEY(user_id)   REFERENCES users(id)   ON DELETE CASCADE,
            FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        );
        comments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            recipe_id  INTEGER NOT NULL,
            content    TEXT    NOT NULL,
            created_at TEXT    DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id)   REFERENCES users(id)   ON DELETE SET NULL,
            FOREIGN KEY(recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        );
        ''')
        conn.commit()
        conn.close()


# parole
class PasswordUtils:
    """Paroles drošības utilītas."""

    @staticmethod
    def hash(password: str) -> str:
        return generate_password_hash(password, method='pbkdf2:sha256:600000')

    @staticmethod
    def verify(password: str, hashed: str) -> bool:
        return check_password_hash(hashed, password)

    @staticmethod
    def generate(length: int = 16) -> str:
        alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
        while True:
            pwd = ''.join(secrets.choice(alphabet) for _ in range(length))
            if (any(c.islower() for c in pwd) and
                    any(c.isupper() for c in pwd) and
                    any(c.isdigit() for c in pwd) and
                    any(c in '!@#$%^&*' for c in pwd)):
                return pwd


# lietotoajs
class UserModel:
    def __init__(self):
        self.db = Database.get()

    def create(self, username, email, password, is_admin=0):
        hashed = PasswordUtils.hash(password)
        try:
            return self.db.execute(
                "INSERT INTO users (username,email,password_hash,is_admin) VALUES (?,?,?,?)",
                (username.strip(), email.strip().lower(), hashed, is_admin)
            )
        except sqlite3.IntegrityError:
            return None

    def authenticate(self, email, password):
        user = self.db.fetchone(
            "SELECT * FROM users WHERE email=?", (email.strip().lower(),)
        )
        if user and PasswordUtils.verify(password, user['password_hash']):
            return user
        return None

    def get_by_id(self, uid):
        return self.db.fetchone("SELECT * FROM users WHERE id=?", (uid,))

    def get_by_username(self, username):
        return self.db.fetchone("SELECT * FROM users WHERE username=?", (username,))

    def get_all(self):
        return self.db.fetchall("SELECT * FROM users ORDER BY created_at DESC")

    def update_profile(self, uid, display_name, bio, username, email):
        try:
            self.db.execute(
                "UPDATE users SET display_name=?,bio=?,username=?,email=? WHERE id=?",
                (display_name, bio, username, email.lower(), uid)
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def update_password(self, uid, new_password):
        self.db.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (PasswordUtils.hash(new_password), uid)
        )

    def update_avatar(self, uid, filename):
        self.db.execute(
            "UPDATE users SET profile_pic=? WHERE id=?", (filename, uid)
        )

    def delete(self, uid):
        self.db.execute("DELETE FROM users WHERE id=?", (uid,))

    def set_admin(self, uid, value=1):
        self.db.execute("UPDATE users SET is_admin=? WHERE id=?", (value, uid))


# recepte
class RecipeModel:
    def __init__(self):
        self.db = Database.get()

    def create(self, name, emoji, time_minutes, cost_eur, difficulty,
               serves, tip, description, created_by=None, is_official=1, is_public=1):
        return self.db.execute(
            '''INSERT INTO recipes
               (name,emoji,time_minutes,cost_eur,difficulty,serves,tip,
                description,created_by,is_official,is_public)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (name, emoji, time_minutes, cost_eur, difficulty, serves,
             tip, description, created_by, is_official, is_public)
        )

    def add_ingredient(self, recipe_id, name, emoji, amount, optional=0):
        self.db.execute(
            "INSERT INTO recipe_ingredients (recipe_id,ingredient_name,emoji,amount,is_optional) VALUES (?,?,?,?,?)",
            (recipe_id, name, emoji, amount, optional)
        )

    def add_step(self, recipe_id, step_num, description):
        self.db.execute(
            "INSERT INTO recipe_steps (recipe_id,step_number,description) VALUES (?,?,?)",
            (recipe_id, step_num, description)
        )

    def get_by_id(self, rid):
        return self.db.fetchone(
            """SELECT r.*, u.username as creator_username, u.display_name as creator_display,
                      u.profile_pic as creator_pic,
                      (SELECT COUNT(*) FROM recipe_likes WHERE recipe_id=r.id) as like_count
               FROM recipes r LEFT JOIN users u ON r.created_by=u.id
               WHERE r.id=?""", (rid,)
        )

    def get_all_public(self):
        return self.db.fetchall(
            """SELECT r.*, 
                      (SELECT COUNT(*) FROM recipe_likes WHERE recipe_id=r.id) as like_count
               FROM recipes r WHERE r.is_public=1 AND r.is_official=1
               ORDER BY like_count DESC"""
        )

    def get_popular(self, limit=3):
        return self.db.fetchall(
            """SELECT r.*,
                      (SELECT COUNT(*) FROM recipe_likes WHERE recipe_id=r.id) as like_count
               FROM recipes r WHERE r.is_public=1
               ORDER BY like_count DESC LIMIT ?""", (limit,)
        )

    def get_by_user(self, user_id):
        return self.db.fetchall(
            """SELECT r.*,
                      (SELECT COUNT(*) FROM recipe_likes WHERE recipe_id=r.id) as like_count
               FROM recipes r WHERE r.created_by=?
               ORDER BY r.created_at DESC""", (user_id,)
        )

    def get_pending_review(self):
        """User recipes awaiting admin approval."""
        return self.db.fetchall(
            """SELECT r.*, u.username as creator_username, u.display_name as creator_display
               FROM recipes r JOIN users u ON r.created_by=u.id
               WHERE r.is_official=0
               ORDER BY r.created_at DESC"""
        )

    def publish(self, rid):
        self.db.execute(
            "UPDATE recipes SET is_official=1, is_public=1 WHERE id=?", (rid,)
        )

    def update(self, rid, name, emoji, time_minutes, cost_eur,
               difficulty, serves, tip, description):
        self.db.execute(
            '''UPDATE recipes SET name=?,emoji=?,time_minutes=?,cost_eur=?,
               difficulty=?,serves=?,tip=?,description=? WHERE id=?''',
            (name, emoji, time_minutes, cost_eur, difficulty, serves, tip, description, rid)
        )

    def delete(self, rid):
        self.db.execute("DELETE FROM recipes WHERE id=?", (rid,))

    def get_ingredients(self, rid):
        return self.db.fetchall(
            "SELECT * FROM recipe_ingredients WHERE recipe_id=? ORDER BY id", (rid,)
        )

    def get_steps(self, rid):
        return self.db.fetchall(
            "SELECT * FROM recipe_steps WHERE recipe_id=? ORDER BY step_number", (rid,)
        )

    def clear_ingredients(self, rid):
        self.db.execute("DELETE FROM recipe_ingredients WHERE recipe_id=?", (rid,))

    def clear_steps(self, rid):
        self.db.execute("DELETE FROM recipe_steps WHERE recipe_id=?", (rid,))

    def search_by_ingredients(self, selected_names):
        """Find recipes matching the given ingredient list.

        A recipe match score is computed as the percentage of required
        (non-optional) ingredients that appear in the provided selection.
        """
        all_recipes = self.get_all_public()
        results = []

        def normalize(text: str) -> str:
            return text.strip().lower()

        selected_normalized = [normalize(n) for n in selected_names]

        for recipe in all_recipes:
            required = self.db.fetchall(
                "SELECT ingredient_name FROM recipe_ingredients WHERE recipe_id=? AND is_optional=0",
                (recipe['id'],)
            )
            required_names = [normalize(r['ingredient_name']) for r in required]

            if not required_names:
                match_score = 100
            else:
                matched = 0
                for name in required_names:
                    if any(name in sel or sel in name for sel in selected_normalized):
                        matched += 1
                match_score = int((matched / len(required_names)) * 100)

            if match_score >= 50 or not selected_names:
                results.append({'recipe': recipe, 'match': match_score})

        results.sort(key=lambda x: x['match'], reverse=True)
        return results


# komentari
class CommentModel:
    def __init__(self):
        self.db = Database.get()

    def add(self, user_id, recipe_id, content):
        return self.db.execute(
            "INSERT INTO comments (user_id,recipe_id,content) VALUES (?,?,?)",
            (user_id, recipe_id, content.strip())
        )

    def get_for_recipe(self, recipe_id):
        return self.db.fetchall(
            """SELECT c.*, u.username, u.display_name, u.profile_pic
               FROM comments c
               LEFT JOIN users u ON c.user_id=u.id
               WHERE c.recipe_id=?
               ORDER BY c.created_at ASC""", (recipe_id,)
        )

    def delete(self, comment_id):
        self.db.execute("DELETE FROM comments WHERE id=?", (comment_id,))

    def get_by_id(self, cid):
        return self.db.fetchone("SELECT * FROM comments WHERE id=?", (cid,))

    def get_all(self):
        return self.db.fetchall(
            """SELECT c.*, u.username, r.name as recipe_name
               FROM comments c
               LEFT JOIN users u ON c.user_id=u.id
               LEFT JOIN recipes r ON c.recipe_id=r.id
               ORDER BY c.created_at DESC"""
        )


# like
class LikeModel:
    def __init__(self):
        self.db = Database.get()

    def toggle(self, user_id, recipe_id):
        existing = self.db.fetchone(
            "SELECT 1 FROM recipe_likes WHERE user_id=? AND recipe_id=?",
            (user_id, recipe_id)
        )
        if existing:
            self.db.execute(
                "DELETE FROM recipe_likes WHERE user_id=? AND recipe_id=?",
                (user_id, recipe_id)
            )
            return False  # unliked
        else:
            self.db.execute(
                "INSERT INTO recipe_likes (user_id,recipe_id) VALUES (?,?)",
                (user_id, recipe_id)
            )
            return True  # liked

    def user_liked(self, user_id, recipe_id):
        return bool(self.db.fetchone(
            "SELECT 1 FROM recipe_likes WHERE user_id=? AND recipe_id=?",
            (user_id, recipe_id)
        ))

    def count(self, recipe_id):
        row = self.db.fetchone(
            "SELECT COUNT(*) as cnt FROM recipe_likes WHERE recipe_id=?",
            (recipe_id,)
        )
        return row['cnt'] if row else 0


# izlase
class FavoriteModel:
    def __init__(self):
        self.db = Database.get()

    def toggle(self, user_id, recipe_id):
        existing = self.db.fetchone(
            "SELECT 1 FROM user_favorites WHERE user_id=? AND recipe_id=?",
            (user_id, recipe_id)
        )
        if existing:
            self.db.execute(
                "DELETE FROM user_favorites WHERE user_id=? AND recipe_id=?",
                (user_id, recipe_id)
            )
            return False
        else:
            self.db.execute(
                "INSERT INTO user_favorites (user_id,recipe_id) VALUES (?,?)",
                (user_id, recipe_id)
            )
            return True

    def is_favorite(self, user_id, recipe_id):
        return bool(self.db.fetchone(
            "SELECT 1 FROM user_favorites WHERE user_id=? AND recipe_id=?",
            (user_id, recipe_id)
        ))

    def get_user_favorites(self, user_id):
        return self.db.fetchall(
            """SELECT r.*,
                      (SELECT COUNT(*) FROM recipe_likes WHERE recipe_id=r.id) as like_count
               FROM user_favorites f
               JOIN recipes r ON f.recipe_id=r.id
               WHERE f.user_id=?
               ORDER BY f.saved_at DESC""", (user_id,)
        )


# ledusskapis
class FridgeModel:
    def __init__(self):
        self.db = Database.get()

    def add(self, user_id, name, emoji='🛒', expiry=None):
        return self.db.execute(
            "INSERT INTO user_fridge (user_id,ingredient_name,emoji,expiry_date) VALUES (?,?,?,?)",
            (user_id, name.strip(), emoji, expiry or None)
        )

    def delete(self, item_id, user_id):
        self.db.execute(
            "DELETE FROM user_fridge WHERE id=? AND user_id=?", (item_id, user_id)
        )

    def get_user_items(self, user_id):
        return self.db.fetchall(
            "SELECT * FROM user_fridge WHERE user_id=? ORDER BY added_date DESC",
            (user_id,)
        )


# sastavdalas
class IngredientModel:
    def __init__(self):
        self.db = Database.get()

    def get_all_by_category(self):
        rows = self.db.fetchall(
            "SELECT * FROM ingredients ORDER BY category, name"
        )
        by_cat = {}
        for r in rows:
            by_cat.setdefault(r['category'], []).append(r)
        return by_cat

    def get_all(self):
        return self.db.fetchall("SELECT * FROM ingredients ORDER BY category, name")

    def create(self, name, emoji, category):
        return self.db.execute(
            "INSERT INTO ingredients (name,emoji,category) VALUES (?,?,?)",
            (name, emoji, category)
        )

    def delete(self, iid):
        self.db.execute("DELETE FROM ingredients WHERE id=?", (iid,))


