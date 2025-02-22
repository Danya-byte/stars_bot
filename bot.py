import asyncio
import atexit
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import F
import aiosqlite  

import config
import database

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

bot = Bot(token=config.TOKEN)
dp = Dispatcher()

commands = [
    '/start - Приветственное сообщение',
    '/help - Список доступных команд',
    '/burgers - Просмотр списка бургеров',
    '/cart - Просмотр корзины'
]


def stars_payment_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Оплатить Stars", pay=True)
    return keyboard.as_markup()


@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    state = await database.async_get_user_state(user_id)
    if state:
        await message.reply(f'Добро пожаловать обратно! Последний раз вы были: {state}')
    else:
        await message.reply('Добро пожаловать в наш магазин бургеров!')
    await database.async_save_user_state(user_id, 'start')
    await message.reply('Доступные команды:\n' + '\n'.join(commands))


@dp.message(Command("help"))
async def help_command(message: types.Message):
    user_id = message.from_user.id
    await database.async_save_user_state(user_id, 'help')
    await message.reply('Доступные команды:\n' + '\n'.join(commands))


@dp.message(Command("burgers"))
async def list_burgers(message: types.Message):
    user_id = message.from_user.id
    await database.async_save_user_state(user_id, 'burgers')
    burgers = await database.async_get_burgers()

    if not burgers:
        await message.reply('Бургеров пока нет.')
        return

    keyboard = []
    for burger in burgers:
        keyboard.append([InlineKeyboardButton(text=burger[1], callback_data=f'burger_{burger[0]}')])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.reply('Выберите бургер:', reply_markup=reply_markup)


@dp.callback_query(F.data.startswith('burger_'))
async def burger_details(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    burger_id = int(callback_query.data.split('_')[1])
    burgers = await database.async_get_burgers()
    burger = next((b for b in burgers if b[0] == burger_id), None)

    if burger:
        text = f'{burger[1]}\n\n{burger[2]}\n\nЦена: 1 ★'
        user_id = callback_query.from_user.id
        await database.async_save_user_state(user_id, f'awaiting_quantity_{burger_id}_1')

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text='-', callback_data=f'decrease_{burger_id}'),
            InlineKeyboardButton(text='1', callback_data=f'quantity_{burger_id}_1'),
            InlineKeyboardButton(text='+', callback_data=f'increase_{burger_id}')
        )
        builder.row(
            InlineKeyboardButton(text='Добавить в корзину', callback_data=f'add_to_cart_{burger_id}')
        )

        await bot.send_message(
            callback_query.message.chat.id,
            f'{text}\n\nВыберите количество бургеров:',
            reply_markup=builder.as_markup()
        )
    else:
        await bot.send_message(callback_query.message.chat.id, 'Бургер не найден.')


@dp.callback_query(F.data.startswith('increase_'))
async def increase_quantity(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    burger_id = int(callback_query.data.split('_')[1])
    user_id = callback_query.from_user.id
    state = await database.async_get_user_state(user_id)

    if state and state.startswith('awaiting_quantity_'):
        current_quantity = int(state.split('_')[3])
        new_quantity = current_quantity + 1
        await database.async_save_user_state(user_id, f'awaiting_quantity_{burger_id}_{new_quantity}')

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text='-', callback_data=f'decrease_{burger_id}'),
            InlineKeyboardButton(text=str(new_quantity), callback_data=f'quantity_{burger_id}_{new_quantity}'),
            InlineKeyboardButton(text='+', callback_data=f'increase_{burger_id}')
        )
        builder.row(
            InlineKeyboardButton(text='Добавить в корзину', callback_data=f'add_to_cart_{burger_id}')
        )

        await bot.edit_message_reply_markup(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=builder.as_markup()
        )


@dp.callback_query(F.data.startswith('decrease_'))
async def decrease_quantity(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    burger_id = int(callback_query.data.split('_')[1])
    user_id = callback_query.from_user.id
    state = await database.async_get_user_state(user_id)

    if state and state.startswith('awaiting_quantity_'):
        current_quantity = int(state.split('_')[3])
        new_quantity = max(current_quantity - 1, 1)
        await database.async_save_user_state(user_id, f'awaiting_quantity_{burger_id}_{new_quantity}')

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text='-', callback_data=f'decrease_{burger_id}'),
            InlineKeyboardButton(text=str(new_quantity), callback_data=f'quantity_{burger_id}_{new_quantity}'),
            InlineKeyboardButton(text='+', callback_data=f'increase_{burger_id}')
        )
        builder.row(
            InlineKeyboardButton(text='Добавить в корзину', callback_data=f'add_to_cart_{burger_id}')
        )

        await bot.edit_message_reply_markup(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=builder.as_markup()
        )


