import os
import asyncio
import re
from io import BytesIO

import feedparser
import requests
from bs4 import BeautifulSoup

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler


TOKEN = os.getenv("TOKEN")

CHANNEL = "@SARKHATEKHABARNEW"
CHANNEL_LINK = "https://t.me/SARKHATEKHABARNEWS1"

MAX_NEWS = 10
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


def get_media(url):
    image = None

    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

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
                r = requests.get(
                    image_url,
                    headers=headers,
                    timeout=10
                )

                if r.status_code == 200:
                    image = BytesIO(r.content)
                    image.name = "news.jpg"

    except Exception as error:
        print("خطای عکس:", error)

    return image


def keyboard(link):
    buttons = [
        [
            InlineKeyboardButton(
                "🔗 ادامه خبر",
                url=link
            )
        ],
        [
            InlineKeyboardButton(
                "👍 مفید",
                callback_data="useful"
            ),
            InlineKeyboardButton(
                "❤️ جالب",
                callback_data="interesting"
            ),
            InlineKeyboardButton(
                "🔥 مهم",
                callback_data="important"
            )
        ],
        [
            InlineKeyboardButton(
                "📤 اشتراک‌گذاری",
                url=CHANNEL_LINK
            )
        ]
    ]

    return InlineKeyboardMarkup(buttons)


async def feedback(update, context):
    try:
        await update.callback_query.answer(
            "بازخورد شما ثبت شد ❤️"
        )
    except Exception as error:
        print("خطای بازخورد:", error)


async def send_news(app, item, source):
    try:
        link = item.get("link", "")
        title = clean(item.get("title", ""))
        summary = clean(item.get("summary", ""))

        if not link or not title:
            return False

        if link in sent_links:
            return False

        score = importance(title, summary)

        if score < 2:
            print("کم‌اهمیت:", title)
            return False

        if len(summary) > 300:
            summary = summary[:300] + "..."

        if not summary:
            summary = "برای مشاهده جزئیات خبر روی «ادامه خبر» بزنید."

        text = (
            f"{category(title, source)}\n\n"
            f"📰 {title}\n\n"
            f"{summary}\n\n"
            f"📡 منبع: {source}\n\n"
            f"📣 سرخط خبر\n"
            f"📢 {CHANNEL_LINK}"
        )

        image = get_media(link)
        buttons = keyboard(link)

        if image:
            try:
                image.seek(0)

                await app.bot.send_photo(
                    chat_id=CHANNEL,
                    photo=image,
                    caption=text[:1024],
                    reply_markup=buttons
                )

                print("✅ عکس + خبر:", title)

                sent_links.add(link)

                return True

            except Exception as error:
                print("خطای ارسال عکس:", error)

        await app.bot.send_message(
            chat_id=CHANNEL,
            text=text,
            reply_markup=buttons
        )

        print("✅ خبر:", title)

        sent_links.add(link)

        return True

    except Exception as error:
        print("خطای خبر:", error)

    return False


async def check_news(app):
    while True:

        print("================================")
        print("🔎 بررسی خبرهای جدید...")
        print("================================")

        candidates = []

        for source, rss in RSS_FEEDS.items():

            try:
                feed = feedparser.parse(rss)

                for item in feed.entries[:10]:

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

                    if score >= 2:
                        candidates.append(
                            (
                                score,
                                source,
                                item
                            )
                        )

            except Exception as error:
                print(
                    "خطا در",
                    source,
                    ":",
                    error
                )

        candidates.sort(
            key=lambda x: x[0],
            reverse=True
        )

        print(
            "🔥 خبرهای مهم:",
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
            "⏱️ بررسی بعدی ۵ دقیقه دیگر"
        )

        await asyncio.sleep(CHECK_TIME)


async def main():

    if not TOKEN:
        print("❌ TOKEN پیدا نشد")
        return

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    app.add_handler(
        CallbackQueryHandler(feedback)
    )

    print("🚀 ربات خبری روشن شد")
    print("⏱️ بررسی هر ۵ دقیقه")
    print("🔥 حداکثر ۱۰ خبر مهم")

    await app.initialize()
    await app.start()

    asyncio.create_task(
        check_news(app)
    )

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())

