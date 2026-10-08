import os
import asyncio
import re
from io import BytesIO

import feedparser
import requests
from bs4 import BeautifulSoup

from telegram.ext import Application


TOKEN = os.getenv("TOKEN")

CHANNEL = "@SARKHATEKHABARNEWS1"
CHANNEL_LINK = "https://t.me/SARKHATEKHABARNEWS1"

# حداکثر خبر در هر بررسی
MAX_NEWS = 3

# بررسی هر ۵ دقیقه
CHECK_TIME = 300

sent_links = set()


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


def clean(text):

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


def short_summary(text):

    text = clean(text)

    if not text:
        return "جزئیات بیشتر این خبر در منبع اصلی منتشر شده است."

    # حذف عبارت‌های اضافی احتمالی
    text = re.sub(
        r"(ادامه خبر|بیشتر بخوانید|منبع:).*",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()

    # حدود ۲ تا ۳ خط
    # حدود ۲۵۰ تا ۳۰۰ کاراکتر
    if len(text) > 280:

        text = (
            text[:280]
            .rsplit(" ", 1)[0]
            + "..."
        )

    return text


def category(title, source):

    text = (
        title +
        " " +
        source
    ).lower()

    sports = [
        "فوتبال",
        "استقلال",
        "پرسپولیس",
        "تیم ملی",
        "ورزش",
        "جام جهانی",
        "قهرمانی",
        "لیگ"
    ]

    economy = [
        "دلار",
        "طلا",
        "سکه",
        "بورس",
        "بنزین",
        "تورم",
        "اقتصاد",
        "قیمت",
        "خودرو",
        "مسکن",
        "ارز"
    ]

    technology = [
        "فناوری",
        "تکنولوژی",
        "هوش مصنوعی",
        "موبایل",
        "گوشی",
        "اینترنت",
        "گوگل",
        "اپل",
        "مایکروسافت"
    ]

    world = [
        "آمریکا",
        "ترامپ",
        "اسرائیل",
        "روسیه",
        "اوکراین",
        "چین",
        "غزه",
        "فلسطین",
        "اروپا"
    ]

    if any(x in text for x in sports):
        return "ورزشی"

    if any(x in text for x in economy):
        return "اقتصادی"

    if any(x in text for x in technology):
        return "فناوری"

    if any(x in text for x in world):
        return "بین‌الملل"

    return "عمومی"


def importance(title, summary):

    text = (
        title +
        " " +
        summary
    ).lower()

    score = 0

    very_important = [
        "فوری",
        "خبر فوری",
        "حمله",
        "جنگ",
        "موشک",
        "انفجار",
        "زلزله",
        "سیل",
        "آتش‌سوزی",
        "کشته",
        "مصدوم",
        "ترور",
        "بازداشت",
        "تحریم",
        "بحران",
        "هشدار"
    ]

    important = [
        "ایران",
        "رئیس جمهور",
        "رئیس‌جمهور",
        "رهبر",
        "دولت",
        "مجلس",
        "وزیر",
        "انتخابات",
        "آمریکا",
        "ترامپ",
        "اسرائیل",
        "روسیه",
        "اوکراین",
        "غزه",
        "فلسطین",
        "دلار",
        "طلا",
        "سکه",
        "بورس",
        "بنزین",
        "تورم",
        "قیمت",
        "فوتبال",
        "تیم ملی",
        "استقلال",
        "پرسپولیس",
        "جام جهانی",
        "هوش مصنوعی"
    ]

    for word in very_important:

       
