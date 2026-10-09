from threatintel.scraper.feeds import Feed, load_feeds
from threatintel.scraper.rss import clean_html, parse_feed

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Critical vulnerability &amp; exploit released</title>
      <link>https://example.org/post-1</link>
      <description><![CDATA[<p>A critical <b>bug</b> reported.</p>]]></description>
      <pubDate>Wed, 08 Oct 2025 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Second story</title>
      <link>https://example.org/post-2</link>
      <description>Plain summary</description>
      <pubDate>Wed, 08 Oct 2025 11:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


def test_clean_html():
    assert clean_html("<p>Hello <b>world</b> &amp; friends</p>") == "Hello world & friends"
    assert clean_html(None) == ""


def test_parse_feed_extracts_articles():
    feed = Feed(name="Test Feed", url="https://example.org/rss", tags=["news"])
    articles = parse_feed(RSS, feed, max_items=10)
    assert len(articles) == 2
    first = articles[0]
    assert first.title == "Critical vulnerability & exploit released"
    assert first.source == "Test Feed"
    assert first.link == "https://example.org/post-1"
    assert "critical" in first.summary.lower()
    assert "<b>" not in first.summary


def test_parse_feed_respects_max_items():
    feed = Feed(name="Test Feed", url="https://example.org/rss")
    assert len(parse_feed(RSS, feed, max_items=1)) == 1


def test_article_hash_is_stable():
    feed = Feed(name="Test Feed", url="https://example.org/rss")
    a = parse_feed(RSS, feed)[0]
    b = parse_feed(RSS, feed)[0]
    assert a.article_hash == b.article_hash


def test_load_feeds_catalog():
    feeds = load_feeds()
    assert len(feeds) >= 20
    assert all(f.url.startswith("http") for f in feeds)
