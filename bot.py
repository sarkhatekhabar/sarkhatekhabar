import os
import feedparser
import asyncio
import requests
import re

from io import BytesIO
from bs4 import BeautifulSoup

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    Application,
    CallbackQueryHandler
)


# =========================================================
# تنظیمات اصلی
# =========================================================

TOKEN = os.getenv("TOKEN")

CHANNEL = "@SARKHATEKHABARNEW"

CHANNEL_LINK = "https://t.me/SARKHATEKHABARNEWS1"

# حداکثر تعداد خبر در هر نوبت
MAX_NEWS_PER_CHECK = 10

# بررسی هر 5 دقیقه
CHECK_INTERVAL = 300


# =========================================================
# منابع خبری
# =========================================================

RSS_FEEDS = {
    "ایرنا": "https://www.irna.ir/rss",
    "ایسنا": "https://www.isna.ir/rss",
    "مهر": "https://www.mehrnews.com/rss",
    "خبرآنلاین": "https://www.khabaronline.ir/rss",
    "باشگاه خبرنگاران": "https://www.yjc.ir/fa/rss/allnews",
    "تابناک": "https://www.tabnak.ir/fa/rss/allnews",
    "عصر ایران": "https://www.asriran.com/fa/rss/allnews",
    "تسنیم": "https://www.tasnimnews.com/fa/rss",
    "ورزش سه": "https://www.varzesh3.com/rss/all",
    "زومیت": "https://www.zoomit.ir/feed/"
}


# =========================================================
# خبرهای ارسال‌شده
# =========================================================

sent_links = set()
sent_titles = set()


# =========================================================
# پاک کردن HTML
# =========================================================

def clean_text(text):

    if not text:
        return ""

    soup = BeautifulSoup(
        text,
        "html.parser"
    )

    text = soup.get_text(
        " ",
        strip=True
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =========================================================
# دسته‌بندی خبر
# =========================================================

def get_category(source, title):

    text = (
        source + " " + title
    ).lower()

    if any(word in text for word in [
        "ورزش",
        "فوتبال",
        "استقلال",
        "پرسپولیس",
        "لیگ",
        "بازیکن",
        "تیم ملی",
        "جام جهانی",
        "قهرمانی"
    ]):
        return "⚽ ورزشی"

    if any(word in text for word in [
        "اقتصاد",
        "دلار",
        "طلا",
        "بورس",
        "بانک",
        "بازار",
        "قیمت",
        "خودرو",
        "تورم",
        "سکه",
        "بنزین",
        "ارز",
        "مسکن"
    ]):
        return "💰 اقتصادی"

    if any(word in text for word in [
        "فناوری",
        "تکنولوژی",
        "هوش مصنوعی",
        "موبایل",
        "گوشی",
        "اینترنت",
        "کامپیوتر",
        "گوگل",
        "اپل",
        "مایکروسافت"
    ]):
        return "💻 فناوری"

    if any(word in text for word in [
        "آمریکا",
        "ترامپ",
        "اسرائیل",
        "روسیه",
        "چین",
        "غزه",
        "اوکراین",
        "اروپا",
        "فلسطین",
        "خاورمیانه"
    ]):
        return "🌍 بین‌الملل"

    return "📰 عمومی"


# =========================================================
# امتیاز اهمیت خبر
# =========================================================

def get_importance_score(title, summary, source):

    text = (
        title + " " +
        summary + " " +
        source
    ).lower()

    score = 0

    # خبرهای خیلی مهم
    very_important = [
        "خبر فوری",
        "فوری",
        "حمله",
        "جنگ",
        "موشک",
        "انفجار",
        "زلزله",
        "سیل",
        "آتش سوزی",
        "آتش‌سوزی",
        "کشته",
        "مصدوم",
        "ترور",
        "بازداشت",
        "تحریم",
        "بحران",
        "هشدار",
        "فاجعه"
    ]

    for word in very_important:
        if word in text:
            score += 3

    # سیاست و ایران
    political = [
        "ایران",
        "رئیس جمهور",
        "رئیس‌جمهور",
        "رهبر",
        "دولت",
        "مجلس",
        "وزیر",
        "انتخابات",
        "رئیس مجلس",
        "قوه قضاییه",
        "سپاه",
        "ارتش"
    ]

    for word in political:
        if word in text:
            score += 2

    # اقتصاد
    economic = [
        "دلار",
        "یورو",
        "طلا",
        "سکه",
        "بورس",
        "بنزین",
        "قیمت",
        "تورم",
        "حقوق",
        "وام",
        "خودرو",
        "مسکن",
        "ارز"
    ]

    for word in economic:
        if word in text:
            score += 2

    # بین‌الملل
    international = [
        "آمریکا",
        "ترامپ",
        "اسرائیل",
        "روسیه",
        "اوکراین",
        "چین",
        "غزه",
        "فلسطین",
        "اروپا",
        "خاورمیانه"
    ]

    for word in international:
        if word

