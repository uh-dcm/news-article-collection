import sys
import requests
import feedparser
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode

import database

def clean_url( url ):
    try:
        parsed = urlparse(url)
        qd = parse_qs(parsed.query, keep_blank_values=True)
        filtered = dict( (k, v) for k, v in qd.items() if not k.startswith('utm_'))
        newurl = urlunparse([
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(filtered, doseq=True), # query string
            parsed.fragment
        ])
        return newurl
    except Exception as e:
        print(f"Error cleaning URL {url}: {e}", file=sys.stderr)
        return url

for feed_url in open("data/feeds.txt"):

    feed_url = feed_url.strip()
    try:
        feed = feedparser.parse( feed_url )

        # Feedparser flags non-well-formed XMLs and character encoding errors using the "bozo" bit
        if feed.bozo:
            bozo_exception = feed.bozo_exception
            exception_msg = bozo_exception.getMessage()
            print(f"Error parsing feed ({feed_url}): {exception_msg}", file=sys.stderr)
    except Exception as e:
        print(f"Error with the feedparser library: {e}", file=sys.stderr)
        continue

    for item in feed['items']:
        link = item['link']

        try:
            res = requests.get( link, allow_redirects = False )
        except requests.RequestException as e:
            print(f"Error fetching URL {link}: {e}", file=sys.stderr)
            continue

        ## some services contain a redirection
        if 300 <= res.status_code < 400: ## detect redirections
            link = res.headers['location']

        link = clean_url( link )

        ## check if we already have this URL
        try:
            has_url = database.urls.select().where( database.urls.c.url == link )
            has_url = database.connection.execute( has_url )
        except Exception as e:
            print(f"Error checking URL in database {link}: {e}", file=sys.stderr)
            continue

        if not has_url.fetchone(): ## have not collected item yet
            try:
                new_url = database.urls.insert().values(
                    feed = feed_url,
                    url = link
                )

                print( link )
                database.connection.execute( new_url )
            except Exception as e:
                print(f"Error inserting URL {link} into database: {e}", file=sys.stderr)

    try:
        database.connection.commit()
    except Exception as e:
        print(f"Error committing collection: {e}", file=sys.stderr)