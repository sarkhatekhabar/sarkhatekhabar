import os
import re
import json
import time
import asyncio
import hashlib
from io import BytesIO
from difflib import SequenceMatcher
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup
from telegram.ext import Application


# =========================
# تنظیمات اصلی
# =========================

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


# =========================
# پاک‌سازی متن
# =========================

def clean(text):
    if not text:
        return ""

    soup = BeautifulSoup(str(text), "html.parser")
    text = soup.get_text(" ", strip=True)

    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize(text):
    text = clean(text).lower()

    replacements = {
        "ي": "ی",
        "ك": "ک",
        "أ": "ا",
        "إ": "ا",
        "ۀ": "ه",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================
# دسته‌بندی خبر
# =========================

def category(title, source):
    text = normalize(title + " " + source)

    sports = [
        "فوتبال", "استقلال", "پرسپولیس",
        "تیم ملی", "ورزش", "جام جهانی",
        "قهرمانی", "لیگ", "والیبال",
        "بسکتبال", "المپیک"
    ]

    economy = [
        "دلار", "طلا", "سکه", "بورس",
        "بنزین", "تورم", "اقتصاد",
        "قیمت", "خودرو", "مسکن", "ارز",
        "حقوق", "بازار"
    ]

    technology = [
        "فناوری", "تکنولوژی", "هوش مصنوعی",
        "موبایل", "گوشی", "اینترنت",
        "گوگل", "اپل", "مایکروسافت",
        "سامسونگ", "ربات", "نرم افزار"
    ]

    world = [
        "آمریکا", "ترامپ", "اسرائیل",
        "روسیه", "اوکراین", "چین",
        "غزه", "فلسطین", "اروپا",
        "سازمان ملل", "خاورمیانه"
    ]

    if any(word in text for word in sports):
        return "ورزشی"

    if any(word in text for word in economy):
        return "اقتصادی"

    if any(word in text for word in technology):
        return "فناوری"

    if any(word in text for word in world):
        return "بین‌الملل"

    return "عمومی"


# =========================
# امتیاز اهمیت خبر
# =========================

def importance(title, summary):
    text = normalize(title + " " + summary)

    score = 0

    very_important = [
        "خبر فوری", "حمله", "جنگ", "موشک",
        "انفجار", "زلزله", "سیل",
        "آتش سوزی", "کشته", "مصدوم",
        "ترور", "بحران", "هشدار",
        "تعطیلی مدارس", "تعطیلی ادارات"
    ]

    important = [
        "ایران", "رئیس جمهور", "رئیس جمهور",
        "رهبر", "دولت", "مجلس", "وزیر",
        "انتخابات", "آمریکا", "ترامپ",
        "اسرائیل", "روسیه", "اوکراین",
        "غزه", "فلسطین", "دلار", "طلا",
        "سکه", "بورس", "بنزین", "تورم",
        "قیمت", "فوتبال", "تیم ملی",
        "استقلال", "پرسپولیس", "جام جهانی",
        "هوش مصنوعی", "اینترنت"
    ]

    for word in very_important:
        if word in text:
            score += 4

    for word in important:
        if word in text:
            score += 1

    # عنوان خبر نسبت به توضیحات اهمیت بیشتری دارد.
    title_normalized = normalize(title)

    for word in very_important:
        if word in title_normalized:
            score += 2

    return score


# =========================
# تاریخچه خبرهای ارسال‌شده
# =========================

def load_history():
    global sent_links, sent_titles

    if not HISTORY_FILE.exists():
        return

    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        sent_links = set(data.get("links", []))
        sent_titles = data.get("titles", [])

        print("تعداد لینک‌های ذخیره‌شده:", len(sent_links))

    except Exception as error:
        print("خطا در خواندن تاریخچه:", error)


def save_history():
    global sent_links, sent_titles

    sent_titles = sent_titles[-MAX_HISTORY:]

    data = {
        "links": list(sent_links)[-MAX_HISTORY:],
        "titles": sent_titles
    }

    temp_file = HISTORY_FILE.with_suffix(".tmp")

    try:
        with temp_file.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False)

        temp_file.replace(HISTORY_FILE)

    except Exception as error:
        print("خطا در ذخیره تاریخچه:", error)


# =========================
# شناسایی خبرهای مشابه
# =========================

def is_duplicate(link, title):
    if link in sent_links:
        return True

    new_title = normalize(title)

    if not new_title:
        return False

    for old_title in sent_titles[-300:]:
        old_normalized = normalize(old_title)

        if not old_normalized:
            continue

        similarity = SequenceMatcher(
            None,
            new_title,
            old_normalized
        ).ratio()

        if similarity >= 0.84:
            return True

    return False


# =========================
# دریافت RSS
# =========================

