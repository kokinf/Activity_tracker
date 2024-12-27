import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram_calendar import DialogCalendar, DialogCalendarCallback
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker

# Загрузка переменных окружения из файла .env
load_dotenv()
API_TOKEN = os.getenv('TOKEN')

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Настройка SQLAlchemy
Base = declarative_base()
engine = create_engine('sqlite:///tasks.db')
Session = sessionmaker(bind=engine)
session = Session()

# Определение модели тренировки
class Training(Base):
    __tablename__ = 'trainings'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    date = Column(String, nullable=False)
    name = Column(Text, nullable=False)

# Определение модели упражнения
class Exercise(Base):
    __tablename__ = 'exercises'
    id = Column(Integer, primary_key=True)
    training_id = Column(Integer, nullable=False)
    name = Column(Text, nullable=False)
    sets = Column(Text, nullable=True)
    weight = Column(Text, nullable=True)

# Создание таблиц
Base.metadata.create_all(engine)

# Определение состояний FSM
class Form(StatesGroup):
    main = State()
    training_type = State()
    level = State()
    custom_training = State()
    custom_training_date = State()
    custom_training_name = State()
    custom_training_exercise = State()
    custom_training_set = State()
    my_trainings = State()
    view_training = State()  # Новое состояние для просмотра конкретной тренировки

