import os
import feedparser
import requests
from bs4 import BeautifulSoup
from telegram import Bot

TOKEN = os.getenv("TOKEN")
CHANNEL = "@KHABARNEWS6"

RSS_FEEDS = {
    "ایرنا": "https://www.irna.ir/rss",
    "ایسنا": "https://www.isna.ir/rss",
    "مهر": "https://www.mehrnews.com/rss",
    "تسنیم": "https://www.tasnimnews.com/fa/rss",
}

MAX_NEWS_PER_RUN = 5
TIMEOUT = 15


def get_image(url):
    try:
        response = requests.get(
            url,
            timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        soup = BeautifulSoup(response.text, "html.parser")

        # تصویر اصلی خبر
        image = soup.find("meta", property="og:image")

        if image and image.get("content"):
            return image["content"]

    except Exception as e:
        print("خطا در دریافت تصویر:", e)

    return None


def make_summary(text, max_length=500):
    text = BeautifulSoup(
        text or "",
        "html.parser"
    ).get_text(" ", strip=True)

    if not text:
        return "برای مطالعه جزئیات کامل خبر، به منبع مراجعه کنید."

    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0] + "..."

    return text


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

                news.append({
                    "source": source,
                    "title": title,
                    "link": link,
                    "description": description
                })

        except Exception as e:
            print(f"خطا در دریافت اخبار {source}: {e}")

    return news[:MAX_NEWS_PER_RUN]


async def send_news():

    bot = Bot(token=TOKEN)

    news_list = get_news()

    print(f"تعداد خبرهای دریافت شده: {len(news_list)}")

    for news in news_list:

        title = news["title"]
        source = news["source"]
        link = news["link"]

        summary = make_summary(
            news["description"]
        )

        # قالب نهایی پیام
        text = (
            f"📰 {title}\n\n"
            f"📌 {summary}\n\n"
            f"🔗 منبع: {source}\n"
            f"{link}\n\n"
            f"@KHABARNEWS6"
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

            print(f"✅ خبر ارسال شد: {title}")

        except Exception as e:

            print(f"❌ خطا در ارسال خبر: {e}")


if __name__ == "__main__":

    import asyncio

    if not TOKEN:

        print("❌ توکن ربات پیدا نشد!")

    else:

        print("🤖 ربات شروع به کار کرد...")

        asyncio.run(send_news())