@dp.callback_query(F.data.startswith('add_to_cart_'))
async def add_to_cart(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    data_parts = callback_query.data.split('_')

    try:
        burger_id = int(data_parts[3])
    except (IndexError, ValueError):
        await bot.send_message(callback_query.message.chat.id, 'Ошибка: некорректные данные.')
        return

    user_id = callback_query.from_user.id
    state = await database.async_get_user_state(user_id)

    if state and state.startswith('awaiting_quantity_'):
        try:
            quantity = int(state.split('_')[3])
        except ValueError:
            await bot.send_message(callback_query.message.chat.id, 'Ошибка: некорректное количество.')
            return

        await database.async_add_to_cart(user_id, burger_id, quantity)
        await bot.send_message(callback_query.message.chat.id, f'Добавлено {quantity} бургера(-ов) в корзину!')
        await database.async_save_user_state(user_id, 'start')
        await bot.send_message(callback_query.message.chat.id, 'Доступные команды:\n' + '\n'.join(commands))


@dp.message(Command("cart"))
async def view_cart(message: types.Message):
    user_id = message.from_user.id
    cart_items = await database.async_get_cart(user_id)

    if not cart_items:
        await message.answer("🛒 Ваша корзина пуста")
        return

    total_stars = sum(item[4] for item in cart_items)
    cart_text = "🛒 *Ваша корзина:*\n\n"

    for item in cart_items:
        cart_text += f"🍔 {item[1]} × {item[4]}\n"

    cart_text += f"\n**Итого к оплате:** {total_stars} ★"

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Оплатить Stars", callback_data="buy")
    keyboard.button(text="Удалить позиции", callback_data="clear_cart")

    await message.answer(
        cart_text,
        reply_markup=keyboard.as_markup(),
        parse_mode="Markdown"
    )


@dp.callback_query(F.data == "buy")
async def buy(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await send_invoice(callback_query)


async def send_invoice(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    cart_items = await database.async_get_cart(user_id)

    if not cart_items:
        await bot.edit_message_text(
            'Ваша корзина пуста.',
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id
        )
        return

    total_stars = sum(item[4] for item in cart_items)

    try:
        await bot.send_invoice(
            chat_id=callback_query.message.chat.id,
            title='Оплата заказа',
            description=f'Оплата {total_stars} ★ за бургеры',
            provider_token="",
            currency='XTR',
            prices=[LabeledPrice(label='Бургеры', amount=total_stars)],
            payload='burgers-payment',
            reply_markup=stars_payment_keyboard()
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке инвойса: {e}")
        await bot.send_message(
            callback_query.message.chat.id,
            "Произошла ошибка при создании платежа"
        )


@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    user_id = message.from_user.id
    payment_info = message.successful_payment

    async with aiosqlite.connect('burgers.db') as db:  # Исправлено
        await db.execute('''
            INSERT INTO payments (user_id, payment_id, amount, currency)
            VALUES (?, ?, ?, ?)
        ''', (user_id,
              payment_info.provider_payment_charge_id,
              payment_info.total_amount,
              payment_info.currency))
        await db.commit()

    await database.async_clear_cart(user_id)
    await message.answer(f"✅ Оплата прошла успешно! Спасибо за покупку {payment_info.total_amount} ★!")


@dp.callback_query(F.data == "clear_cart")
async def clear_cart(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    await database.async_clear_cart(user_id)
    await bot.send_message(callback_query.message.chat.id, "Корзина успешно очищена!")


@dp.callback_query(F.data.startswith('delete_'))
async def delete_burger(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    data_parts = callback_query.data.split('_')

    if len(data_parts) == 2 and data_parts[0] == 'delete' and data_parts[1].isdigit():
        burger_id = int(data_parts[1])
        user_id = callback_query.from_user.id
        cart_items = await database.async_get_cart(user_id)
        burger = next((b for b in cart_items if b[0] == burger_id), None)

        if burger:
            quantity = burger[4]
            builder = InlineKeyboardBuilder()
            for i in range(1, quantity + 1):
                builder.add(InlineKeyboardButton(text=str(i), callback_data=f'remove_{burger_id}_{i}'))
            builder.adjust(3)

            await bot.send_message(
                chat_id=callback_query.message.chat.id,
                text=f'Сколько бургеров {burger[1]} вы хотите удалить?',
                reply_markup=builder.as_markup()
            )
        else:
            await bot.send_message(
                chat_id=callback_query.message.chat.id,
                text='Бургер не найден в корзине.'
            )
    else:
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text='Ошибка: неверный формат данных.'
        )


@dp.callback_query(F.data.startswith('remove_'))
async def remove_burger(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    data_parts = callback_query.data.split('_')

    if len(data_parts) == 3 and data_parts[0] == 'remove' and data_parts[1].isdigit() and data_parts[2].isdigit():
        burger_id = int(data_parts[1])
        quantity_to_remove = int(data_parts[2])
        user_id = callback_query.from_user.id
        cart_items = await database.async_get_cart(user_id)
        burger = next((b for b in cart_items if b[0] == burger_id), None)

        if burger:
            quantity = burger[4]
            if 0 < quantity_to_remove <= quantity:
                await database.async_remove_from_cart(user_id, burger_id, quantity_to_remove)
                await bot.send_message(
                    chat_id=callback_query.message.chat.id,
                    text=f'Удалено {quantity_to_remove} бургера(-ов) {burger[1]}.'
                )
                await bot.send_message(
                    callback_query.message.chat.id,
                    'Доступные команды:\n' + '\n'.join(commands)
                )
            else:
                await bot.send_message(
                    chat_id=callback_query.message.chat.id,
                    text='Неверное количество для удаления.'
                )
        else:
            await bot.send_message(
                chat_id=callback_query.message.chat.id,
                text='Бургер не найден в корзине.'
            )
    else:
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text='Ошибка: неверный формат данных.'
        )


async def main():
    await dp.start_polling(bot)


async def shutdown():
    await bot.close()
    await asyncio.sleep(0.1)


def atexit_handler():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(shutdown())


if __name__ == '__main__':
    database.init_db()
    atexit.register(atexit_handler)
    asyncio.run(main())
