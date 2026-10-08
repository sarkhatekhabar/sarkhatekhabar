import os
import asyncio
import re
from io import BytesIO

import feedparser
import requests
from bs4 import BeautifulSoup

from telegram.ext import Application


TOKEN = os.getenv("TOKEN")

CHANNEL = "@KHABARNEWS6"

MAX_NEWS = 5
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
        return "⚽ ورزشی"

    if any(x in text for x in economy):
        return "💰 اقتصادی"

    if any(x in text for x in technology):
        return "💻 فناوری"

    if any(x in text for x in world):
        return "🌍 بین‌الملل"

    return "📰 عمومی"


def importance(title, summary):
    text = (title + " " + summary).lower()

    score = 0

    very_important = [
        "فوری", "خبر فوری", "حمله", "جنگ",
        "موشک", "انفجار", "زلزله",
        "سیل", "آتش‌سوزی", "کشته",
        "مصدوم", "ترور", "بازداشت",
        "تحریم", "بحران", "هشدار"
    ]

    important = [
        "ایران", "رئیس جمهور", "رئیس‌جمهور",
        "رهبر", "دولت", "مجلس",
        "وزیر", "انتخابات", "آمریکا",
        "ترامپ", "اسرائیل", "روسیه",
        "اوکراین", "غزه", "فلسطین",
        "دلار", "طلا", "سکه", "بورس",
        "بنزین", "تورم", "قیمت",
        "فوتبال", "تیم ملی", "استقلال",
        "پرسپولیس", "جام جهانی",
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
        print("❌ خطا در RSS:", error)
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
        print("⚠️ خطای عکس:", error)

    return None


async def send_news(app, item, source):

    try:
        link = item.get("link", "")

        title = clean(
            item.get("title", "")
        )

        summary = clean(
            item.get("summary", "")
        )

        if not link or not title:
            return False

        if link in sent_links:
            return False

        # خلاصه کوتاه
        if len(summary) > 300:
            summary = summary[:300] + "..."

        if not summary:
            summary = "جزئیات خبر در منبع اصلی منتشر شده است."

        text = (
            f"{category(title, source)}\n\n"
            f"📰 {title}\n\n"
            f"{summary} /{source}\n\n"
            f"📢 @KHABARNEWS6\n\n"
            f"😁 😍 😐 ❤️ 👍 👎"
        )

        # دریافت عکس خبر
        image = await asyncio.to_thread(
            get_media,
            link
        )

        # اگر عکس داشت
        if image:

            try:
                image.seek(0)

                await app.bot.send_photo(
                    chat_id=CHANNEL,
                    photo=image,
                    caption=text[:1024]
                )

                print(
                    "✅ عکس + خبر:",
                    title
                )

                sent_links.add(link)

                return True

            except Exception as error:

                print(
                    "⚠️ ارسال عکس نشد:",
                    error
                )

        # اگر عکس نداشت
        await app.bot.send_message(
            chat_id=CHANNEL,
            text=text[:4096]
        )

        print(
            "✅ خبر:",
            title
        )

        sent_links.add(link)

        return True

    except Exception as error:

        print(
            "❌ خطای ارسال:",
            error
        )

        return False


async def check_news(app):

    while True:

        print()
        print("==============================")
        print("🔎 بررسی خبرهای جدید...")
        print("==============================")

        candidates = []

        for source, rss in RSS_FEEDS.items():

            print(
                "📡 بررسی:",
                source
            )

            feed = await asyncio.to_thread(
                get_feed,
                rss
            )

            if not feed:

                print(
                    "⚠️ دریافت نشد:",
                    source
                )

                continue

            entries = feed.entries[:10]

            print(
                "تعداد خبر:",
                len(entries)
            )

            for item in entries:

                title = clean(
                    item.get("title", "")
                )

                summary = clean(
                    item.get("summary", "")
                )

                link = item.get(
                    "link",
                    ""
                )

                if not title or not link:
                    continue

                if link in sent_links:
                    continue

                score = importance(
                    title,
                    summary
                )

                if score >= 1:

                    candidates.append(
                        (
                            score,
                            source,
                            item
                        )
                    )

        # مهم‌ترین خبرها اول
        candidates.sort(
            key=lambda x: x[0],
            reverse=True
        )

        print(
            "🔥 خبرهای آماده:",
            len(candidates)
        )

        count = 0

        for score, source, item in candidates:

            if count >= MAX_NEWS:
                break

            success = await send_news(
                app,
                item,
                source
            )

            if success:

                count += 1

                await asyncio.sleep(3)

        print(
            "✅ ارسال این نوبت:",
            count
        )

        print(
            "⏱️ بررسی بعدی ۵ دقیقه دیگر..."
        )

        await asyncio.sleep(
            CHECK_TIME
        )


async def main():

    if not TOKEN:

        print(
            "❌ TOKEN پیدا نشد"
        )

        return

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    print(
        "🚀 ربات خبری روشن شد"
    )

    print(
        "📢 کانال:",
        CHANNEL
    )

    print(
        "⏱️ بررسی هر ۵ دقیقه"
    )

    print(
        "📰 حداکثر ۵ خبر"
    )

    await app.initialize()

    await app.start()

    asyncio.create_task(
        check_news(app)
    )

    await asyncio.Event().wait()


if __name__ == "__main__":

    asyncio.run(main())
