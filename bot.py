import os
import re
import json
import asyncio
import logging
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import feedparser
import requests
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.error import TelegramError


# =========================
# تنظیمات اصلی
# =========================

TOKEN = os.getenv("TOKEN")
CHANNEL = "@KHABARNEWS6"

MAX_NEWS = 2
CHECK_TIME = 300
MAX_HISTORY = 3000

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


# =========================
# سابقه خبرها
# =========================

def load_history():
    try:
        if HISTORY_FILE.exists():
            data = json.loads(
                HISTORY_FILE.read_text(encoding="utf-8")
            )

            if isinstance(data, list):
                return set(data)

    except Exception as error:
        logging.warning("خطا در خواندن سابقه: %s", error)

    return set()


sent_links = load_history()


def save_history():
    try:
        recent = list(sent_links)[-MAX_HISTORY:]

        HISTORY_FILE.write_text(
            json.dumps(
                recent,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

    except Exception as error:
        logging.error("ذخیره سابقه ناموفق بود: %s", error)


def normalize_link(link):
    if not link:
        return ""

    try:
        parsed = urlparse(link.strip())

        # حذف پارامترهای رهگیری برای شناسایی بهتر لینک
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query)
            if not key.lower().startswith("utm_")
            and key.lower() not in ("fbclid", "gclid")
        ]

        return urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            urlencode(query),
            ""
        ))

    except Exception:
        return link.strip()


# =========================
# پاک‌سازی متن
# =========================

def clean(text):
    if not text:
        return ""

    soup = BeautifulSoup(str(text), "html.parser")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# =========================
# دسته‌بندی خبرها
# =========================

def category(title, source):
    text = (title + " " + source).lower()

    sports = [
        "فوتبال", "استقلال", "پرسپولیس",
        "تیم ملی", "ورزش", "جام جهانی",
        "قهرمانی", "لیگ", "والیبال",
        "بسکتبال", "المپیک", "کشتی"
    ]

    economy = [
        "دلار", "طلا", "سکه", "بورس",
        "بنزین", "تورم", "اقتصاد", "قیمت",
        "خودرو", "مسکن", "ارز", "بانک",
        "حقوق", "یارانه", "بازار", "معیشت"
    ]

    technology = [
        "فناوری", "تکنولوژی", "هوش مصنوعی",
        "موبایل", "گوشی", "اینترنت",
        "گوگل", "اپل", "مایکروسافت",
        "ربات", "سایبری", "نرم‌افزار"
    ]

    world = [
        "آمریکا", "ترامپ", "اسرائیل",
        "روسیه", "اوکراین", "چین",
        "غزه", "فلسطین", "اروپا",
        "سازمان ملل", "خاورمیانه"
    ]

    politics = [
        "رئیس جمهور", "رئیس‌جمهور",
        "دولت", "مجلس", "وزیر",
        "انتخابات", "نماینده",
        "سیاست", "مصوبه", "قانون"
    ]

    if any(x in text for x in sports):
        return "⚽ ورزشی"

    if any(x in text for x in economy):
        return "💰 اقتصادی"

    if any(x in text for x in technology):
        return "💻 فناوری"

    if any(x in text for x in world):
        return "🌍 بین‌الملل"

    if any(x in text for x in politics):
        return "🏛 سیاسی"

    return "📰 عمومی"


# =========================
# امتیاز اهمیت خبر
# =========================

def importance(title, summary):
    text = (title + " " + summary).lower()

    score = 0

    very_important = [
        "خبر فوری", "فوری", "حمله", "جنگ",
        "موشک", "انفجار", "زلزله", "سیل",
        "آتش‌سوزی", "کشته", "مصدوم",
        "ترور", "بحران", "هشدار",
        "تعطیلی مدارس", "تعطیلی ادارات"
    ]

    important = [
        "ایران", "رئیس جمهور", "رئیس‌جمهور",
        "رهبر", "دولت", "مجلس", "وزیر",
        "انتخابات", "آمریکا", "ترامپ",
        "اسرائیل", "روسیه", "اوکراین",
        "غزه", "فلسطین", "دلار", "طلا",
        "سکه", "بورس", "بنزین", "تورم",
        "قیمت", "فوتبال", "تیم ملی",
        "استقلال", "پرسپولیس", "جام جهانی",
        "هوش مصنوعی", "یارانه", "حقوق"
    ]

    for word in very_important:
        if word in text:
            score += 3

    for word in important:
        if word in text:
            score += 1

    # خبرهای خیلی کوتاه یا فاقد اطلاعات کافی
    if len(title.strip()) < 12:
        score -= 1

    return score


