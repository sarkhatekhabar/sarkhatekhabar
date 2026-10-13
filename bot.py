import os
import re
import json
import asyncio
import hashlib
from io import BytesIO
from pathlib import Path
from difflib import SequenceMatcher

import feedparser
import requests
from bs4 import BeautifulSoup
from telegram.ext import Application


TOKEN = os.getenv("TOKEN")
CHANNEL = "@KHABARNEWS6"

MAX_NEWS = 3
CHECK_TIME = 300
MAX_HISTORY = 1000

HISTORY_FILE = Path("sent_news.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; KhabarNewsBot/1.0)"
}

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
sent_titles = []


def clean(text):
    """پاک‌سازی متن خبر"""
    if not text:
        return ""

    text = BeautifulSoup(str(text), "html.parser").get_text(" ")
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\r\n\t]+", " ", text)

    return text.strip()


def normalize(text):
    """یکسان‌سازی متن برای تشخیص خبرهای تکراری"""
    text = clean(text).lower()
    text = text.replace("ي", "ی").replace("ك", "ک")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def category(title, source):
    """تشخیص تقریبی دسته خبر"""
    text = normalize(title)

    if any(word in text for word in [
        "فوتبال", "ورزش", "تیم ملی", "لیگ برتر",
        "پرسپولیس", "استقلال", "والیبال", "بسکتبال"
    ]):
        return "ورزشی"

    if any(word in text for word in [
        "دلار", "طلا", "بورس", "اقتصاد", "تورم",
        "قیمت", "بازار", "خودرو", "بانک", "حقوق"
    ]):
        return "اقتصادی"

    if any(word in text for word in [
        "فناوری", "هوش مصنوعی", "موبایل", "اینترنت",
        "گوگل", "اپل", "سامسونگ", "کامپیوتر"
    ]):
        return "فناوری"

    return "عمومی"


def importance(title, summary, source):
    """امتیازدهی ساده برای اولویت‌بندی خبرها"""
    text = normalize(title + " " + summary)
    score = 0

    important_words = [
        "فوری", "مهم", "اعلام شد", "تصویب شد",
        "رئیس جمهور", "دولت", "وزیر", "مجلس",
        "زلزله", "سیل", "هشدار", "تعطیلی",
        "قیمت بنزین", "یارانه", "کالابرگ",
        "نرخ ارز", "دلار", "سکه", "طلا",
        "تیم ملی", "انتخابات", "آموزش و پرورش"
    ]

    for word in important_words:
        if normalize(word) in text:
            score += 2

    # منابع شناخته‌شده امتیاز پایه می‌گیرند
    trusted_sources = [
        "ایرنا", "ایسنا", "مهر", "تسنیم"
    ]

    if source in trusted_sources:
        score += 1

    if len(clean(title)) < 15:
        score -= 1

    return score


def load_history():
    """بارگذاری سابقه خبرهای ارسال‌شده"""
    global sent_links, sent_titles

    if not HISTORY_FILE.exists():
        return

    try:
        data = json.loads(
            HISTORY_FILE.read_text(encoding="utf-8")
        )

        sent_links = set(data.get("links", []))
        sent_titles = data.get("titles", [])

    except (OSError, ValueError, TypeError):
        sent_links = set()
        sent_titles = []


def save_history():
    """ذخیره سابقه خبرها"""
    global sent_links, sent_titles

    sent_links = set(list(sent_links)[-MAX_HISTORY:])
    sent_titles = sent_titles[-MAX_HISTORY:]

    data = {
        "links": list(sent_links),
        "titles": sent_titles,
    }

    try:
        HISTORY_FILE.write_text(
            json.dumps(data, ensure_ascii=False),
            encoding="utf-8"
        )
    except OSError as error:
        print(f"خطا در ذخیره سابقه: {error}")


def is_duplicate(link, title):
    """بررسی تکراری نبودن خبر"""
    if link and link in sent_links:
        return True

    new_title = normalize(title)

    if not new_title:
        return True

    for old_title in sent_titles[-300:]:
        ratio = SequenceMatcher(
            None,
            new_title,
            normalize(old_title)
        ).ratio()

        if ratio >= 0.82:
            return True

    return False


def get_feed(source, url):
    """دریافت خبرهای یک منبع"""
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )
        response.raise_for_status()

        feed = feedparser.parse(response.content)

        results = []

        for entry in feed.entries[:30]:
            title = clean(entry.get("title", ""))
            link = entry.get("link", "").strip()

            summary = clean(
                entry.get("summary", "")
                or entry.get("description", "")
            )

            if not title or not link:
                continue

            # حذف متن اضافی و کوتاه‌کردن خلاصه
            summary = re.sub(
                r"(ادامه مطلب|بیشتر بخوانید).*",
                "",
                summary
            ).strip()

            results.append({
                "title": title,
                "summary": summary,
                "link": link,
                "source": source,
                "score": importance(title, summary, source),
            })

        return results

    except Exception as error:
        print(f"خطا در دریافت {source}: {error}")
        return []


