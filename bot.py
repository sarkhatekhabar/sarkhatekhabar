import os
import feedparser
import asyncio
import requests
from io import BytesIO
from bs4 import BeautifulSoup
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application

TOKEN = os.getenv("TOKEN")
CHANNEL = "@SARKHATEKHABARNEW"

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

sent_links = set()


def get_image(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}

        r = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        soup = BeautifulSoup(r.text, "html.parser")

        image = soup.find(
            "meta",
            property="og:image"
        )

        if image and image.get("content"):

            image_url = image["content"]

            img = requests.get(
                image_url,
                headers=headers,
                timeout=15
            )

            if img.status_code == 200:
                return BytesIO(img.content)

    except Exception as e:
        print("خطای عکس:", e)

    return None


async def send_news(app, item, source):

    try:
        link = item.get("link", "")
        title = item.get("title", "")
        summary = item.get("summary", "")

        if not link:
            return

        if link in sent_links:
            return

        text = f"""📰 {title}

{summary[:500]}

📡 سرخط خبر"""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔗 ادامه خبر",
                    url=link
                )
            ]
        ])

        image = get_image(link)

        if image:

            image.name = "news.jpg"

            await app.bot.send_photo(
                chat_id=CHANNEL,
                photo=image,
                caption=text,
                reply_markup=keyboard
            )

            print("خبر + عکس ارسال شد:", title)

        else:

            await app.bot.send_message(
                chat_id=CHANNEL,
                text=text,
                reply_markup=keyboard
            )

            print("خبر بدون عکس ارسال شد:", title)

        sent_links.add(link)

    except Exception as e:
        print("خطا در ارسال خبر:", e)


async def check_news(app):

    first_run = True

    while True:

        for source, rss_url in RSS_FEEDS.items():

            try:

                print("بررسی:", source)

                feed = feedparser.parse(rss_url)

                if not feed.entries:

                    print("خبری پیدا نشد:", source)
                    continue

                if first_run:

                    items = [feed.entries[0]]

                else:

                    items = reversed(feed.entries)

                for item in items:

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

        print("دور بررسی منابع تمام شد.")

        await asyncio.sleep(300)


async def main():

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    print("ربات خبری روشن شد...")

    await app.initialize()
    await app.start()

    asyncio.create_task(
        check_news(app)
    )

    await asyncio.Event().wait()


if __name__ == "__main__":

    asyncio.run(main())


