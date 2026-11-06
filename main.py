import os
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

DRUGS_FILE = "drugs_database.json"

# Render Environment Variables bo'limidan avtomatik o'qiydi
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNELS = ["@fundamedical_academy"]  # Faqat bitta rasmiy kanal qoldirildi
WEB_APP_URL = os.getenv("WEB_APP_URL", os.getenv("WEBAPP_URL", "https://pharmaxotira-bot.onrender.com"))

bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher()
router = Router()

# JSON ma'lumotlarini server ishga tushganda 1 marta xotiraga yuklash (Caching)
DRUGS_CACHE = []

def load_drugs():
    global DRUGS_CACHE
    if os.path.exists(DRUGS_FILE):
        try:
            with open(DRUGS_FILE, "r", encoding="utf-8") as f:
                DRUGS_CACHE = json.load(f)
                return DRUGS_CACHE
        except Exception as e:
            print(f"JSON o'qishda xatolik: {e}")
    DRUGS_CACHE = []
    return DRUGS_CACHE

START_TEXT = (
    "👋 <b>PharmaXotira</b> botiga xush kelibsiz!\n\n"
    "💊 Bu bot farmakologiya fanidan <b>\"Periferik asab sistemasiga ta'sir etuvchi dorilar\"</b> "
    "bo'limidagi 63 ta dori vositasini interaktiv flashcardlar va mnemonikalar orqali oson yodlashingizga yordam beradi.\n\n"
    "📚 <b>Ma'lumotlar manbasi:</b>\n"
    "Barcha dori dozalari va chiqarilish shakllari <b>\"Retseptura 2017\"</b> o'quv qo'llanmasi hamda "
    "xalqaro tibbiy manbalar (Medscape, Drugs.com) asosida shakllantirilgan.\n\n"
    "📥 <b>Taklif va murojaatlar uchun:</b>\n"
    "Bot bo'yicha taklif va mulohazalaringiz bo'lsa, @Shakhbozbek_Abdulamitov ga murojaat qilishingiz mumkin.\n\n"
    "👇 Pastdagi tugma orqali Mini App'ni ochishingiz mumkin:"
)

@router.message(CommandStart())
async def start_handler(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Mini App'ni ochish",
                    web_app=WebAppInfo(url=WEB_APP_URL)
                )
            ],
            [
                InlineKeyboardButton(
                    text="📢 Rasmiy kanal",
                    url="https://t.me/fundamedical_academy"
                )
            ]
        ]
    )
    await message.answer(text=START_TEXT, reply_markup=keyboard, parse_mode="HTML")

dp.include_router(router)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Server ishga tushganda dori bazasini xotiraga 1 marta yuklaymiz
    load_drugs()
    
    polling_task = None
    if bot:
        await bot.delete_webhook(drop_pending_updates=True)
        polling_task = asyncio.create_task(dp.start_polling(bot))
    
    yield
    
    if bot:
        if polling_task:
            polling_task.cancel()
        await bot.session.close()

app = FastAPI(lifespan=lifespan)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
@app.get("/app")
async def read_app():
    return FileResponse("static/index.html")

@app.get("/api/drugs")
async def get_drugs():
    # Faylni qayta-qayta o'qimasdan xotiradagi tayyor keshni qaytaradi
    return DRUGS_CACHE

@app.get("/api/check-sub")
async def check_subscription(user_id: int = Query(...)):
    if not bot:
        return {"subscribed": True}

    for channel in CHANNELS:
        try:
            # httpx o'rniga Aiogram'ning rasmiy async bot obyektidan foydalaniladi
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return {"subscribed": False, "channel": channel}
        except (TelegramBadRequest, TelegramAPIError) as e:
            print(f"Kanal {channel} bo'yicha obuna tekshirishda xatolik (Bot admin qilinganmi?): {e}")
            return {"subscribed": False, "channel": channel}
        except Exception as e:
            print(f"Kutilmagan xatolik: {e}")
            return {"subscribed": False, "channel": channel}

    return {"subscribed": True}
