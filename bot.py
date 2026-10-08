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
# تنظیمات
# =========================================================

TOKEN = os.getenv("TOKEN")

CHANNEL = "@SARKHATEKHABARNEW"

CHANNEL_LINK = "https://t.me/SARKHATEKHABARNEWS1"

# حداکثر خبر مهم در هر بررسی
MAX_NEWS_PER_CHECK = 10

# فاصله بین بررسی‌ها
CHECK_INTERVAL = 300  # 300 ثانیه = 5 دقیقه


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
    "زومیت": "https://www.zoomit.ir/feed/",
}


# =========================================================
# خبرهای ارسال‌شده
# =========================================================

sent_links = set()


# =========================================================
# پاک کردن متن
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
# تشخیص دسته خبر
# =========================================================

def get_category(source, title):

    text = (
        source + " " + title
    ).lower()

    if any(x in text for x in [
        "ورزش",
        "فوتبال",
        "استقلال",
        "پرسپولیس",
        "لیگ",
        "بازیکن",
        "تیم ملی",
        "قهرمانی"
    ]):
        return "⚽ ورزشی"

    if any(x in text for x in [
        "اقتصاد",
        "دلار",
        "طلا",
        "بورس",
        "بانک",
        "بازار",
        "قیمت",
        "خودرو",
        "





