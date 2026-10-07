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

RSS_URL = "https://www.irna.ir/rss"

sent_links = set()


def get_image(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

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


async def check_news(app):
    first_run = True

    while True:
        try:
            feed = feedparser.parse(RSS_URL)

            if feed.entries:

                if first_run:
                    items = [feed.entries[0]]
                    first_run = False
                else:
                    items = reversed(feed.entries)

                for item in items:

                    link = item.get("link", "")
                    title = item.get("title", "")
                    summary = item.get("summary", "")

                    if not link or link in sent_links:
                        continue

                    text = f"""📰 {title}

{summary[:500]}

📡 منبع: خبرگزاری ایرنا"""

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
            print("خطا:", e)

        await asyncio.sleep(300)


async def main():

    app = Application.builder().token(TOKEN).build()

    print("ربات خبری روشن شد...")

    await app.initialize()
    await app.start()

    asyncio.create_task(check_news(app))

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
