# mdr-mcp 📡

mcp-name: io.github.mohammad-abbasi-sh/mdr-mcp

سرور MCP غیررسمی و **فقط‌خواندنی** برای **[MDR](https://www.mdr.de)** — رادیو-تلویزیون آلمان مرکزی (Mitteldeutscher Rundfunk)، رسانهٔ عمومی ایالت‌های زاکسن، زاکسن-آنهالت و تورینگن و عضو ARD — از طریق فیدهای رسمی RSS (فید اصلی MDR Aktuell، یک فید برای هر ایالت، یک فید برای هر بخش و یک فید برای هر شهر) و صفحات مقالات که متن کامل آن‌ها از `articleBody` در JSON-LD از نوع NewsArticle خوانده می‌شود (صفحات MDR یک متن واقعی دارند). تیترهای برتر، اخبار بر اساس ایالت (sachsen، sachsen-anhalt، thueringen)، اخبار بر اساس شهر (leipzig، dresden، chemnitz، magdeburg، halle)، اخبار بر اساس بخش (deutschland، kultur، wissen، sport)، جست‌وجوی کلیدواژه و متن کامل مقالات. بدون کلید، بدون ورود.

> ساختهٔ محمد عباسی در چارچوب «کارخانهٔ MCP آلمان» (خط تولیدی به سبک سپهر). وابسته به MDR یا ARD نیست.

## برای ایجنت‌های هوش مصنوعی

در پیکربندی کلاینت MCP اضافه کنید (stdio):

```json
{
  "mcpServers": {
    "mdr": {
      "command": "uvx",
      "args": ["mdr-mcp==0.1.0"]
    }
  }
}
```

یا اجرای محلی: `python -m mdr_mcp.server` (نیازمند `mcp<2` و `httpx`).

## ابزارها

| ابزار | توضیح |
|------|-------|
| `mdr_headlines` | تیترهای برتر MDR Aktuell (فید رسمی RSS، حدود ۴۵ مورد)، تازه‌ترین اول — `limit` ۱ تا ۱۵۰. هر مورد عنوان، لینک مقاله، تیزر، آدرس تصویر، منطقه (از مسیر لینک) و زمان انتشار دارد |
| `mdr_regional_news` | تازه‌ترین اخبار یک ایالت فدرال، از فید رسمی خودش — `region`: ‏«sachsen»، ‏«sachsen-anhalt» یا «thueringen»، `limit` ۱ تا ۱۵۰ |
| `mdr_local_news` | تازه‌ترین اخبار یک شهر، از فید رسمی خودش — `city`: ‏«leipzig»، ‏«dresden»، ‏«chemnitz» (زاکسن) یا «magdeburg»، «halle» (زاکسن-آنهالت)، `limit` ۱ تا ۱۵۰ |
| `mdr_section_news` | تازه‌ترین اخبار یک بخش، از فید رسمی خودش — `section`: ‏«deutschland»، ‏«kultur»، ‏«wissen» یا «sport»، `limit` ۱ تا ۱۵۰ |
| `mdr_search_news` | جست‌وجوی اخبار با کلیدواژه (عنوان + تیزر) در فید اصلی و همهٔ فیدهای ایالت، بخش و شهر (حدود ۴۷۰ مورد) — `query` (مثلاً «Leipzig»)، `limit` ۱ تا ۱۵۰ |
| `mdr_get_article` | متن کامل یک مقالهٔ MDR (`articleBody` در JSON-LD از نوع NewsArticle، با پاراگراف‌های `<article>` رندرشده در سرور به‌عنوان جایگزین) — `url`: آدرس مقاله در www.mdr.de به شکل /nachrichten/‎<بخش>/‎<slug>‎,‎<id> یا /sport/‎<بخش>/‎<slug>‎,‎<id>. صفحات لایوتیکر `kind: "live-ticker"` برمی‌گردانند (متن، همان متن آغازین است؛ ورودی‌های تیکر در سمت کاربر بارگذاری می‌شوند). لینک‌های هاب و لینک‌های خارجی رد می‌شوند؛ صفحهٔ غیررایگان فقط تیزر را برمی‌گرداند (`paywalled: true`) |
| `mdr_health` | بررسی دسترسی به فید (ok / blocked / error) — یک درخواست مؤدبانه |

نمونهٔ خروجی (`mdr_headlines` با `limit` برابر ۲):

```json
{"feed_title": "MDR Aktuell – Nachrichten für Sachsen, Sachsen-Anhalt und Thüringen", "total_results": 45, "count": 2,
 "items": [
  {"title": "Deutsche Bahn lobt Sicherheitskonzept in Regionalzügen",
   "link": "https://www.mdr.de/nachrichten/deutschland/politik/deutsche-bahn-regio-bodycam-magdeburg-sachsen-anhalt,db-sicherheit-108.html",
   "description": "Die Bahn hat ihr Sicherheitskonzept in Regionalzügen getestet. Dabei wurden Zugbegleiter durch Sicherheitsmitarbeiter verstärkt und Bodycams eingesetzt. ...",
   "published": "2026-11-23T06:03:18+00:00", "region": "deutschland", "category": null,
   "image_url": "https://images.mdr.de/image/0975f5c7-c7fc-4511-ad48-baac0ca44eec/AAABogSUPsA/AAABnSSvrFg/16x9-big/db-bodycam-100.jpg?width=1920"},
  ...]}
```

نکته‌ها:
- سرور **فیدهای رسمی RSS** را می‌خواند (فید اصلی ۴۵ مورد؛ فیدهای ایالت ۵۴/۱۱۶/۱۰۷؛ فیدهای بخش ۱۲۵/۲۰/۱۹/۳۷؛ فیدهای شهر ۶۵/۶۶/۶۵/۴۷/۴۶ — تأیید زنده در ۲۰۲۶-۱۱-۲۳). جست‌وجو روی فیدِ دریافت‌شده انجام می‌شود.
- فیدها **نه `<category>` دارند نه عنصر تصویر**: منطقه از مسیر لینک به دست می‌آید (`/nachrichten/sachsen/...` یعنی «sachsen»؛ لینک‌های `/sport/...` یعنی `null`) و تصویر از تگ `<img>` در `content:encoded` خوانده می‌شود (images.mdr.de، در حدود ۹۵٪ موردها).
- فیدها **موردهای هاب/ناوبری** هم دارند (صفحه‌های بخش مثل `/nachrichten/sachsen/bautzen`، لینک‌های شبکه‌های اجتماعی مثل صفحهٔ فیسبوک MDR Sport) با تاریخ‌های قدیمی (بعضی از ۲۰۲۳). این‌ها خبر نیستند: موردهایی که لینکشان به `.html` ختم نمی‌شود حذف می‌شوند (فید زاکسن ۵۴ ← ۴۹، فید آلمان ۱۲۵ ← ۱۰۴، فید ورزش ۳۷ ← ۳۳، فید لایپزیگ ۶۵ ← ۶۱). چند صفحهٔ موضوعی با پسوند `.html` («Schwerpunkt Carolabrücke»، «Kommentierbare Artikel») هنوز رد می‌شوند — صفحه‌های واقعی mdr.de که فید به آن‌ها لینک داده و همان‌طور که هستند برگردانده می‌شوند.
- **نکتهٔ خبر فوری (Eilmeldung):** موردهای خبر فوری تگ `<title>` خالی دارند؛ عنوان به توضیح برمی‌گردد — همان سطر «+++ ... +++» خودِ فید، نه متن ساخته‌شده.
- **متن مقالات، صادقانه:** صفحات مقالات MDR یک `articleBody` واقعی در JSON-LD دارند (در نمونه ۲۶۶ کلمه برای مقالهٔ خبری و ۳۸۵ کلمه برای لایوتیکر)، پس متن از همان‌جا می‌آید؛ پاراگراف‌های `<article>` رندرشده در سرور فقط جایگزین‌اند (در نمونه ۲۵۹ کلمه، با حذف سطرهای AUDIO و امضا و تبلیغ). صفحات لایوتیکر یک بلوک `LiveBlogPosting` هم دارند: با `kind: "live-ticker"` گزارش می‌شوند — متن، همان متن آغازین است و ورودی‌های تیکر در سمت کاربر بارگذاری می‌شوند و در خروجی نیستند. MDR رسانهٔ عمومی است: نمونه‌ها رایگان‌اند؛ صفحهٔ غیررایگان فقط تیزر را برمی‌گرداند (`paywalled: true`).
- لینک‌های خارجی در موردهای فید (sportschau.de، youtube.com، whatsapp.com) همان‌طور که هستند برگردانده می‌شوند و `mdr_get_article` هرگز آن‌ها را نمی‌خواند.
- فقط ایالت‌ها/بخش‌ها/شهرهای فهرست‌شده فید دارند — politik، wirtschaft، panorama، gesundheit، thueringen/erfurt و thueringen/jena در سایت زنده همه 404 می‌دهند؛ ورزش در `/sport/index-rss.xml` است، نه زیر `/nachrichten/`.
- داده‌ها: فیدهای عمومی RSS و صفحات مقالات MDR — بدون کلید، بدون ورود، فقط‌خواندنی.

## توسعه

```bash
python3 -m venv .venv && .venv/bin/pip install "mcp<2" httpx pytest
.venv/bin/pip install -e .
.venv/bin/python -m pytest tests/ -q
```

- `tests/test_domain.py` — آفلاین؛ فیدهای واقعیِ ذخیره‌شده (اصلی، ایالت، بخش و شهر) و دو صفحهٔ مقالهٔ واقعی را تجزیه می‌کند (یک NewsArticle با متن واقعی JSON-LD، و یک صفحهٔ لایوتیکر با بلوک LiveBlogPosting)
- `tests/test_live.py` — درخواست‌های زندهٔ محتاطانه به www.mdr.de

تست‌ها: ۳۵/۳۵ سبز (۲۸ آفلاین + ۷ زنده، ۲۰۲۶-۱۱-۲۳).

## مجوز

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) — رایگان برای استفادهٔ شخصی و غیرتجاری؛ استفادهٔ تجاری نیازمند مجوز جداگانه است (به LICENSE نگاه کنید).

---

ساختهٔ [محمد عباسی](https://github.com/mohammad-abbasi-sh) — [آلمانی‌باما](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
