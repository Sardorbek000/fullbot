import asyncio
import logging
import json
from typing import Dict, Any
from datetime import datetime
import random
import string
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.exceptions import TelegramBadRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot va kanal ma'lumotlari
BOT_TOKEN = "7545334583:AAEH_EV1Pif5CMipNYi6q1WqWVszz8MRSNE"
CHANNEL_ID = "-1002464112677"
ADMIN_IDS = [861521974]
ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "123"

# FSM States
class AdminStates(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()
    waiting_for_video = State()
    waiting_for_video_name = State()
    waiting_for_ad_text = State()
    waiting_for_ad_media = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()
    confirm_ad = State()

class AdManager:
    def __init__(self):
        self.current_ad = {}
        self.ads_history = []

    def save_ad(self, ad_data: dict):
        ad_data['created_at'] = datetime.now().isoformat()
        self.ads_history.append(ad_data)

    def clear_current_ad(self):
        self.current_ad = {}

ad_manager = AdManager()

class VideoData:
    def __init__(self):
        self.videos: Dict[str, Dict[str, Any]] = {}
        self.users: Dict[int, Dict[str, Any]] = {}
        self.last_video_number = 0
        self.load_data()

    def load_data(self):
        try:
            with open('data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.videos = data.get('videos', {})
                self.users = data.get('users', {})
                # Mavjud videolar ichidan eng katta raqamni topish
                if self.videos:
                    max_number = max(int(code.split('_')[1]) for code in self.videos.keys() if code.startswith('video_'))
                    self.last_video_number = max_number
        except FileNotFoundError:
            self.save_data()
        except json.JSONDecodeError:
            logger.error("JSON file is corrupted")
            self.save_data()

    def save_data(self):
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump({
                'videos': self.videos,
                'users': self.users
            }, f, ensure_ascii=False, indent=4)

    def add_user(self, user_id: int, user_data: dict):
        self.users[str(user_id)] = {
            'id': user_id,
            'username': user_data.get('username'),
            'full_name': user_data.get('full_name'),
            'joined_date': datetime.now().isoformat()
        }
        self.save_data()

    def add_video(self, code: str, data: dict):
        self.videos[code] = data
        self.save_data()

    def get_next_video_code(self) -> str:
        """Keyingi video uchun noyob kod generatsiya qilish"""
        self.last_video_number += 1
        return f"8234{self.last_video_number}238"

# Keyboards
def get_admin_keyboard():
    buttons = [
        [types.KeyboardButton(text="🎬 Video qo'shish")],
        [types.KeyboardButton(text="📊 Statistika")],
        [types.KeyboardButton(text="Reklama tayyorlash")],
        [types.KeyboardButton(text="📢 Reklama tarqatish")],
        [types.KeyboardButton(text="🔙 Adminlikdan chiqish")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_video_share_keyboard(bot_username: str, code: str):
    buttons = [
        [InlineKeyboardButton(
            text="♻️ Do'stlarga ulashish",
            url=f"https://t.me/{bot_username}?start={code}"
        )]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Bot initialization
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
video_data = VideoData()

# Command handlers
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    logger.info(f"Start command received from user {user_id}")

    # Foydalanuvchini ro'yxatga olish
    if str(user_id) not in video_data.users:
        video_data.add_user(user_id, {
            'username': message.from_user.username,
            'full_name': message.from_user.full_name
        })

    # Start parametrlarini tekshirish
    args = message.text.split()
    if len(args) > 1:
        video_code = args[1]
        logger.info(f"Requested video code: {video_code}")

        # Videoni kod bo'yicha qidirish
        found_video = video_data.videos.get(video_code)

        if found_video:
            try:
                # Videoni yuborish
                await message.answer_video(
                    video=found_video['file_id'],
                    caption=found_video['name'],  # Faqat video nomini ko‘rsatamiz
                )
                logger.info(f"Video {video_code} successfully sent to user {user_id}")
                return
            except Exception as e:
                logger.error(f"Error sending video: {e}")
                await message.answer("Video yuborishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
                return
        else:
            logger.warning(f"Video not found with code: {video_code}")
            await message.answer("Kechirasiz, so'ralgan video topilmadi.")
            return

    # Agar start parametrsiz bo'lsa
    await message.answer("Assalomu alaykum! Video ko'rish uchun menga link orqali kiring.")


@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Bu buyruq faqat adminlar uchun!")
        return

    await message.answer("Admin loginini kiriting:")
    await state.set_state(AdminStates.waiting_for_login)

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    total_users = len(video_data.users)
    total_videos = len(video_data.videos)

    stats = f"📊 Bot statistikasi:\n\n"
    stats += f"👥 Foydalanuvchilar: {total_users}\n"
    stats += f"🎬 Videolar: {total_videos}\n"

    await message.answer(stats)

# Admin state handlers
@dp.message(AdminStates.waiting_for_login)
async def process_login(message: types.Message, state: FSMContext):
    if message.text == ADMIN_LOGIN:
        await message.answer("Parolni kiriting:")
        await state.set_state(AdminStates.waiting_for_password)
    else:
        await message.answer("Noto'g'ri login!")
        await state.clear()

@dp.message(AdminStates.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        await message.answer("Admin panelga xush kelibsiz!", reply_markup=get_admin_keyboard())
        await state.clear()
    else:
        await message.answer("Noto'g'ri parol!")
        await state.clear()

# Video qo'shish handlers
@dp.message(F.text == "🎬 Video qo'shish")
async def add_video(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer("Video nomini kiriting:")
    await state.set_state(AdminStates.waiting_for_video_name)

@dp.message(AdminStates.waiting_for_video_name)
async def process_video_name(message: types.Message, state: FSMContext):
    await state.update_data(video_name=message.text)
    await message.answer("Video faylini yuboring:")
    await state.set_state(AdminStates.waiting_for_video)

@dp.message(F.video, AdminStates.waiting_for_video)
async def process_video(message: types.Message, state: FSMContext, bot: Bot):
    try:
        data = await state.get_data()
        video_name = data['video_name']
        file_id = message.video.file_id

        # Yangi video kodi generatsiya qilish
        video_code = video_data.get_next_video_code()

        bot_info = await bot.get_me()
        share_url = f"https://t.me/{bot_info.username}?start={video_code}"

        # Video sarlavhasi uchun caption
        caption = f"🎬 {video_name}\n\n🔗 Ulashish: {share_url}"


        # Videoni kanalga yuborish
        channel_post = await bot.send_video(
            chat_id=CHANNEL_ID,
            video=file_id,
            caption=caption,
            reply_markup=get_video_share_keyboard(bot_info.username, video_code)
        )

        # Video ma'lumotlarini saqlash
        video_data.add_video(video_code, {
            'file_id': file_id,
            'name': video_name,
            'code': video_code,
            'caption': caption,
            'channel_message_id': channel_post.message_id,
            'date_added': datetime.now().isoformat()
        })

        logger.info(f"New video added - Name: {video_name}, Code: {video_code}")

        await message.answer(
            f"✅ Video muvaffaqiyatli qo'shildi!\n\n"
            f"📝 Nomi: {video_name}\n"
            f"🔢 Ichki kod: {video_code}\n"
            f"🔗 Ulashish linki: {share_url}",
            reply_markup=get_video_share_keyboard(bot_info.username, video_code)
        )

    except Exception as e:
        logger.error(f"Error processing video: {e}")
        await message.answer("Xatolik yuz berdi. Qaytadan urinib ko'ring.")
    finally:
        await state.clear()

# Reklama tarqatish handlers
# Reklama tayyorlash handlers
@dp.message(F.text == "Reklama tayyorlash")
async def start_ad_creation(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    ad_manager.clear_current_ad()
    await message.answer(
        "Reklama yaratish boshlandi!\n\n"
        "Reklama matnini kiriting:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="🚫 Bekor qilish")]],
            resize_keyboard=True
        )
    )
    await state.set_state(AdminStates.waiting_for_ad_text)

# Reklama matnini qabul qilish
@dp.message(AdminStates.waiting_for_ad_text)
async def process_ad_text(message: types.Message, state: FSMContext):
    if message.text == "🚫 Bekor qilish":
        await cancel_ad_creation(message, state)
        return

    ad_manager.current_ad['text'] = message.text
    await message.answer(
        "✅ Matn saqlandi!\n\n"
        "Endi reklama uchun rasm/video yuboring yoki o'tkazib yuborish uchun \"➡️ O'tkazib yuborish\" tugmasini bosing:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="➡️ O'tkazib yuborish")],
                [types.KeyboardButton(text="🚫 Bekor qilish")]
            ],
            resize_keyboard=True
        )
    )
    await state.set_state(AdminStates.waiting_for_ad_media)

# Reklama media faylini qabul qilish
@dp.message(AdminStates.waiting_for_ad_media)
async def process_ad_media(message: types.Message, state: FSMContext):
    if message.text == "🚫 Bekor qilish":
        await cancel_ad_creation(message, state)
        return

    if message.text == "➡️ O'tkazib yuborish":
        ad_manager.current_ad['has_media'] = False
    else:
        if message.photo:
            ad_manager.current_ad['media_type'] = 'photo'
            ad_manager.current_ad['media_id'] = message.photo[-1].file_id
            ad_manager.current_ad['has_media'] = True
        elif message.video:
            ad_manager.current_ad['media_type'] = 'video'
            ad_manager.current_ad['media_id'] = message.video.file_id
            ad_manager.current_ad['has_media'] = True
        else:
            await message.answer("❌ Noto'g'ri format! Iltimos, rasm yoki video yuboring.")
            return

    await message.answer(
        "Tugma uchun matnni kiriting:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="➡️ O'tkazib yuborish")],
                [types.KeyboardButton(text="🚫 Bekor qilish")]
            ],
            resize_keyboard=True
        )
    )
    await state.set_state(AdminStates.waiting_for_button_text)

# Tugma matni uchun handler
@dp.message(AdminStates.waiting_for_button_text)
async def process_button_text(message: types.Message, state: FSMContext):
    if message.text == "🚫 Bekor qilish":
        await cancel_ad_creation(message, state)
        return

    if message.text == "➡️ O'tkazib yuborish":
        ad_manager.current_ad['has_button'] = False
        await preview_ad(message, state)
    else:
        ad_manager.current_ad['button_text'] = message.text
        ad_manager.current_ad['has_button'] = True
        await message.answer("Tugma uchun URL manzilini kiriting:")
        await state.set_state(AdminStates.waiting_for_button_url)

# Tugma URL manzili uchun handler
@dp.message(AdminStates.waiting_for_button_url)
async def process_button_url(message: types.Message, state: FSMContext):
    if message.text == "🚫 Bekor qilish":
        await cancel_ad_creation(message, state)
        return

    if not message.text.startswith(('http://', 'https://')):
        await message.answer("❌ URL noto'g'ri formatda! URL http:// yoki https:// bilan boshlanishi kerak.")
        return

    ad_manager.current_ad['button_url'] = message.text
    await preview_ad(message, state)

# Reklamani ko'rish va tasdiqlash
async def preview_ad(message: types.Message, state: FSMContext):
    keyboard = []

    if ad_manager.current_ad.get('has_button', False):
        keyboard.append([
            InlineKeyboardButton(
                text=ad_manager.current_ad['button_text'],
                url=ad_manager.current_ad['button_url']
            )
        ])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    preview_text = "📢 Reklama ko'rinishi:\n\n" + ad_manager.current_ad['text']

    reply_markup = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="✅ Tasdiqlash")],
            [types.KeyboardButton(text="🚫 Bekor qilish")]
        ],
        resize_keyboard=True
    )

    try:
        if ad_manager.current_ad.get('has_media', False):
            if ad_manager.current_ad['media_type'] == 'photo':
                await message.answer_photo(
                    photo=ad_manager.current_ad['media_id'],
                    caption=preview_text,
                    reply_markup=markup
                )
            else:  # video
                await message.answer_video(
                    video=ad_manager.current_ad['media_id'],
                    caption=preview_text,
                    reply_markup=markup
                )
        else:
            await message.answer(preview_text, reply_markup=markup)

        await message.answer(
            "Reklamani tasdiqlaysizmi?",
            reply_markup=reply_markup
        )

        await state.set_state(AdminStates.confirm_ad)

    except Exception as e:
        logger.error(f"Preview ad error: {e}")
        await message.answer(
            "Reklamani ko'rishda xatolik yuz berdi. Qaytadan urinib ko'ring.",
            reply_markup=get_admin_keyboard()
        )
        await state.clear()

