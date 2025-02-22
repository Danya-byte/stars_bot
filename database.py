import sqlite3
import aiosqlite


def get_connection():
    return sqlite3.connect('burgers.db')


async def async_get_connection():
    return await aiosqlite.connect('burgers.db')


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()

        # Таблица бургеров
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS burgers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                price INTEGER NOT NULL DEFAULT 1
            )
        ''')

        # Таблица корзины
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cart (
                user_id INTEGER NOT NULL,
                burger_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (burger_id) REFERENCES burgers (id)
            )
        ''')

        # Таблица платежей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                user_id INTEGER,
                payment_id TEXT,
                amount INTEGER,
                currency TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, payment_id)
            )
        ''')

        # Таблица состояний пользователя
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT NOT NULL
            )
        ''')

        conn.commit()


def get_burgers():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM burgers')
        return cursor.fetchall()


def remove_burger(burger_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM burgers WHERE id = ?', (burger_id,))
        conn.commit()


def add_to_cart(user_id, burger_id, quantity):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO cart (user_id, burger_id, quantity)
            VALUES (?, ?, ?)
        ''', (user_id, burger_id, quantity))
        conn.commit()


def get_cart(user_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.id, b.name, b.description, b.price, c.quantity
            FROM cart c
            JOIN burgers b ON c.burger_id = b.id
            WHERE c.user_id = ?
        ''', (user_id,))
        return cursor.fetchall()


def remove_from_cart(user_id, burger_id, quantity):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT quantity FROM cart WHERE user_id = ? AND burger_id = ?', (user_id, burger_id))
        result = cursor.fetchone()

        if result:
            current_quantity = result[0]
            new_quantity = max(current_quantity - quantity, 0)

            if new_quantity == 0:
                cursor.execute('DELETE FROM cart WHERE user_id = ? AND burger_id = ?', (user_id, burger_id))
            else:
                cursor.execute('''
                    UPDATE cart SET quantity = ?
                    WHERE user_id = ? AND burger_id = ?
                ''', (new_quantity, user_id, burger_id))

            conn.commit()


def save_user_state(user_id, state):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO user_states (user_id, state)
            VALUES (?, ?)
        ''', (user_id, state))
        conn.commit()


def get_user_state(user_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT state FROM user_states WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None


# Асинхронные версии функций

async def async_get_burgers():
    async with aiosqlite.connect('burgers.db') as db:
        async with db.execute('SELECT * FROM burgers') as cursor:
            return await cursor.fetchall()


async def async_add_to_cart(user_id, burger_id, quantity):
    async with aiosqlite.connect('burgers.db') as db:
        await db.execute('''
            INSERT INTO cart (user_id, burger_id, quantity)
            VALUES (?, ?, ?)
        ''', (user_id, burger_id, quantity))
        await db.commit()


async def async_get_cart(user_id):
    async with aiosqlite.connect('burgers.db') as db:
        async with db.execute('''
            SELECT b.id, b.name, b.description, b.price, c.quantity
            FROM cart c
            JOIN burgers b ON c.burger_id = b.id
            WHERE c.user_id = ?
        ''', (user_id,)) as cursor:
            return await cursor.fetchall()


async def async_remove_from_cart(user_id, burger_id, quantity):
    async with aiosqlite.connect('burgers.db') as db:
        async with db.execute('SELECT quantity FROM cart WHERE user_id = ? AND burger_id = ?',
                              (user_id, burger_id)) as cursor:
            result = await cursor.fetchone()

            if result:
                current_quantity = result[0]
                new_quantity = max(current_quantity - quantity, 0)

                if new_quantity == 0:
                    await db.execute('DELETE FROM cart WHERE user_id = ? AND burger_id = ?', (user_id, burger_id))
                else:
                    await db.execute('''
                        UPDATE cart SET quantity = ?
                        WHERE user_id = ? AND burger_id = ?
                    ''', (new_quantity, user_id, burger_id))

                await db.commit()


async def async_save_user_state(user_id, state):
    async with aiosqlite.connect('burgers.db') as db:
        await db.execute('''
            INSERT OR REPLACE INTO user_states (user_id, state)
            VALUES (?, ?)
        ''', (user_id, state))
        await db.commit()


async def async_get_user_state(user_id):
    async with aiosqlite.connect('burgers.db') as db:
        async with db.execute('SELECT state FROM user_states WHERE user_id = ?', (user_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None


async def async_clear_cart(user_id):
    async with aiosqlite.connect('burgers.db') as db:
        await db.execute('DELETE FROM cart WHERE user_id = ?', (user_id,))
        await db.commit()