# =========================
# دریافت فید خبری
# =========================

def get_feed(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        feed = feedparser.parse(response.content)

        return feed

    except Exception as error:
        logging.warning("خطا در دریافت RSS: %s", error)
        return None


# =========================
# دریافت عکس واقعی خبر
# =========================

def get_media(url, item=None):
    try:
        # اول بررسی عکس موجود در RSS
        if item:
            media_content = item.get("media_content", [])

            for media in media_content:
                image_url = media.get("url", "")

                if image_url.startswith("https://") or image_url.startswith("http://"):
                    image = download_image(image_url)

                    if image:
                        return image

            for key in ("media_thumbnail", "links"):
                media_list = item.get(key, [])

                for media in media_list:
                    image_url = media.get("url", "")

                    media_type = media.get("type", "")

                    if (
                        image_url
                        and (
                            media_type.startswith("image/")
                            or key == "media_thumbnail"
                        )
                    ):
                        image = download_image(image_url)

                        if image:
                            return image

            # تصویر درج‌شده در توضیحات RSS
            content = item.get("summary", "")

            soup = BeautifulSoup(
                content,
                "html.parser"
            )

            image_tag = soup.find("img")

            if image_tag and image_tag.get("src"):
                image = download_image(
                    image_tag["src"]
                )

                if image:
                    return image

        # در صورت نبود عکس در RSS، صفحه خبر بررسی شود
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        image_url = ""

        for selector in (
            {"property": "og:image"},
            {"name": "twitter:image"},
        ):
            tag = soup.find("meta", attrs=selector)

            if tag and tag.get("content"):
                image_url = tag["content"].strip()

                if image_url:
                    break

        if image_url:
            if image_url.startswith("//"):
                image_url = "https:" + image_url

            elif image_url.startswith("/"):
                parsed = urlparse(url)

                image_url = (
                    parsed.scheme
                    + "://"
                    + parsed.netloc
                    + image_url
                )

            return download_image(image_url)

    except Exception as error:
        logging.warning("خطای دریافت عکس: %s", error)

    return None


def download_image(image_url):
    try:
        if not image_url.startswith(("http://", "https://")):
            return None

        response = requests.get(
            image_url,
            headers=HEADERS,
            timeout=20,
            stream=True
        )

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type", ""
        ).lower()

        if not content_type.startswith("image/"):
            return None

        data = response.content

        # جلوگیری از دانلود تصاویر بسیار بزرگ
        if len(data) > 10 * 1024 * 1024:
            logging.warning("حجم عکس بیش از حد مجاز است.")
            return None

        image = BytesIO(data)
        image.name = "news.jpg"
        image.seek(0)

        return image

    except Exception as error:
        logging.warning("دانلود عکس ناموفق بود: %s", error)

        return None


# =========================
# ساخت پیام خبر
# =========================

def make_message(item, source):
    title = clean(item.get("title", ""))

    summary = clean(item.get("summary", ""))

    link = item.get("link", "")

    if not summary:
        summary = "برای مطالعه جزئیات بیشتر، خبر کامل را در منبع اصلی بخوانید."

    # خلاصه کوتاه و مناسب تلگرام
    if len(summary) > 350:
        summary = summary[:350].rsplit(" ", 1)[0] + "..."

    # جلوگیری از درج HTML یا لینک‌های طولانی در خلاصه
    text = (
        f"{category(title, source)}\n\n"
        f"📰 {title}\n\n"
        f"{summary}\n\n"
        f"✍️ منبع: {source}\n"
        f"🔗 <a href=\"{link}\">ادامه خبر</a>\n\n"
        f"📢 اخبار بیشتر در خبر نیوز:\n"
        f"@KHABARNEWS6"
    )

    return text


