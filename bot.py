from dotenv import load_dotenv
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
import aiohttp
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types.reply_keyboard_markup import ReplyKeyboardMarkup
from aiogram.types.keyboard_button import KeyboardButton
from aiogram import F
from datetime import date, datetime
from aiogram.types import ReplyKeyboardRemove
from aiogram.types import Message

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
API_URL = os.getenv('API_URL')

dp = Dispatcher()

class WorkoutForm(StatesGroup): # Before handle any states you will need to specify what kind of states you want to handle
    waiting_for_date = State()
    waiting_for_another_date = State()
    waiting_for_workout_type = State()
    waiting_for_duplicate_confirm = State()

async def get_workout_types(API_URL):         # делаем запрос к API чтобы получить виды тренировок
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}/api/workout-types") as response:
            data = await response.json()
    return data


@dp.message(Command('workout'))
async def cmd_workout(message: Message,               # когда придёт сообщение с командой /workout — вызови эту функцию
                      state: FSMContext):                    # message данные из сообщения, state - на каком состоянии бот
    telegram_id = message.from_user.id                       # из данных о присланном сообщении узнаем telegram_id отправителя

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_URL}/api/users/by-telegram/{telegram_id}") as response: # делаем запрос к API чтобы проверить, есть ли пользователь с таким id в базе
                if response.status == 404:
                    await message.answer(
                        "К сожалению, я не нашёл вас в базе пользователей.\n"
                        "Пожалуйста, обратитесь к администратору."
                    )
                    return


                response.raise_for_status()  # если 500, 403 и т.п.
                data = await response.json()

    except aiohttp.ClientError as e:
        print(f"Ошибка обращения к API: {e}")
        await message.answer(
            "Сервис сейчас временно недоступен. Попробуйте позже."
        )
        return

    await state.update_data(user_name=data['name'],
                            user_id=data['id'])
    await state.set_state(WorkoutForm.waiting_for_date)  # устанавливаем состояние ожидания данных о дне тренировки
    await message.answer(f"{data['name']}, тренировка сегодня или другой день?",
                         reply_markup=ReplyKeyboardMarkup(
                             keyboard=[
                                 [
                                     KeyboardButton(text="Сегодня"),
                                     KeyboardButton(text="Другой день"),
                                 ],
                             ],
                             resize_keyboard=True,
                         )
                         )



@dp.message(WorkoutForm.waiting_for_date,
            F.text == "Сегодня")
async def cmd_workout_date_today(message: Message, state: FSMContext):
    data = await state.get_data()

    user_name = data['user_name']
    workout_date = date.today()

    list_of_workout_types = await get_workout_types(API_URL)

    await state.update_data(workout_date=workout_date,
                                workout_types=list_of_workout_types)
    await state.set_state(
            WorkoutForm.waiting_for_workout_type)  # устанавливаем состояние ожидания данных о типе тренировки







    await message.answer(f"{user_name}, какая сегодня была тренировка?",
                         reply_markup=ReplyKeyboardMarkup(
                             keyboard=[[KeyboardButton(text=item['name'])] for item in list_of_workout_types],
                             resize_keyboard=True,
                         )
                         )



@dp.message(WorkoutForm.waiting_for_date,
            F.text == "Другой день")
async def cmd_workout_date_anoter_day(message: Message, state: FSMContext):
    data = await state.get_data()
    user_name = data['user_name']

    await state.set_state(WorkoutForm.waiting_for_another_date)  # устанавливаем состояние ожидания данных о дате, если дата не сегодня
    await message.answer(f"Введите дату в формате ДД.ММ.ГГГГ", reply_markup=ReplyKeyboardRemove()) # тут нужно как-то записать пользовательский ввод в переменную workout_anoter_day_date



@dp.message(WorkoutForm.waiting_for_date) # если пользователь пришлет что-то другое
async def cmd_unknown_write(message: Message):
        await message.reply("Не понимаю, что вы ввели :(")



