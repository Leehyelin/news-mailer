"""
daily news mailer
- GeekNews (IT/기술)
- Spring/Baeldung/InfoQ RSS (AI/Java/Spring)
- 한국경제 (경제)
- 네이버 뉴스 랭킹 (시사)
"""

import os
import smtplib
import feedparser
import requests
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
SEND_TO            = os.environ["MAIL_RECVR"]  # 본인한테 발송
TOP_N              = 5  # 섹션별 기사 수

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


# ─────────────────────────────────────────
# 크롤러
# ─────────────────────────────────────────
def fetch_geeknews() -> list[dict]:
    try:
        resp = requests.get("https://news.hada.io", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        items = []
        for item in soup.select("li.topic-item")[:TOP_N]:
            title_el = item.select_one("a.topic-title")
            if not title_el:
                continue
            title = title_el.text.strip()
            link  = "https://news.hada.io" + title_el["href"]
            count_el = item.select_one(".topic-comment-count")
            count = count_el.text.strip() if count_el else ""
            items.append({"title": title, "link": link, "meta": f"댓글 {count}" if count else ""})
        return items
    except Exception as e:
        print(f"GeekNews 실패: {e}")
        return []


def fetch_rss(feed_url: str, keyword_filter: list[str] = None) -> list[dict]:
    try:
        feed  = feedparser.parse(feed_url)
        items = []
        for entry in feed.entries:
            title = entry.get("title", "")
            link  = entry.get("link", "")
            if keyword_filter:
                lower = title.lower()
                if not any(k.lower() in lower for k in keyword_filter):
                    continue
            items.append({"title": title, "link": link, "meta": feed.feed.get("title", "")})
            if len(items) >= TOP_N:
                break
        return items
    except Exception as e:
        print(f"RSS 실패 ({feed_url}): {e}")
        return []


def fetch_tech_rss() -> list[dict]:
    """Spring + Baeldung + InfoQ 합쳐서 TOP_N개"""
    sources = [
        ("https://spring.io/blog.atom",   None),
        ("https://www.baeldung.com/feed",  ["java", "spring", "ai"]),
        ("https://feed.infoq.com",         ["java", "spring", "ai", "llm"]),
    ]
    items = []
    for url, keywords in sources:
        items.extend(fetch_rss(url, keywords))
    # 중복 제거 후 TOP_N
    seen  = set()
    dedup = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            dedup.append(item)
    return dedup[:TOP_N]


def fetch_hankyung() -> list[dict]:
    try:
        resp = requests.get("https://www.hankyung.com/economy", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        items = []
        for el in soup.select("h3.news-tit a, .article-tit a")[:TOP_N * 2]:
            title = el.text.strip()
            href  = el.get("href", "")
            if not title or not href:
                continue
            if not href.startswith("http"):
                href = "https://www.hankyung.com" + href
            items.append({"title": title, "link": href, "meta": "한국경제"})
            if len(items) >= TOP_N:
                break
        return items
    except Exception as e:
        print(f"한국경제 실패: {e}")
        return []


def fetch_naver_news() -> list[dict]:
    try:
        url  = "https://news.naver.com/main/ranking/popularDay.naver"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        items = []
        for el in soup.select(".rankingnews_list .list_title")[:TOP_N]:
            title  = el.text.strip()
            parent = el.find_parent("a")
            link   = parent["href"] if parent else ""
            if not link.startswith("http"):
                link = "https://news.naver.com" + link
            items.append({"title": title, "link": link, "meta": "네이버 뉴스"})
        return items
    except Exception as e:
        print(f"네이버 뉴스 실패: {e}")
        return []


# ─────────────────────────────────────────
# HTML 템플릿
# ─────────────────────────────────────────
def render_section(label: str, badge_color: str, source_name: str, items: list[dict]) -> str:
    if not items:
        return ""

    rows = ""
    for i, item in enumerate(items, 1):
        rows += f"""
        <tr>
          <td style="font-size:12px;color:#999;padding:10px 8px 10px 0;vertical-align:top;width:18px;">{i}</td>
          <td style="padding:10px 0;border-bottom:1px solid #f0f0f0;">
            <a href="{item['link']}" style="font-size:14px;color:#1a1a1a;text-decoration:none;line-height:1.5;">{item['title']}</a>
            <div style="font-size:12px;color:#aaa;margin-top:2px;">{item['meta']}</div>
          </td>
        </tr>"""

    return f"""
    <div style="margin-bottom:28px;">
      <span style="display:inline-block;font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px;margin-bottom:10px;background:{badge_color['bg']};color:{badge_color['text']};">{label}</span>
      <p style="font-size:11px;color:#aaa;text-transform:uppercase;letter-spacing:0.08em;margin:0 0 10px;">{source_name}</p>
      <table style="width:100%;border-collapse:collapse;">{rows}</table>
    </div>
    <hr style="border:none;border-top:1px solid #f0f0f0;margin:0 0 24px;">
    """


def build_html(sections: list) -> str:
    today    = datetime.now().strftime("%Y년 %m월 %d일 (%a) %p %I:%M")
    body     = "".join(sections)
    return f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f7f7f5;font-family:-apple-system,sans-serif;">
  <div style="max-width:620px;margin:24px auto;">
    <div style="background:#1a1a2e;border-radius:12px 12px 0 0;padding:24px 28px;">
      <h1 style="color:#fff;font-size:18px;font-weight:500;margin:0 0 4px;">오늘의 뉴스 브리핑</h1>
      <p style="color:rgba(255,255,255,0.5);font-size:13px;margin:0;">{today}</p>
    </div>
    <div style="background:#fff;border:1px solid #eee;border-top:none;border-radius:0 0 12px 12px;padding:24px 28px;">
      {body}
      <p style="font-size:12px;color:#ccc;text-align:center;margin-top:8px;">매일 오전 8시 자동 발송 · GitHub Actions</p>
    </div>
  </div>
</body>
</html>"""


# ─────────────────────────────────────────
# 메일 발송
# ─────────────────────────────────────────
def send_mail(html: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[뉴스브리핑] {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = SEND_TO
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_USER, SEND_TO, msg.as_string())
    print("메일 발송 완료")


# ─────────────────────────────────────────
# 메인
# ─────────────────────────────────────────
def main():
    print("크롤링 시작...")

    sections = [
        render_section(
            "IT / 기술", {"bg": "#E6F1FB", "text": "#0C447C"},
            "GeekNews 핫픽", fetch_geeknews()
        ),
        render_section(
            "AI / Java / Spring", {"bg": "#EAF3DE", "text": "#27500A"},
            "Spring · Baeldung · InfoQ", fetch_tech_rss()
        ),
        render_section(
            "경제", {"bg": "#FAEEDA", "text": "#633806"},
            "한국경제 핫픽", fetch_hankyung()
        ),
        render_section(
            "시사", {"bg": "#FBEAF0", "text": "#4B1528"},
            "네이버 뉴스 랭킹", fetch_naver_news()
        ),
    ]

    html = build_html(sections)
    send_mail(html)


if __name__ == "__main__":
    main()