# =========================
# ارسال خبر
# =========================

async def send_news(bot, item, source):
    link = item.get("link", "")

    title = clean(item.get("title", ""))

    if not link or not title:
        return False

    normalized = normalize_link(link)

    if not normalized or normalized in sent_links:
        return False

    text = make_message(item, source)

    image = await asyncio.to_thread(
        get_media,
        link,
        item
    )

    try:
        if image:
            try:
                image.seek(0)

                # کپشن تلگرام محدودیت دارد
                await bot.send_photo(
                    chat_id=CHANNEL,
                    photo=image,
                    caption=text,
                    parse_mode="HTML"
                )

            except TelegramError as error:
                logging.warning(
                    "ارسال عکس ناموفق بود؛ ارسال متن: %s",
                    error
                )

                await bot.send_message(
                    chat_id=CHANNEL,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )

        else:
            await bot.send_message(
                chat_id=CHANNEL,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )

        sent_links.add(normalized)
        save_history()

        logging.info("خبر ارسال شد: %s", title)

        return True

    except Exception as error:
        logging.error("خطای ارسال خبر: %s", error)

        return False


# =========================
# بررسی خبرهای جدید
# =========================

async def check_news(bot):
    while True:
        logging.info("بررسی منابع خبری آغاز شد.")

        candidates = []
        seen_this_cycle = set()

        for source, rss in RSS_FEEDS.items():
            logging.info("بررسی منبع: %s", source)

            feed = await asyncio.to_thread(
                get_feed,
                rss
            )

            if not feed:
                continue

            for item in feed.entries[:10]:
                title = clean(item.get("title", ""))
                link = item.get("link", "")
                summary = clean(item.get("summary", ""))

                if not title or not link:
                    continue

                normalized = normalize_link(link)

                if (
                    not normalized
                    or normalized in sent_links
                    or normalized in seen_this_cycle
                ):
                    continue

                seen_this_cycle.add(normalized)

                score = importance(title, summary)

                # خبرهای دارای امتیاز مثبت در اولویت‌اند
                if score >= 1:
                    candidates.append(
                        (
                            score,
                            source,
                            item
                        )
                    )

        # خبرهای مهم‌تر در اولویت
        candidates.sort(
            key=lambda item: item[0],
            reverse=True
        )

        count = 0

        for score, source, item in candidates:
            if count >= MAX_NEWS:
                break

            success = await send_news(
                bot,
                item,
                source
            )

            if success:
                count += 1
                await asyncio.sleep(3)

        logging.info(
            "پایان نوبت؛ تعداد خبر ارسال‌شده: %s",
            count
        )

        await asyncio.sleep(CHECK_TIME)


# =========================
# اجرای ربات
# =========================

async def main():
    if not TOKEN:
        logging.error(
            "TOKEN پیدا نشد؛ متغیر TOKEN را بررسی کنید."
        )
        return

    bot = Bot(token=TOKEN)

    logging.info("ربات خبر نیوز روشن شد.")
    logging.info("کانال: %s", CHANNEL)
    logging.info("حداکثر خبر در هر نوبت: %s", MAX_NEWS)
    logging.info("فاصله بررسی: %s ثانیه", CHECK_TIME)

    try:
        await bot.initialize()

        # بررسی دسترسی به تلگرام و کانال
        me = await bot.get_me()
        logging.info("ربات متصل شد: @%s", me.username)

        chat = await bot.get_chat(CHANNEL)
        logging.info("کانال شناسایی شد: %s", chat.title)

        await check_news(bot)

    except asyncio.CancelledError:
        raise

    except Exception as error:
        logging.exception("خطای اصلی ربات: %s", error)

    finally:
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())