def get_feed(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        response.raise_for_status()

        feed = feedparser.parse(response.content)

        return feed

    except Exception as error:
        print("خطا در دریافت RSS:", error)
        return None


# =========================
# دریافت تصویر خبر
# =========================

def get_media(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
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

        if not tag:
            tag = soup.find(
                "meta",
                attrs={"name": "twitter:image"}
            )

        if not tag:
            return None

        image_url = tag.get("content", "").strip()

        if not image_url:
            return None

        image_response = requests.get(
            image_url,
            headers=HEADERS,
            timeout=15
        )

        image_response.raise_for_status()

        content_type = image_response.headers.get(
            "Content-Type", ""
        )

        if not content_type.startswith("image/"):
            return None

        if len(image_response.content) > 9 * 1024 * 1024:
            return None

        image = BytesIO(image_response.content)
        image.name = "news.jpg"

        return image

    except Exception as error:
        print("دریافت تصویر ناموفق بود:", error)
        return None


# =========================
# آماده‌سازی خلاصه خبر
# =========================

def prepare_summary(summary):
    summary = clean(summary)

    if not summary:
        return ""

    # حذف بخش‌های رایج تبلیغاتی و اضافی
    summary = re.sub(
        r"(برای مطالعه ادامه خبر کلیک کنید|ادامه مطلب)",
        "",
        summary
    )

    summary = re.sub(r"\s+", " ", summary).strip()

    # خلاصه کوتاه و خوانا
    if len(summary) > 350:
        summary = summary[:350].rsplit(" ", 1)[0] + "..."

    return summary


def make_message(title, summary, source):
    news_category = category(title, source)

    parts = [
        f"📰 {title}"
    ]

    if summary:
        parts.append(summary)

    body = "\n\n".join(parts)

    # منبع در انتهای متن خبری
    body += f"\n\n/{source}"

    # شناسه کانال در انتهای پیام
    body += "\n\n@KHABARNEWS6"

    return body


# =========================
# انتشار خبر
# =========================

async def send_news(app, item, source):
    try:
        link = item.get("link", "").strip()

        title = clean(item.get("title", ""))
        raw_summary = item.get("summary", "")

        summary = prepare_summary(raw_summary)

        if not link or not title:
            return False

        if is_duplicate(link, title):
            print("خبر تکراری کنار گذاشته شد:", title)
            return False

        message = make_message(
            title,
            summary,
            source
        )

        image = await asyncio.to_thread(
            get_media,
            link
        )

        sent = False

        if image:
            try:
                image.seek(0)

                await app.bot.send_photo(
                    chat_id=CHANNEL,
                    photo=image,
                    caption=message[:1024]
                )

                sent = True

            except Exception as error:
                print("ارسال تصویر ناموفق بود:", error)

        if not sent:
            await app.bot.send_message(
                chat_id=CHANNEL,
                text=message[:4096]
            )

        sent_links.add(link)
        sent_titles.append(title)

        save_history()

        print("خبر منتشر شد:", title)

        return True

    except Exception as error:
        print("خطا در ارسال خبر:", error)
        return False


# =========================
# بررسی و انتخاب خبرها
# =========================

async def check_news(app):
    while True:
        try:
            print("\n==============================")
            print("بررسی خبرهای جدید...")
            print("==============================")

            candidates = []

            for source, rss in RSS_FEEDS.items():
                print("بررسی منبع:", source)

                feed = await asyncio.to_thread(
                    get_feed,
                    rss
                )

                if not feed:
                    continue

                for item in feed.entries[:10]:
                    title = clean(item.get("title", ""))
                    summary = clean(item.get("summary", ""))
                    link = item.get("link", "").strip()

                    if not title or not link:
                        continue

                    if is_duplicate(link, title):
                        continue

                    score = importance(title, summary)

                    if score >= 1:
                        candidates.append(
                            (score, source, item)
                        )

            # اولویت با خبرهای مهم‌تر
            candidates.sort(
                key=lambda entry: entry[0],
                reverse=True
            )

            print("تعداد خبرهای منتخب:", len(candidates))

            count = 0
            considered_titles = []

            for score, source, item in candidates:
                if count >= MAX_NEWS:
                    break

                title = clean(item.get("title", ""))
                link = item.get("link", "").strip()

                if not link or is_duplicate(link, title):
                    continue

                # حذف موارد مشابه در همین نوبت
                duplicate_in_batch = False

                for old_title in considered_titles:
                    similarity = SequenceMatcher(
                        None,
                        normalize(title),
                        normalize(old_title)
                    ).ratio()

                    if similarity >= 0.84:
                        duplicate_in_batch = True
                        break

                if duplicate_in_batch:
                    continue

                considered_titles.append(title)

                success = await send_news(
                    app,
                    item,
                    source
                )

                if success:
                    count += 1
                    await asyncio.sleep(3)

            print("تعداد اخبار منتشرشده:", count)
            print("بررسی بعدی ۵ دقیقه دیگر انجام می‌شود.")

        except Exception as error:
            print("خطا در چرخه بررسی خبرها:", error)

        await asyncio.sleep(CHECK_TIME)


# =========================
# اجرای ربات
# =========================

async def main():
    if not TOKEN:
        print("خطا: متغیر TOKEN تنظیم نشده است.")
        return

    load_history()

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

    print("ربات خبر نیوز آماده اجراست.")
    print("کانال:", CHANNEL)
    print("حداکثر خبر در هر نوبت:", MAX_NEWS)
    print("فاصله بررسی:", CHECK_TIME, "ثانیه")

    await app.initialize()
    await app.start()

    try:
        await check_news(app)

    finally:
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
