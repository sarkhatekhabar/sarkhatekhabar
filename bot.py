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

MAX_NEWS = 3
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

    soup = BeautifulSoup(text, "html.parser")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def short_summary(text):
    text = clean(text)

    if not text:
        return "جزئیات بیشتر این خبر در منبع اصلی منتشر شده است."

    text = re.sub(
        r"(ادامه خبر|بیشتر بخوانید|منبع:).*",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()

    if len(text) > 280:
        text = text[:280].rsplit(" ", 1)[0] + "..."

    return text


def category(title, source):
    text = (title + " " + source).lower()

    sports = [
        "فوتبال", "استقلال", "پرسپولیس",
        "تیم ملی", "ورزش", "جام جهانی",
        "قهرمانی", "لیگ"
    ]

    economy = [
        "دلار", "طلا", "سکه", "بورس",
        "بنزین", "تورم", "اقتصاد",
        "قیمت", "خودرو", "مسکن", "ارز"
    ]

    technology = [
        "فناوری", "تکنولوژی", "هوش مصنوعی",
        "موبایل", "گوشی", "اینترنت",
        "گوگل", "اپل", "مایکروسافت"
    ]

    world = [
        "آمریکا", "ترامپ", "اسرائیل",
        "روسیه", "اوکراین", "چین",
        "غزه", "فلسطین", "اروپا"
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
    text = (title + " " + summary).lower()

    score = 0

    very_important = [
        "فوری", "خبر فوری", "حمله", "جنگ",
        "موشک", "انفجار", "زلزله", "سیل",
        "آتش‌سوزی", "کشته", "مصدوم",
        "ترور", "بازداشت", "تحریم",
        "بحران", "هشدار"
    ]

    important = [
        "ایران", "رئیس جمهور", "رئیس‌جمهور",
        "رهبر", "دولت", "مجلس", "وزیر",
        "انتخابات", "آمریکا", "ترامپ",
        "اسرائیل", "روسیه", "اوکراین",
        "غزه", "فلسطین", "دلار", "طلا",
        "سکه", "بورس", "بنزین", "تورم",
        "قیمت", "فوتبال", "تیم ملی",
        "استقلال", "پرسپولیس", "جام جهانی",
        "هوش مصنوعی"
    ]

    for word in very_important:
        if word in text:
            score += 3

    for word in important:
        if word in text:
            score += 1

    return score


def get_feed(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

        return feedparser.parse(response.content)

    except Exception as error:
        print("خطا در دریافت RSS:", error)
        return None


def get_media(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        tag = soup.find(
            "meta",
            property="og:image"
        )

        if not tag:
            tag = soup.find(
                "meta",
                attrs={"name": "twitter:image"}
            )

        if tag:
            image_url = tag.get("content")

            if image_url:
                image_response = requests.get(
                    image_url,
                    headers=headers,
                    timeout=15
                )

                image_response.raise_for_status()

                image = BytesIO(
                    image_response.content
                )

                image.name = "news.jpg"

                return image

    except Exception as error:
        print("خطای دریافت عکس:", error)

    return None


def make_text(title, summary, source):
    summary = short_summary(summary)

    text = (
        f"{category(title, source)}\n\n"
        f"{title}\n\n"
        f"{summary}\n"
        f"منبع: {source}\n\n"
        f"{CHANNEL_LINK}"
    )

    return text


async def send_news(app, item, source):
    try:
        link = item.get("link", "")
        title = clean(item.get("title", ""))
        summary = clean(item.get("summary", ""))

        if not link or not title:
            return False

        if link in sent_links:
            return False

        text = make_text(
            title,
            summary,
            source
        )

        image = await asyncio.to_thread(
            get_media,
            link
        )

        if image:
            try:
                image.seek(0)

                await app.bot.send_photo(
                    chat_id=CHANNEL,
                    photo=image,
                    caption=text[:1024]
                )

                print("عکس + خبر:", title)

                sent_links.add(link)

                return True

            except Exception as error:
                print(
                    "ارسال عکس انجام نشد:",
                    error
                )

        await app.bot.send_message(
            chat_id=CHANNEL,
            text=text
        )

        print("خبر:", title)

        sent_links.add(link)

        return True

    except Exception as error:
        print(
            "خطای ارسال خبر:",
            error
        )

        return False


async def check_news(app):
    while True:
        print()
        print("================

       