@dp.message(WorkoutForm.waiting_for_another_date)
async def cmd_anoter_date(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    user_name = data['user_name']

    user_answer = message.text
    try:
        workout_anoter_day_date = datetime.strptime(user_answer, "%d.%m.%Y").date()  # тут подумать над форматом даты
    except ValueError as e:
        print(f"Ошибка ввода формата даты, пользователь ввел {user_answer}: {e}")
        await message.answer(
            "Неверный формат даты.\n"
            "Введите дату в формате ДД.ММ.ГГГГ, например: 25.07.2026"
        )
        return
    list_of_workout_types = await get_workout_types(API_URL)
    await state.update_data(workout_date=workout_anoter_day_date,
                            workout_types=list_of_workout_types)

    await state.set_state(WorkoutForm.waiting_for_workout_type) # устанавливаем состояние ожидания данных о типе тренировки

    await message.answer(f"{user_name}, какая сегодня была тренировка?",
                         reply_markup=ReplyKeyboardMarkup(
                             keyboard=[[KeyboardButton(text=item['name'])] for item in list_of_workout_types],
                             resize_keyboard=True,
                         )
                         )

@dp.message(WorkoutForm.waiting_for_workout_type)
async def cmd_workout_type(message: Message,
                           state: FSMContext):
    user_answer_workout_type = message.text.casefold()
    await state.update_data(workout_type=user_answer_workout_type)

    data = await state.get_data()
    user_id = data['user_id']

    async with (aiohttp.ClientSession() as session):
        async with session.get(
                f"{API_URL}/api/check_workout_date",
                params= {"user_id": user_id, "workout_date":data['workout_date'].isoformat()}) as response:
            result = await response.json()
    if len(result) == 0:  # если еще не было записаей о тренировках на указанную дату

        body_data = {
            "user_id": int(data['user_id']),
            "workout_date": data['workout_date'].isoformat(),
            "workout_type_id": [item['id'] for item in data['workout_types'] if item['name'] == user_answer_workout_type][0]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_URL}/api/workouts", json = body_data) as response: # отправляем POST запрос
                result = await response.json()
                print(response.status)
                print(result)

        await message.answer("Тренировка записана!", reply_markup=ReplyKeyboardRemove())
        await state.clear()
    else:
        await state.set_state(WorkoutForm.waiting_for_duplicate_confirm)  # устанавливаем состояние ожидания данных повторной отправке даты
        await message.answer(f"На эту дату {data['workout_date']} уже есть тренировка. Вы можете добавить не более 1й тренировки в день. Хочешь записать на другой день?" ,
                             reply_markup=ReplyKeyboardMarkup(
                                 keyboard=[
                                     [KeyboardButton(text="Да"),
                                     KeyboardButton(text="Нет")]
                                 ],
                                 resize_keyboard=True,
                             )
                             )
@dp.message(WorkoutForm.waiting_for_duplicate_confirm, F.text == "Да")
async def cmd_positive_duplicate_confirm(message: Message,
                           state: FSMContext):
    await state.set_state(WorkoutForm.waiting_for_another_date)
    await message.answer("Введите дату в формате ДД.ММ.ГГГГ", reply_markup=ReplyKeyboardRemove())




@dp.message(WorkoutForm.waiting_for_duplicate_confirm, F.text == "Нет")
async def cmd_negative_duplicate_confirm(message: Message,
                           state: FSMContext):
    await state.clear()
    await message.answer("Тренировка не записана", reply_markup=ReplyKeyboardRemove())


@dp.message(Command('cancel'))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=ReplyKeyboardRemove())


async def main():
    bot = Bot(token=BOT_TOKEN)  # подключаемся к Telegram
    await dp.start_polling(bot) # начинаем слушать входящие сообщения



if __name__ == '__main__':
    import asyncio
    asyncio.run(main())