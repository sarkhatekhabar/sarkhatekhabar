import os
import asyncio
import re
from io import BytesIO

import feedparser
import requests
from bs4 import BeautifulSoup
from telegram.ext import Application


TOKEN = os.getenv("TOKEN")

CHANNEL = "@SARKHATEAKHBARNEWS"
CHANNEL_LINK = "https://t.me/SARKHATEAKHBARNEWS"

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
    "زومیت": "https://www.zoomit.ir/feed/",
}


def clean(text):
    if not text:
        return ""

    text = BeautifulSoup(
        str(text),
        "html.parser"
    ).get_text(" ", strip=True)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def short_summary(text):
    text = clean(text)

    if not text:
        return "جزئیات بیشتر این خبر در منبع اصلی منتشر شده است."

    text = re.split(
        r"(ادامه خبر|بیشتر بخوانید|منبع:)",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]

    text = text.strip()

    if len(text) > 280:
        text = text[:280]

        if " " in text:
            text = text.rsplit(" ", 1)[0]

        text += "..."

    return text


def category(title, source):
    text = f"{title} {source}".lower()

    sports_words = [
        "ورزش",
        "فوتبال",
        "لیگ",
        "بازیکن",
        "تیم",
        "جام جهانی",
        "پرسپولیس",
        "استقلال",
        "والیبال",
        "بسکتبال",
        "کشتی",
    ]

    economy_words = [
        "اقتصاد",
        "دلار",
        "یورو",
        "طلا",
        "سکه",
        "بورس",
        "بانک",
        "قیمت",
        "بازار",
        "تورم",
        "مسکن",
        "خودرو",
    ]

    technology_words = [
        "فناوری",
        "تکنولوژی",
        "هوش مصنوعی",
        "موبایل",
        "گوشی",
        "سامسونگ",
        "اپل",
        "اینترنت",
        "نرم افزار",
        "سخت افزار",
        "ربات",
    ]

    world_words = [
        "آمریکا",
        "اروپا",
        "اسرائیل",
        "غزه",
        "فلسطین",
        "اوکراین",
        "روسیه",
        "ترامپ",
        "جهان",
        "بین الملل",
        "بین‌الملل",
    ]

    if any(word in text for word in sports_words):
        return "ورزشی"

    if any(word in text for word in economy_words):
        return "اقتصادی"

    if any(word in text for word in technology_words):
        return "فناوری"

    if any(word in text for word in world_words):
        return "بین‌الملل"

    return "عمومی"


def importance(title, summary):
    text = f"{title} {summary}".lower()

    very_important = [
        "فوری",
        "زلزله",
        "سیل",
        "جنگ",
        "حمله",
        "انفجار",
        "آتش سوزی",
        "آتش‌سوزی",
        "کشته",
        "مفقود",
        "تحریم",
        "رئیس جمهور",
        "رئیس‌جمهور",
    ]

    important = [
        "دولت",
        "مجلس",
        "وزیر",
        "وزارت",
        "انتخابات",
        "دلار",
        "طلا",
        "بنزین",
        "قیمت",
        "بازار",
        "ایران",
        "تهران",
        "استان",
    ]

    score = 0

    for word in very_important:
        if word in text:
            score += 3

    for word in important:
        if word in text:
            score += 1

    return score


def get_feed(url):
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "Chrome/120 Safari/537.36"
                )
            },
            timeout=20,
        )

        response.raise_for_status()

        return feedparser.parse(response.content)

    except Exception as e:
        print(f"خطا در دریافت RSS: {e}")
        return None


def get_media(url):
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "Chrome/120 Safari/537.36"
                )
            },
            timeout=20,
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        image_url = None

        og_image = soup.find(
            "meta",
            property="og:image"
        )

        if og_image:
            image_url = og_image.get("content")

        if not image_url:
            twitter_image = soup.find(
                "meta",
                attrs={"name": "twitter:image"}
            )

            if twitter_image:
                image_url = twitter_image.get("content")

        if not image_url:
            return None

        image_response = requests.get(
            image_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )

        image_response.raise_for_status()

        image = BytesIO(image_response.content)
        image.name = "news.jpg"

        return image

    except Exception as e:
        print(f"تصویر پیدا نشد: {e}")
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
        title = clean(
            item.get("title", "خبر جدید")
        )

        link = item.get("link", "").strip()

        if not link:
            return False

        if link in sent_links:
            return False

        summary = clean(
            item.get("summary")
            or item.get("description")
            or ""
        )

        score = importance(
            title,
            summary
        )

        if score < 1:
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
                await app.bot.send_photo(
                    chat_id=CHANNEL,
                    photo=image,
                    caption=text[:1024],
                )

            except Exception as e:
                print(
                    f"خطا در ارسال تصویر: {e}"
                )

                await app.bot.send_message(
                    chat_id=CHANNEL,
                    text=text,
                    disable_web_page_preview=False,
                )

        else:
            await app.bot.send_message(
                chat_id=CHANNEL,
                text=text,
                disable_web_page_preview=False,
            )

        sent_links.add(link)

        print(
            f"خبر ارسال شد: {title}"
        )

        return True

    except Exception as e:
        print(
            f"خطا در ارسال خبر: {e}"
        )

        return False


async def check_news(app):
    while True:
        print(
            "در حال بررسی خبرهای جدید..."
        )

        candidates = []

        for source, rss_url in RSS_FEEDS.items():
            feed = await asyncio.to_thread(
                get_feed,
                rss_url
            )

            if not feed:
                continue

            entries = getattr(
                feed,
                "entries",
                []
            )

            for item in entries[:5]:
                title = clean(
                    item.get("title", "")
                )

                link = item.get(
                    "link",
                    ""
                ).strip()

                if not title or not link:
                    continue

                if link in sent_links:
                    continue

                summary = clean(
                    item.get("summary")
                    or item.get("description")
                    or ""
                )

                score = importance(
                    title,
                    summary
                )

                if score < 1:
                    continue

                candidates.append(
                    {
                        "item": item,
                        "source": source,
                        "score": score,
                    }
                )

        candidates.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        sent_count = 0

        for candidate in candidates:
            if sent_count >= MAX_NEWS:
                break

            success = await send_news(
                app,
                candidate["item"],
                candidate["source"]
            )

            if success:
                sent_count += 1
                await asyncio.sleep(5)

        print(
            f"بررسی تمام شد. "
            f"تعداد خبرهای ارسال‌شده: {sent_count}"
        )

        print(
            f"بررسی بعدی تا "
            f"{CHECK_TIME} ثانیه دیگر."
        )

        await asyncio.sleep(
            CHECK_TIME
        )


async def main():
    if not TOKEN:
        print(
            "خطا: توکن ربات پیدا نشد."
        )
        return

    print(
        "ربات خبری در حال شروع است..."
    )

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    await app.initialize()
    await app.start()

    print(
        "ربات با موفقیت روشن شد."
    )

    asyncio.create_task(
        check_news(app)
    )

    try:
        while True:
            await asyncio.sleep(3600)

    except KeyboardInterrupt:
        print(
            "ربات متوقف شد."
        )

    finally:
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())