def get_media(url):
    """پیداکردن تصویر اصلی خبر در صورت وجود"""
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        image_url = None

        for attribute in [
            {"property": "og:image"},
            {"name": "twitter:image"},
        ]:
            tag = soup.find("meta", attrs=attribute)

            if tag and tag.get("content"):
                image_url = tag["content"].strip()
                break

        if not image_url:
            return None

        if image_url.startswith("//"):
            image_url = "https:" + image_url

        if not image_url.startswith("https://") and not image_url.startswith("http://"):
            return None

        image_response = requests.get(
            image_url,
            headers=HEADERS,
            timeout=15
        )
        image_response.raise_for_status()

        content_type = image_response.headers.get(
            "Content-Type", ""
        ).lower()

        if not content_type.startswith("image/"):
            return None

        if len(image_response.content) > 8 * 1024 * 1024:
            return None

        image = BytesIO(image_response.content)
        image.name = "news.jpg"
        image.seek(0)

        return image

    except Exception as error:
        print(f"تصویر دریافت نشد: {error}")
        return None


def prepare_summary(summary, title):
    """آماده‌سازی خلاصه کوتاه و خوانا"""
    summary = clean(summary)
    title = clean(title)

    if not summary or normalize(summary) == normalize(title):
        return ""

    # حذف جمله‌های خیلی طولانی
    sentences = re.split(r"(?<=[.!؟])\s+", summary)
    summary = " ".join(sentences[:3]).strip()

    if len(summary) > 450:
        summary = summary[:447].rsplit(" ", 1)[0] + "..."

    return summary


def make_message(title, summary, source):
    """ساخت متن نهایی پیام"""
    title = clean(title)
    summary = prepare_summary(summary, title)

    parts = [f"📰 {title}"]

    if summary:
        parts.append(summary)

    # لینک منبع در متن پیام درج نمی‌شود.
    # شناسه کانال در انتهای پیام قرار می‌گیرد.
    parts.append("@KHABARNEWS6")

    message = "\n\n".join(parts)

    return message[:4000]


async def send_news(app, news):
    """ارسال خبر به کانال"""
    title = news["title"]
    summary = news["summary"]
    link = news["link"]
    source = news["source"]

    message = make_message(title, summary, source)

    media = await asyncio.to_thread(get_media, link)

    try:
        if media:
            await app.bot.send_photo(
                chat_id=CHANNEL,
                photo=media,
                caption=message[:1024]
            )

            # اگر کپشن طولانی‌تر از محدودیت تلگرام باشد،
            # ادامه متن جداگانه فرستاده می‌شود.
            if len(message) > 1024:
                await app.bot.send_message(
                    chat_id=CHANNEL,
                    text=message[1024:].strip()
                )
        else:
            await app.bot.send_message(
                chat_id=CHANNEL,
                text=message
            )

        sent_links.add(link)
        sent_titles.append(title)
        save_history()

        print(f"خبر ارسال شد: {title}")

    except Exception as error:
        print(f"خطا در ارسال خبر: {error}")


async def check_news(app):
    """جمع‌آوری، اولویت‌بندی و ارسال خبرها"""
    all_news = []

    for source, url in RSS_FEEDS.items():
        items = await asyncio.to_thread(
            get_feed,
            source,
            url
        )
        all_news.extend(items)

    # خبرهای جدید و غیرتکراری
    candidates = []

    for news in all_news:
        if is_duplicate(news["link"], news["title"]):
            continue

        candidates.append(news)

    # اولویت با خبرهای مهم‌تر است
    candidates.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    sent_count = 0

    for news in candidates:
        if sent_count >= MAX_NEWS:
            break

        # از خبرهای کم‌اهمیت صرف‌نظر می‌کنیم
        if news["score"] < 1:
            continue

        await send_news(app, news)
        sent_count += 1

        await asyncio.sleep(2)

    print(f"این نوبت {sent_count} خبر ارسال شد.")


async def main():
    if not TOKEN:
        raise RuntimeError(
            "توکن ربات تنظیم نشده است. مقدار TOKEN را در GitHub Secrets بررسی کن."
        )

    load_history()

    app = Application.builder().token(TOKEN).build()

    async with app:
        await app.initialize()
        await app.start()

        try:
            while True:
                await check_news(app)
                await asyncio.sleep(CHECK_TIME)

        finally:
            await app.stop()


if __name__ == "__main__":
    asyncio.run(main())