# Класс для обработки тренировок
class TrainingBot:
    def __init__(self, dp: Dispatcher):
        self.dp = dp
        self.register_handlers()

    # Создание клавиатуры с кнопкой "Назад"
    def get_back_keyboard(self):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back_to_trainings")],
            ]
        )
        return keyboard

    # Создание клавиатуры с типами тренировок
    def get_training_types_keyboard(self):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Создать тренировку", callback_data="custom_training")],
                [InlineKeyboardButton(text="Мои тренировки", callback_data="my_trainings")],
                [InlineKeyboardButton(text="Сплит", callback_data="split_training")],
                [InlineKeyboardButton(text="Фулбади", callback_data="fullbody_training")],
                [InlineKeyboardButton(text="Кардио", callback_data="cardio_training")],
                [InlineKeyboardButton(text="Назад", callback_data="back_to_main")],
            ]
        )
        return keyboard

    # Создание клавиатуры с уровнями тренировок
    def get_level_keyboard(self):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Новичок", callback_data="beginner")],
                [InlineKeyboardButton(text="Средний", callback_data="intermediate")],
                [InlineKeyboardButton(text="Продвинутый", callback_data="advanced")],
                [InlineKeyboardButton(text="Назад", callback_data="back_to_trainings")],
            ]
        )
        return keyboard

    # Создание клавиатуры с упражнениями
    def get_exercise_keyboard(self):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Добавить подход", callback_data="add_set")],
                [InlineKeyboardButton(text="Создать новое упражнение", callback_data="new_exercise")],
                [InlineKeyboardButton(text="Закончить тренировку", callback_data="finish_training")],
            ]
        )
        return keyboard

    # Создание клавиатуры для просмотра тренировок
    def get_view_training_keyboard(self, user_id, page=1):
        trainings = session.query(Training).filter_by(user_id=user_id).all()
        max_per_page = 3
        total_pages = (len(trainings) + max_per_page - 1) // max_per_page
        start_idx = (page - 1) * max_per_page
        end_idx = min(start_idx + max_per_page, len(trainings))

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"{training.date} - {training.name}", callback_data=f"view_training_{training.id}") for training in trainings[start_idx:end_idx]],
            ]
        )

        if total_pages > 1:
            navigation_buttons = []
            if page > 1:
                navigation_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"prev_page_{page-1}"))
            if page < total_pages:
                navigation_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"next_page_{page+1}"))
            keyboard.inline_keyboard.append(navigation_buttons)

        keyboard.inline_keyboard.append([InlineKeyboardButton(text="Назад", callback_data="back_to_trainings")])

        return keyboard

    # Создание клавиатуры для существующей тренировки
    def get_existing_training_keyboard(self):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Просмотреть тренировку", callback_data="view_training")],
                [InlineKeyboardButton(text="Выбрать другую дату", callback_data="choose_another_date")],
            ]
        )
        return keyboard

    # Создание клавиатуры с кнопкой "Назад" для просмотра тренировки
    def get_view_training_back_keyboard(self):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back_to_trainings")],
            ]
        )
        return keyboard

    # Обработка выбора типа тренировки
    async def process_training_selection(self, callback_query: CallbackQuery, state: FSMContext):
        if callback_query.data == "custom_training":
            await state.set_state(Form.custom_training_date)
            await callback_query.message.edit_text("Выберите дату для своей тренировки:", reply_markup=await DialogCalendar().start_calendar())
        elif callback_query.data == "my_trainings":
            await state.set_state(Form.my_trainings)
            await callback_query.message.edit_text("Выберите тренировку для просмотра:", reply_markup=self.get_view_training_keyboard(callback_query.from_user.id))
        else:
            await state.update_data(training_type=callback_query.data)
            await state.set_state(Form.level)
            await callback_query.message.edit_text("Выберите свой уровень подготовки:", reply_markup=self.get_level_keyboard())
        await callback_query.answer()

    # Обработка выбора уровня тренировки
    async def process_level_selection(self, callback_query: CallbackQuery, state: FSMContext):
        level = callback_query.data
        data = await state.get_data()
        training_type = data.get('training_type')

        file_paths = {
            "split_training": {
                "beginner": r'C:\Users\nikit\Desktop\Курсач\Сплит\Начальный_сплит.xlsx',
                "intermediate": r'C:\Users\nikit\Desktop\Курсач\Сплит\Средний_сплит.xlsx',
                "advanced": r'C:\Users\nikit\Desktop\Курсач\Сплит\Продвинутый_сплит.xlsx'
            },
            "fullbody_training": {
                "beginner": r'C:\Users\nikit\Desktop\Курсач\Фулбади\Начальный_фулбади.xlsx',
                "intermediate": r'C:\Users\nikit\Desktop\Курсач\Фулбади\Средний_фулбади.xlsx',
                "advanced": r'C:\Users\nikit\Desktop\Курсач\Фулбади\Продвинутый_фулбади.xlsx'
            },
            "cardio_training": {
                "beginner": r'C:\Users\nikit\Desktop\Курсач\Кардио\Начальный_кардио.xlsx',
                "intermediate": r'C:\Users\nikit\Desktop\Курсач\Кардио\Средний_кардио.xlsx',
                "advanced": r'C:\Users\nikit\Desktop\Курсач\Кардио\Продвинутый_кардио.xlsx'
            }
        }

        if training_type in file_paths and level in file_paths[training_type]:
            document = FSInputFile(file_paths[training_type][level])
            await callback_query.message.answer_document(document, caption="Вот твоя программа")
            await callback_query.message.answer("Вот всё, что мне удалось найти", reply_markup=self.get_back_keyboard())

        # Удаление сообщения с выбором уровня подготовки
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        await callback_query.answer()

    # Обработка выбора даты для создания тренировки
    async def process_custom_training_date(self, callback_query: CallbackQuery, callback_data: dict, state: FSMContext):
        result, key = await DialogCalendar().process_selection(callback_query, callback_data)
        if result:
            selected_date = key.strftime("%d/%m/%Y")
            from datetime import datetime
            if datetime.strptime(selected_date, "%d/%m/%Y") > datetime.now():
                await callback_query.message.edit_text("Данная дата ещё не наступила, попробуйте выбрать другой день.", reply_markup=await DialogCalendar().start_calendar())
                return

            await state.update_data(custom_training_date=selected_date)
            existing_training = session.query(Training).filter_by(user_id=callback_query.from_user.id, date=selected_date).first()
            if existing_training:
                await state.set_state(Form.custom_training_name)
                await callback_query.message.edit_text(f"Тренировка на {selected_date} уже существует. Что вы хотите сделать?", reply_markup=self.get_existing_training_keyboard())
            else:
                await state.set_state(Form.custom_training_name)
                await callback_query.message.edit_text(f"Выбрана дата: {selected_date}. Напишите название тренировки:")
        await callback_query.answer()

    # Сохранение названия тренировки
    async def save_custom_training_name(self, message: Message, state: FSMContext):
        data = await state.get_data()
        date = data.get('custom_training_date')
        user_id = message.from_user.id
        name = message.text

        # Проверка, что дата не в будущем
        from datetime import datetime
        selected_date = datetime.strptime(date, "%d/%m/%Y")
        if selected_date > datetime.now():
            await message.answer("Данная дата ещё не наступила, попробуйте выбрать другой день.")
            return

        # Проверка, что тренировка на эту дату уже не существует
        existing_training = session.query(Training).filter_by(user_id=user_id, date=date).first()
        if existing_training:
            await message.answer(f"Тренировка на {date} уже существует: {existing_training.name}")
        else:
            new_training = Training(user_id=user_id, date=date, name=name)
            session.add(new_training)
            session.commit()
            await state.update_data(training_id=new_training.id)
            await state.set_state(Form.custom_training_exercise)
            await message.answer("Тренировка сохранена. Теперь создайте упражнение. Напишите название упражнения:")

    # Сохранение упражнения
    async def save_custom_training_exercise(self, message: Message, state: FSMContext):
        data = await state.get_data()
        training_id = data.get('training_id')
        exercise_name = message.text

        new_exercise = Exercise(training_id=training_id, name=exercise_name)
        session.add(new_exercise)
        session.commit()
        await state.update_data(exercise_id=new_exercise.id)
        await state.set_state(Form.custom_training_set)
        await message.answer("Упражнение сохранено. Теперь введите повторения и вес за подход в формате: Подходы x Вес.")

    # Сохранение подходов и веса
    async def save_custom_training_set(self, message: Message, state: FSMContext):
        data = await state.get_data()
        exercise_id = data.get('exercise_id')
        sets_weight = message.text.split(' x ')
        if len(sets_weight) == 2:
            sets, weight = sets_weight
            exercise = session.query(Exercise).filter_by(id=exercise_id).first()
            exercise.sets = sets
            exercise.weight = weight
            session.commit()
            await message.answer("Подход сохранен. Что вы хотите сделать дальше?", reply_markup=self.get_exercise_keyboard())
        else:
            await message.answer("Некорректный формат. Пожалуйста, используйте формат: Подходы x Вес.")

    # Обработка выбора упражнения
    async def process_exercise_selection(self, callback_query: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        exercise_id = data.get('exercise_id')
        exercise = session.query(Exercise).filter_by(id=exercise_id).first()

        if callback_query.data == "add_set":
            await state.set_state(Form.custom_training_set)
            await callback_query.message.edit_text(f"Текущие подходы для {exercise.name}: {exercise.sets} x {exercise.weight}. Напишите новый подход и вес в формате: Подходы x Вес.")
        elif callback_query.data == "new_exercise":
            await state.set_state(Form.custom_training_exercise)
            await callback_query.message.edit_text("Напишите название нового упражнения:")
        elif callback_query.data == "finish_training":
            training_id = data.get('training_id')
            exercises = session.query(Exercise).filter_by(training_id=training_id).all()
            exercises_text = "\n".join([f"{exercise.name}: {exercise.sets} x {exercise.weight}" for exercise in exercises])
            await state.set_state(Form.main)
            await callback_query.message.edit_text(f"Тренировка завершена. Вот всё, что вы сделали:\n{exercises_text}\n\nСейчас вы перенаправитесь в раздел «Тренировки»")
            await asyncio.sleep(5)
            await callback_query.message.edit_text("Привет, выберите то, что вас интересует:", reply_markup=self.get_training_types_keyboard())
        await callback_query.answer()

    # Обработка выбора существующей тренировки
    async def process_existing_training_selection(self, callback_query: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        date = data.get('custom_training_date')
        user_id = callback_query.from_user.id
        if callback_query.data == "view_training":
            training = session.query(Training).filter_by(user_id=user_id, date=date).first()
            if training is None:
                await callback_query.message.edit_text(f"Тренировка на {date} не найдена.")
                return
            exercises = session.query(Exercise).filter_by(training_id=training.id).all()
            exercises_text = "\n".join([f"{exercise.name}: {exercise.sets} x {exercise.weight}" for exercise in exercises])
            await state.set_state(Form.view_training)
            await callback_query.message.edit_text(f"Тренировка на {date}:\n{exercises_text}", reply_markup=self.get_view_training_back_keyboard())
        elif callback_query.data == "choose_another_date":
            await state.set_state(Form.custom_training_date)
            await callback_query.message.edit_text("Выберите новую дату для тренировки:", reply_markup=await DialogCalendar().start_calendar())
        await callback_query.answer()

    # Обработка выбора тренировки для просмотра
    async def process_my_trainings_selection(self, callback_query: CallbackQuery, state: FSMContext):
        training_id = int(callback_query.data.split('_')[-1])
        training = session.query(Training).filter_by(id=training_id).first()
        if training is None:
            await callback_query.message.edit_text("Тренировка не найдена.")
            return
        exercises = session.query(Exercise).filter_by(training_id=training.id).all()
        exercises_text = "\n".join([f"{exercise.name}: {exercise.sets} x {exercise.weight}" for exercise in exercises])
        await state.set_state(Form.view_training)
        await callback_query.message.edit_text(f"Тренировка на {training.date}:\n{exercises_text}", reply_markup=self.get_view_training_back_keyboard())
        await callback_query.answer()

    # Обработка пагинации
    async def process_pagination(self, callback_query: CallbackQuery, state: FSMContext):
        user_id = callback_query.from_user.id
        page = int(callback_query.data.split('_')[-1])
        await callback_query.message.edit_text("Выберите тренировку для просмотра:", reply_markup=self.get_view_training_keyboard(user_id, page))
        await callback_query.answer()

    # Обработка отмены
    async def process_cancel(self, callback_query: CallbackQuery, state: FSMContext):
        await state.set_state(Form.training_type)
        await callback_query.message.edit_text("Выберите вид тренировки:", reply_markup=self.get_training_types_keyboard())
        await callback_query.answer()

    # Регистрация обработчиков
    def register_handlers(self):
        self.dp.callback_query.register(self.process_training_selection, lambda c: c.data in ["custom_training", "my_trainings", "split_training", "fullbody_training", "cardio_training"])
        self.dp.callback_query.register(self.process_level_selection, lambda c: c.data in ["beginner", "intermediate", "advanced"])
        self.dp.callback_query.register(self.process_custom_training_date, DialogCalendarCallback.filter())
        self.dp.message.register(self.save_custom_training_name, Form.custom_training_name)
        self.dp.message.register(self.save_custom_training_exercise, Form.custom_training_exercise)
        self.dp.message.register(self.save_custom_training_set, Form.custom_training_set)
        self.dp.callback_query.register(self.process_exercise_selection, lambda c: c.data in ["add_set", "new_exercise", "finish_training"])
        self.dp.callback_query.register(self.process_existing_training_selection, lambda c: c.data in ["view_training", "choose_another_date"])
        self.dp.callback_query.register(self.process_my_trainings_selection, lambda c: c.data.startswith("view_training_"))
        self.dp.callback_query.register(self.process_pagination, lambda c: c.data.startswith("prev_page_") or c.data.startswith("next_page_"))
        self.dp.callback_query.register(self.process_cancel, lambda c: c.data == "cancel")

# Класс для обработки питания
class NutritionBot:
    def __init__(self, dp: Dispatcher):
        self.dp = dp
        self.register_handlers()

    # Создание клавиатуры для питания
    def get_nutrition_keyboard(self):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Расчёт КБЖУ", url="https://nfacademy.ru/calc")],
                [InlineKeyboardButton(text="Спортпит", url="https://telegra.ph/Sport-pit-07-09")],
                [InlineKeyboardButton(text="Назад", callback_data="back_to_main")],
            ]
        )
        return keyboard

    # Обработка
    async def process_nutrition_selection(self, callback_query: CallbackQuery):
        await callback_query.message.edit_text("Выберите опцию:", reply_markup=self.get_nutrition_keyboard())
        await callback_query.answer()

    # Регистрация обработчиков
    def register_handlers(self):
        self.dp.callback_query.register(self.process_nutrition_selection, lambda c: c.data == "nutrition")

