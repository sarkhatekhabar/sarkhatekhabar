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


TOKEN = os.getenv("TOKEN")

# کانال برای ارسال خبر
CHANNEL = "@SARKHATEKHABARNEW"

# لینک عمومی کانال
CHANNEL_LINK = "https://t.me/SARKHATEKHABARNEWS1"


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


# جلوگیری از ارسال خبرهای تکراری
sent_links = set()

# حداکثر خبر در هر ساعت
MAX_NEWS_PER_HOUR = 30

news_counter = 0


def clean_text(text):
    """پاک کردن HTML و متن‌های اضافی"""

    if not text:
        return ""

    soup = BeautifulSoup(text, "html.parser")

    text = soup.get_text(" ", strip=True)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def get_category(source, title):
    """تشخیص دسته خبر"""

    text = (source + " " + title).lower()

    if any(x in text for x in [
        "ورزش",
        "فوتبال",
        "استقلال",
        "پرسپولیس",
        "لیگ",
        "بازیکن"
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
        "خودرو"
    ]):
        return "💰 اقتصادی"

    if any(x in text for x in [
        "فناوری",
        "تکنولوژی",
        "هوش مصنوعی",
        "موبایل",
        "گوشی",
        "اینترنت",
        "کامپیوتر"
    ]):
        return "💻 فناوری"

    if any(x in text for x in [
        "جهان",
        "آمریکا",
        "اروپا",
        "اسرائیل",
        "روسیه",
        "چین",
        "غزه",
        "اوکراین"
    ]):
        return "🌍 بین‌الملل"

    return "📰 عمومی"


def get_image_and_video(url):

    image_data = None
    video_url = None

    try:

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        r = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        # -------------------------
        # عکس اصلی خبر
        # -------------------------

        image = soup.find(
            "meta",
            property="og:image"
        )

        if image and image.get("content"):

            image_url = image["content"]

            try:

                img = requests.get(
                    image_url,
                    headers=headers,
                    timeout=15
                )

                if img.status_code == 200:

                    image_data = BytesIO(
                        img.content
                    )

                    image_data.name = "news.jpg"

            except Exception as e:

                print(
                    "خطای دریافت عکس:",
                    e
                )

        # -------------------------
        # ویدئو
        # -------------------------

        video = soup.find(
            "meta",
            property="og:video"
        )

        if video and video.get("content"):

            video_url = video["content"]

        if not video_url:

            video = soup.find(
                "meta",
                property="og:video:url"
            )

            if video and video.get("content"):

                video_url = video["content"]

    except Exception as e:

        print(
            "خطای دریافت رسانه:",
            e
        )

    return image_data, video_url


def make_keyboard(link):

    keyboard = [
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
            ),
            InlineKeyboardButton(
                "👎 ضعیف",
                callback_data="bad"
            )
        ],
        [
            InlineKeyboardButton(
                "📤 اشتراک‌گذاری",
                url=CHANNEL_LINK
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


async def feedback(update, context):

    query = update.callback_query

    try:

        await query.answer(
            "بازخورد شما ثبت شد ❤️"
        )

    except Exception as e:

        print(
            "خطای بازخورد:",
            e
        )


async def send_news(
    app,
    item,
    source
):

    global news_counter

    try:

        if news_counter >= MAX_NEWS_PER_HOUR:

            return

        link = item.get(
            "link",
            ""
        )

        title = clean_text(
            item.get(
                "title",
                ""
            )
        )

        summary = clean_text(
            item.get(
                "summary",
                ""
            )
        )

        if not link or not title:

            return

        # جلوگیری از تکرار
        if link in sent_links:

            return

        category = get_category(
            source,
            title
        )

        # خلاصه کوتاه‌تر
        if len(summary) > 350:

            summary = summary[:350] + "..."

        if not summary:

            summary = "برای مشاهده جزئیات خبر روی «ادامه خبر» بزنید."

        text = f"""🔴 {category}

📰 {title}

{summary}

📡 منبع: {source}

📣 سرخط خبر
📢 کانال ما:
{CHANNEL_LINK}
"""

        keyboard = make_keyboard(
            link
        )

        image, video = get_image_and_video(
            link
        )

        # -------------------------
        # ارسال ویدئو
        # -------------------------

        if video:

            try:

                await app.bot.send_video(
                    chat_id=CHANNEL,
                    video=video,
                    caption=text,
                    reply_markup=keyboard
                )

                print(
                    "ویدئو ارسال شد:",
                    title
                )

                sent_links.add(link)

                news_counter += 1

                return

            except Exception as e:

                print(
                    "ارسال ویدئو ناموفق:",
                    e
                )

        # -------------------------
        # ارسال عکس
        # -------------------------

        if image:

            try:

                await app.bot.send_photo(
                    chat_id=CHANNEL,
                    photo=image,
                    caption=text,
                    reply_markup=keyboard
                )

                print(
                    "خبر + عکس ارسال شد:",
                    title
                )

                sent_links.add(link)

                news_counter += 1

                return

            except Exception as e:

                print(
                    "ارسال عکس ناموفق:",
                    e
                )

        # -------------------------
        # ارسال متن
        # -------------------------

        await app.bot.send_message(
            chat_id=CHANNEL,
            text=text,
            reply_markup=keyboard
        )

        print(
            "خبر متنی ارسال شد:",
            title
        )

        sent_links.add(link)

        news_counter += 1

    except Exception as e:

        print(
            "خطا در ارسال خبر:",
            e
        )


async def check_news(app):

    global news_counter

    first_run = True

    while True:

        news_counter = 0

        print(
            "شروع بررسی خبرها..."
        )

        for source, rss_url in RSS_FEEDS.items():

            if news_counter >= MAX_NEWS_PER_HOUR:

                break

            try:

                print(
                    "بررسی:",
                    source
                )

                feed = feedparser.parse(
                    rss_url
                )

                if not feed.entries:

                    print(
                        "خبری پیدا نشد:",
                        source
                    )

                    continue

                # در اجرای اول فقط خبر اول
                if first_run:

                    items = feed.entries[:1]

                else:

                    # حداکثر ۳ خبر از هر منبع
                    items = feed.entries[:3]

                for item in items:

                    if news_counter >= MAX_NEWS_PER_HOUR:

                        break

                    await send_news(
                        app,
                        item,
                        source
                    )

                    await asyncio.sleep(2)

            except Exception as e:

                print(
                    "خطا در منبع",
                    source,
                    ":",
                    e
                )

        first_run = False

        print(
            "تعداد خبر این دور:",
            news_counter
        )

        print(
            "پایان بررسی منابع."
        )

        # هر ۲ ساعت دوباره بررسی
        await asyncio.sleep(
            7200
        )


async def main():

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    # سیستم بازخورد
    app.add_handler(
        CallbackQueryHandler(
            feedback
        )
    )

    print(
        "ربات خبری روشن شد..."
    )

    await app.initialize()

    await app.start()

    asyncio.create_task(
        check_news(app)
    )

    await asyncio.Event().wait()


if __name__ == "__main__":

    asyncio.run(main())