# Reklamani tasdiqlash yoki bekor qilish
@dp.message(AdminStates.confirm_ad)
async def confirm_ad(message: types.Message, state: FSMContext):
    if message.text == "🚫 Bekor qilish":
        await cancel_ad_creation(message, state)
        return

    if message.text == "✅ Tasdiqlash":
        ad_manager.save_ad(ad_manager.current_ad)
        await message.answer(
            "✅ Reklama muvaffaqiyatli saqlandi!\n\n"
            "Reklamani tarqatish uchun \"📢 Reklama tarqatish\" tugmasini bosing.",
            reply_markup=get_admin_keyboard()
        )
        await state.clear()

# Reklamani bekor qilish
async def cancel_ad_creation(message: types.Message, state: FSMContext):
    ad_manager.clear_current_ad()
    await message.answer(
        "❌ Reklama yaratish bekor qilindi!",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()

# Reklama tarqatish handler
@dp.message(F.text == "📢 Reklama tarqatish")
async def distribute_ad(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    if not ad_manager.current_ad:
        await message.answer("❌ Avval reklama yarating!")
        return

    try:
        sent_count = 0
        failed_count = 0

        # Inline keyboard yaratish
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text=ad_manager.current_ad['button_text'],
                    url=ad_manager.current_ad['button_url']
                )
            ]] if ad_manager.current_ad.get('has_button', False) else []
        )

        # Har bir foydalanuvchiga yuborish
        for user_id in video_data.users:
            try:
                if ad_manager.current_ad.get('has_media', False):
                    if ad_manager.current_ad['media_type'] == 'photo':
                        await message.bot.send_photo(
                            chat_id=user_id,
                            photo=ad_manager.current_ad['media_id'],
                            caption=ad_manager.current_ad['text'],
                            reply_markup=markup
                        )
                    else:  # video
                        await message.bot.send_video(
                            chat_id=user_id,
                            video=ad_manager.current_ad['media_id'],
                            caption=ad_manager.current_ad['text'],
                            reply_markup=markup
                        )
                else:
                    await message.bot.send_message(
                        chat_id=user_id,
                        text=ad_manager.current_ad['text'],
                        reply_markup=markup
                    )
                sent_count += 1
                await asyncio.sleep(0.05)  # Telegram API limitations
            except Exception as e:
                logger.error(f"Error sending ad to user {user_id}: {e}")
                failed_count += 1

        # Natijalarni ko'rsatish
        await message.answer(
            f"📊 Reklama tarqatish yakunlandi:\n\n"
            f"✅ Muvaffaqiyatli: {sent_count}\n"
            f"❌ Muvaffaqiyatsiz: {failed_count}"
        )

    except Exception as e:
        logger.error(f"Ad distribution error: {e}")
        await message.answer("Reklama tarqatishda xatolik yuz berdi. Qaytadan urinib ko'ring.")



# Statistika handler
@dp.message(F.text == "📊 Statistika")
async def show_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    total_users = len(video_data.users)
    total_videos = len(video_data.videos)

    stats = (
        f"📊 Bot statistikasi\n\n"
        f"👥 Foydalanuvchilar: {total_users}\n"
        f"🎬 Videolar soni: {total_videos}\n\n"
        f"📅 Oxirgi 24 soat ichida:\n"
        f"➕ Yangi foydalanuvchilar: {0}\n"
        f"👁 Video ko'rishlar: {0}"
    )

    await message.answer(stats)

# Adminlikdan chiqish handler
@dp.message(F.text == "🔙 Adminlikdan chiqish")
async def logout_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        "Siz admin paneldan chiqdingiz!",
        reply_markup=types.ReplyKeyboardRemove()
    )

# Bot ishga tushirish
async def main():
    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