# Класс для обработки советов
class TipsBot:
    def __init__(self, dp: Dispatcher):
        self.dp = dp
        self.register_handlers()

    # Создание клавиатуры для советов
    def get_tips_keyboard(self):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Разминка", url="https://telegra.ph/Razminka-12-25")],
                [InlineKeyboardButton(text="Сон", url="https://telegra.ph/Son-12-25-6")],
                [InlineKeyboardButton(text="Рекомпозиция", url="https://telegra.ph/Rekompoziciya-sushka-12-25")],
                [InlineKeyboardButton(text="Травмы", url="https://telegra.ph/Testovyj-dokument-07-09")],
                [InlineKeyboardButton(text="Назад", callback_data="back_to_main")],
            ]
        )
        return keyboard

    # Обработка выбора совета
    async def process_tips_selection(self, callback_query: CallbackQuery):
        await callback_query.message.edit_text("Выберите совет:", reply_markup=self.get_tips_keyboard())
        await callback_query.answer()

    # Регистрация обработчиков
    def register_handlers(self):
        self.dp.callback_query.register(self.process_tips_selection, lambda c: c.data == "tips")

# Основной класс бота
class MainBot:
    def __init__(self, dp: Dispatcher):
        self.dp = dp
        self.training_bot = TrainingBot(dp)
        self.nutrition_bot = NutritionBot(dp)
        self.tips_bot = TipsBot(dp)
        self.register_handlers()

    # Создание главной клавиатуры
    def get_main_keyboard(self):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Тренировки", callback_data="trainings")],
                [InlineKeyboardButton(text="Советы", callback_data="tips")],
                [InlineKeyboardButton(text="Питание", callback_data="nutrition")],
            ]
        )
        return keyboard

    # Отправка приветственного сообщения
    async def send_welcome(self, message: Message, state: FSMContext):
        user_name = message.from_user.first_name
        await state.set_state(Form.main)
        await message.answer(f"Привет, {user_name}, выберите то, что вас интересует:", reply_markup=self.get_main_keyboard())

    # Обработка выбора основного меню
    async def process_main_selection(self, callback_query: CallbackQuery, state: FSMContext):
        if callback_query.data == "trainings":
            await state.set_state(Form.training_type)
            await callback_query.message.edit_text("Выберите вид тренировки:", reply_markup=self.training_bot.get_training_types_keyboard())
        elif callback_query.data == "tips":
            await state.set_state(Form.main)
            await callback_query.message.edit_text("Выберите совет:", reply_markup=self.tips_bot.get_tips_keyboard())
        elif callback_query.data == "nutrition":
            await callback_query.message.edit_text("Выберите опцию:", reply_markup=self.nutrition_bot.get_nutrition_keyboard())
        await callback_query.answer()

    # Обработка выбора "Назад"
    async def process_back_selection(self, callback_query: CallbackQuery, state: FSMContext):
        current_state = await state.get_state()
        if current_state == Form.training_type.state:
            await state.set_state(Form.main)
            await callback_query.message.edit_text("Привет, выберите то, что вас интересует:", reply_markup=self.get_main_keyboard())
        elif current_state == Form.level.state:
            await state.set_state(Form.training_type)
            await callback_query.message.edit_text("Выберите вид тренировки:", reply_markup=self.training_bot.get_training_types_keyboard())
        elif current_state == Form.custom_training.state:
            await state.set_state(Form.training_type)
            await callback_query.message.edit_text("Выберите вид тренировки:", reply_markup=self.training_bot.get_training_types_keyboard())
        elif current_state == Form.my_trainings.state:
            await state.set_state(Form.training_type)
            await callback_query.message.edit_text("Выберите вид тренировки:", reply_markup=self.training_bot.get_training_types_keyboard())
        elif current_state == Form.view_training.state:
            await state.set_state(Form.training_type)
            await callback_query.message.edit_text("Выберите вид тренировки:", reply_markup=self.training_bot.get_training_types_keyboard())
        elif current_state == Form.main.state and callback_query.data == "back_to_main":
            await callback_query.message.edit_text("Привет, выберите то, что вас интересует:", reply_markup=self.get_main_keyboard())
        await callback_query.answer()

    # Регистрация обработчиков
    def register_handlers(self):
        self.dp.message.register(self.send_welcome, Command(commands=['start']))
        self.dp.callback_query.register(self.process_main_selection, lambda c: c.data in ["trainings", "tips", "nutrition"])
        self.dp.callback_query.register(self.process_back_selection, lambda c: c.data == "back_to_main" or c.data == "back_to_trainings")

    # Запуск опроса
    async def start_polling(self):
        await self.dp.start_polling(bot)

if __name__ == '__main__':
    main_bot = MainBot(dp)
    asyncio.run(main_bot.start_polling())