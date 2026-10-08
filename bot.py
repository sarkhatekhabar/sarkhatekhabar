import os
import feedparser
import requests
import hashlib
from bs4 import BeautifulSoup
from telegram import Bot

TOKEN = os.getenv("TOKEN")
CHANNEL = "@SARKHATEAKHBARNEWS"

RSS_FEEDS = {
    "ایرنا": "https://www.irna.ir/rss",
    "ایسنا": "https://www.isna.ir/rss",
    "مهر": "https://www.mehrnews.com/rss",
    "تسنیم": "https://www.tasnimnews.com/fa/rss",
}

MAX_NEWS_PER_RUN = 5
TIMEOUT = 15

sent_news = set()


def get_image(url):
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={
            "User-Agent": "Mozilla/5.0"
        })
        soup = BeautifulSoup(r.text, "html.parser")

        image = soup.find("meta", property="og:image")

        if image and image.get("content"):
            return image["content"]

    except Exception:
        pass

    return None


def make_summary(text, max_length=500):
    text = BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)

    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0] + "..."

    return text


def news_id(title, link):
    return hashlib.md5(
        (title + link).encode("utf-8")
    ).hexdigest()


def get_news():
    news = []

    for source, rss_url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(rss_url)

            for item in feed.entries[:5]:
                title = item.get("title", "").strip()
                link = item.get("link", "").strip()
                description = item.get("summary", "")

                if not title or not link:
                    continue

                uid = news_id(title, link)

                if uid in sent_news:
                    continue

                news.append({
                    "source": source,
                    "title": title,
                    "link": link,
                    "description": description,
                    "uid": uid
                })

        except Exception as e:
            print(f"خطا در دریافت {source}: {e}")

    return news[:MAX_NEWS_PER_RUN]


async def send_news():
    bot = Bot(token=TOKEN)

    news_list = get_news()

    print(f"تعداد خبرهای جدید: {len(news_list)}")

    for news in news_list:

        title = news["title"]
        source = news["source"]
        link = news["link"]

        description = make_summary(news["description"])

        text = (
            f"📰 {title}\n\n"
            f"📌 {description}\n\n"
            f"🔗 منبع: {source}\n"
            f"{link}\n\n"
            f"@SARKHATEAKHBARNEWS"
        )

        image_url = get_image(link)

        try:
            if image_url:
                await bot.send_photo(
                    chat_id=CHANNEL,
                    photo=image_url,
                    caption=text
                )
            else:
                await bot.send_message(
                    chat_id=CHANNEL,
                    text=text
                )

            sent_news.add(news["uid"])

            print(f"ارسال شد: {title}")

        except Exception as e:
            print(f"خطا در ارسال خبر: {e}")


if __name__ == "__main__":
    import asyncio

    if not TOKEN:
        print("❌ توکن ربات پیدا نشد!")
    else:
        print("🤖 ربات شروع به کار کرد...")
        asyncio.run(send_news())
