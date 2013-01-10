import sys

from readability.readability import Document
import urllib2
from BeautifulSoup import BeautifulSoup

def get_text(url):
    headers = { 'User-Agent' : 'Mozilla/5.0' }
    req = urllib2.Request(url, None, headers)
    html = urllib2.urlopen(req).read()
    #html = urllib.urlopen(url).read().decode('windows-1250')
    #page = readable_article = Document(html) #.summary()
    #readable_title = Document(html).short_title()


    try:
        txt = BeautifulSoup(html).findAll(attrs={"class": "opener"})[0].getText()
        txt += " " + BeautifulSoup(html).findAll(id="art-text")[0].getText()
    except:
        txt = None

    return txt
"""
    print txt

    exit(0)
    page = ''.join(BeautifulSoup(page).findAll(text=True))

    import re
    expr = re.compile("&[^ ]{1,10};")
    page = expr.sub("", page)
    page = re.compile("  ").sub(" ", page)
    page = page.replace("\t", " ")
    page = page.replace("\n", " ")
    return page.encode('utf8', errors='ignore')
"""
