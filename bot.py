import os
import asyncio
import feedparser
import requests
from bs4 import BeautifulSoup

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
)

# =========================
# تنظیمات
# =========================

TOKEN = os.getenv("TOKEN")
CHANNEL = "@KHABARNEWS6"

MAX_NEWS = 10
CHECK_INTERVAL = 300  # هر 5 دقیقه

RSS_FEEDS = {
    "ایرنا": "https://www.irna.ir/rss",
    "ایسنا": "https://www.isna.ir/rss",
    "مهر": "https://www.mehrnews.com/rss",
    "تسنیم": "https://www.tasnimnews.com/fa/rss",
}

sent_links = set()


# =========================
# گرفتن تصویر خبر
# =========================

def get_news_image(url):
    try:
        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        soup = BeautifulSoup(response.text, "html.parser")

        image = soup.find(
            "meta",
            property="og:image"
        )

        if image and image.get("content"):
            return image["content"]

    except Exception as e:
        print("خطا در دریافت تصویر:", e)

    return None


# =========================
# ساخت خلاصه
# =========================

def make_summary(text):
    text = BeautifulSoup(
        text or "",
        "html.parser"
    ).get_text(" ", strip=True)

    if not text:
        return "جزئیات بیشتر این خبر را در منبع اصلی بخوانید."

    if len(text) > 350:
        text = text[:350].rsplit(" ", 1)[0] + "..."

    return text


# =========================
# دریافت خبرها
# =========================

def get_news():

    news = []

    for source, rss_url in RSS_FEEDS.items():

        try:

            feed = feedparser.parse(rss_url)

            for item in feed.entries:

                title = item.get(
                    "title",
                    ""
                ).strip()

                link = item.get(
                    "link",
                    ""
                ).strip()

                summary = item.get(
                    "summary",
                    ""
                )

                if not title or not link:
                    continue

                if link in sent_links:
                    continue

                news.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "source": source
                })

                if len(news) >= MAX_NEWS:
                    break

            if len(news) >= MAX_NEWS:
                break

        except Exception as e:

            print(
                f"خطا در دریافت {source}:",
                e
            )

    return news


# =========================
# واکنش‌ها
# =========================

def reaction_buttons():

    keyboard = [
        [
            InlineKeyboardButton(
                "😁",
                callback_data="react_1"
            ),
            InlineKeyboardButton(
                "😍",
                callback_data="react_2"
            ),
            InlineKeyboardButton(
                "😐",
                callback_data="react_3"
            ),
        ],
        [
            InlineKeyboardButton(
                "❤️",
                callback_data="react_4"
            ),
            InlineKeyboardButton(
                "👍",
                callback_data="react_5"
            ),
            InlineKeyboardButton(
                "👎",
                callback_data="react_6"
            ),
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# =========================
# مدیریت واکنش
# =========================

async def reaction_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer("ثبت شد ❤️")


# =========================
# ارسال خبر
# =========================

async def send_news(application):

    news_list = get_news()

    print(
        f"تعداد خبرهای جدید: {len(news_list)}"
    )

    for news in news_list:

        title = news["title"]
        link = news["link"]
        source = news["source"]

        summary = make_summary(
            news["summary"]
        )

        # =========================
        # متن نهایی خبر
        # =========================

        text = (
            f"📰 {title}\n\n"
            f"📌 {summary}\n\n"
            f'📡 <a href="{link}">منبع: {source}</a>\n\n'
            f"@KHABARNEWS6"
        )

        image_url = get_news_image(link)

        try:

            if image_url:

                await application.bot.send_photo(
                    chat_id=CHANNEL,
                    photo=image_url,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=reaction_buttons()
                )

            else:

                await application.bot.send_message(
                    chat_id=CHANNEL,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=reaction_buttons()
                )

            sent_links.add(link)

            print(
                "✅ خبر ارسال شد:",
                title
            )

            # فاصله کوتاه بین خبرها
            await asyncio.sleep(3)

        except Exception as e:

            print(
                "❌ خطا در ارسال:",
                e
            )


# =========================
# اجرای ربات
# =========================

async def news_loop(application):

    while True:

        try:

            await send_news(application)

        except Exception as e:

            print(
                "❌ خطا در اجرای چرخه:",
                e
            )

        print(
            "⏳ بررسی بعدی ۵ دقیقه دیگر..."
        )

        await asyncio.sleep(
            CHECK_INTERVAL
        )


async def post_init(application):

    print(
        "🤖 ربات روشن شد..."
    )

    asyncio.create_task(
        news_loop(application)
    )


# =========================
# شروع
# =========================

def main():

    if not TOKEN:

        print(
            "❌ TOKEN پیدا نشد!"
        )

        return

    application = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(
        CallbackQueryHandler(
            reaction_handler,
            pattern="^react_"
        )
    )

    print(
        "🚀 ربات در حال اجراست..."
    )

    application.run_polling()


if __name__ == "__main__":
    main()

