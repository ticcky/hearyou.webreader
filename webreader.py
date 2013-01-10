# encoding: utf8
import threading
import multiprocessing
import Queue
import feedparser
import urllib
import os
import pycurl
import StringIO
import json
import sys
import pygame
import signal
import subprocess

import voice
from commander import Commander
import idnes

from util import strip_accents, debug

class Sayer(object):
    pass


class EposSayer(Sayer):
    def say(self, what):
        os.system("/tmp/epos-2.4.85/src/say '%s'" % what.encode("latin2"))


class GoogleSayer(Sayer):
    _cachedir = "tts_cache"
    _cache_index = os.path.join(_cachedir, "index.json")

    def __init__(self):
        super(GoogleSayer, self).__init__()

        self.cache = {'items': {}}

        try:
            self.load_cache()
        except Exception, e:
            print >> sys.stderr, "Could not load cache: %s" % str(e)

    def load_cache(self):
        with open(self._cache_index, "r") as f_in:
            self.cache = json.loads(f_in.read())

    def save_cache(self):
        with open(self._cache_index, "w") as f_out:
            f_out.write(json.dumps(self.cache))

    def cache_new(self, what):
        ndx = len(self.cache['items'])
        name = strip_accents(what)[:20]

        item = "%d_%s" % (ndx, name,)

        assert not what in self.cache['items']
        self.cache['items'][what] = item

        return item

    def cache_get(self, what):
        return self.cache['items'].get(what, None)

    def say(self, what):
        cache_item = self.cache_get(what)

        if cache_item is None:
            cache_item = self._say_new(what)

        mp3name = self._mk_mp3name(cache_item)

        os.system("mplayer -nojoystick -nolirc -nortc -noautosub -framedrop -noconsolecontrols -nomouseinput -nocache -ni -nobps -af scaletempo -speed 1.5 -msglevel all=-1 '%s'" % mp3name)
        #subprocess.call(["mpg123", mp3name])
        #os.system("mpg123 '%s'" % mp3name)

    def _mk_mp3name(self, item_name):
        return os.path.join(self._cachedir, "%s.mp3" % item_name)

    def _say_new(self, what):
        debug("say: new")
        item_name = self.cache_new(what)

        what = urllib.quote(urllib.unquote(what).encode('utf8'), '')

        url = "http://translate.google.com/translate_tts?tl=cs&q=%s" % what

        c = pycurl.Curl()

        c.setopt(pycurl.URL, url)
        #c.setopt(pycurl.RETEURNTRANSFER, 1)
        c.setopt(pycurl.HEADER, 0)
        c.setopt(pycurl.FOLLOWLOCATION, 1)
        c.setopt(pycurl.ENCODING, "")
        c.setopt(pycurl.USERAGENT, "Mozilla/5.0 (Windows NT 5.1) AppleWebKit/535.2 (KHTML, like Gecko) Chrome/15.0.872.0 Safari/535.2")
        c.setopt(pycurl.CONNECTTIMEOUT, 120)
        c.setopt(pycurl.TIMEOUT, 120)
        c.setopt(pycurl.MAXREDIRS, 10)

        b = StringIO.StringIO()
        c.setopt(pycurl.WRITEFUNCTION, b.write)

        c.perform()

        content = b.getvalue()
        mp3name = self._mk_mp3name(item_name)

        with open(mp3name, "w") as f_out:
            f_out.write(content)

        return item_name


class RSSReader(object):
    def __init__(self, rss_url):
        self.rss_url = rss_url
        self.feed = None

    def retrieve_rss(self):
        self.feed = feedparser.parse(self.rss_url)

    def get_titles(self):
        return [item['title'] for item in self.feed['items']]

    def get_links(self):
        return [item['link'] for item in self.feed['items']]




class Task(multiprocessing.Process):
    def __init__(self, target, args):
        super(Task, self).__init__()
        self.target = target
        self.args = args

    def run(self):
        os.setpgrp()
        self.target(*self.args)


class TaskStack(threading.Thread):
    def __init__(self):
        super(TaskStack, self).__init__()

        self.stack = Queue.Queue()
        self.lock = threading.RLock()
        self.curr_task = None

    def add_task(self, task, args=()):
        print 'new task adding'
        self.stack.put((task, args))
        print 'new task added'

    def empty(self):
        while not self.stack.empty():
            self.stack.get()

    def stop_task(self):
        with self.lock:
            os.killpg(self.curr_task.pid, signal.SIGKILL)

    def run(self):
        while 1:
            with self.lock:
                task, args = self.stack.get()
                self.curr_task = Task(target=task, args=args)
                print 'new task created'
            self.curr_task.start()
            print 'new task running'
            self.curr_task.join()

class MainOperator(threading.Thread):
    def __init__(self, comm, taskstack):
        super(MainOperator, self).__init__()
        self.comm = comm
        self.taskstack = taskstack

    def run(self):
        sayer = GoogleSayer()

        rr = RSSReader(open("data/idnes.rss"))
        rr.retrieve_rss()
        newslist = rr.get_titles()
        newslist_links = rr.get_links()
        curr_news = 0
        news_cnt = len(newslist)

        #self.taskstack.add_task(lambda: sayer.say(u"Ahoj, jsem Dobruše, chceš přečíst nějaké zprávy?"))

        while True:
            cmd = self.comm.pop()
            print 'recvd "%s"' % cmd

            if cmd == "prev_news":
                if curr_news == 0:
                    self.taskstack.add_task(lambda: sayer.say(u"Už seš na začátku."))
                else:
                    curr_news -= 1
                    self.taskstack.add_task(lambda: sayer.say(u"Dobře."))
            if cmd == "next_news":
                if not curr_news < news_cnt:
                    self.taskstack.add_task(lambda: sayer.say(u"Už seš na konci."))
                else:
                    curr_news += 1
                    self.taskstack.add_task(lambda: sayer.say(u"Dobře."))
            elif cmd == "stop":
                print "stopping"
                self.taskstack.empty()
                self.taskstack.stop_task()
            elif cmd == "read":
                msg1 = u"Čtu %d. zprávu" % (curr_news + 1)
                msg2 = newslist[curr_news]
                self.taskstack.add_task(sayer.say, (msg1,))
                self.taskstack.add_task(sayer.say, (msg2,))
            elif cmd == "more":
                txt = idnes.get_text(newslist_links[curr_news])
                for sentence in txt.split("."):
                    self.taskstack.add_task(sayer.say, (sentence + ".",))

            elif cmd == "noentiendo":
                self.taskstack.add_task(sayer.say, (u"Nerozumím?",))


def main():
    sayer = GoogleSayer()
    txt = u"""
    Nemusí vám být osm let, abyste toužili na nějakou tu chvilku ponořit se do svého vlastního světa; do prostředí plného rozmanité fantazie, mírně zkrášlených představ a upravených realit. Jen tak pro radost, pro vlastní potěšení a pro pocit uspokojení. Takovou psychickou léčbou projde čas od času každý, někdo častěji a dokonaleji, jiný zřídka a povrchně. Přestože je v podobném „mini-světě“ většinou vše černobílé a občas i nemastné a neslané, stejně krátká exkurze potěší. Jednu podívanou stejného druhu připravil i režisér Rich Moore v animovaném trháku Raubíř Ralf. Povedlo se mu vytvořit skvělý film – odehrávající se v drobném, ale nesmírně zajímavém a chytře promyšleném světě herních automatů.

Hlavní hrdina Ralf je typický záporák. Na rozdíl od dalších negativních postav však nevykrádá banky ani neplodí nemanželské děti; ke statusu toho špatného mu postačuje jeho každodenní práce. V herním automatu Fix-It Felix (tedy Oprav to, Felixi) vždy s vervou rozbije postavený dům, který po něm musí pracně opravit postavička Felix, ovládaná oním mladým stvořením stojícím před konzolí. Všechny vavříny, medaile a pochvalná gesta tak logicky sbírá právě Felix, což se Ralfovi příliš nelíbí. Proto se vydává na dobrodružnou výpravu do dalších her a v jejich prostředích se snaží získat ocenění a obdivná plácání po ramenou. Během devadesáti čtyř minut se několikrát zdá, že se vysněné odměny dočká – jenže pokaždé mu do toho „něco skočí“. A tak musí bojovat až do úplného konce. Happy end se přesto koná a Ralf se z něj neraduje sám, nýbrž s kamarádkou Vanellope, které tím vlastně také zachránil krk.


Dle výše popsaného příběhu můžete usoudit, jak moc je zvláštní zápletka. Nic extra. Vše ale vynahrazuje excelentní zpracování a zasazení do světa skutečně existujících her. Já osobně nepatřím mezi milovníky konzolí různých druhů (po pravdě řečeno jsem nerozpoznal ani jeden název videohry); přesto mi neunikl nádech nostalgie, s jakou jsou všechny virtuality prezentovány. Důmyslný svět, v rámci něhož mohly postavičky po zavírací době přecházet mezi svými zaměstnáními a prožívat různorodá trápení, vás vskutku ohromí a nenechá přemýšlet nad tím, jestli by se tohle a tamto dalo udělat lépe či jinak.

Nápad a prostředí v Raubíři Ralfovi jednoduše dělají víc než polovinu úspěchu. Diváckou náladu zvednou i hlášky hlavních postav. Jsou absurdní a svým způsobem dětinské – právě proto však vyvolají na tvářích diváků lehký úsměv podkreslený dávkou ironie. Onen úsměv a potěšení vydrží i při sledování product placementových vložek – sušenky Oreo v roli strážců hradu, kakao Nesquik jako hnědé lepkavé jezero nebo dietní coca-cola tvořící v kombinaci s mentoskami explodující sopku. Sice jde o klasickou reklamu; nicméně ta díky vcelku úsměvnému a komickému zakomponování do děje dodává potřebnou šťávu.


Zmínku si neodpustím ani směrem k českému dabingu. Ten domácím tvůrcům víceméně vyšel, z normálu vybočovala pouze Veronika Žilková, která propůjčila svůj hlas dívčí hrdince Vanellope. Jakkoliv vynikající herečkou může Žilková být, rádoby roztomilý hlas v Raubíři Ralfovi spíše působil, jako by jí někdo na boky přilepil husí křídla, držel pistoli u hlavy a nutil ji napodobovat tóny opeřence. Možná jde jen o můj laický dojem – každopádně především laici do kin chodí. Dabing prostě udělal na kontě disneyovského snímku drobnou kaňku. Ve všem ostatním je Raubíř Ralf velmi kvalitní film – a rovněž i nesmírně chytré dílo. Nejedná se totiž o směsici toho „nejdětštějšího“ z širokého okolí, která má přinést nejvyšší tržby a hysterickou hladovost nejmenších diváků. Zápletka a hlavně prostředí snesou měřítka animáku, na nějž rádi přijdou diváci různých věkových kategorií. A takové obveselení se teď před Vánoci hodí všem.
    """
    for sentence in txt.split("."):
        sayer.say(sentence)
    """rr = RSSReader(open("data/idnes.rss"))
    rr.retrieve_rss()
    newslist = rr.get_titles()
    newslist_links = rr.get_links()

    txt = idnes.get_text(newslist_links[1])
    print txt
    exit(0)"""
    # start commander
    comm = Commander("localhost", 12345)
    comm.daemon = True
    comm.start()

    # start task stack
    ts = TaskStack()
    ts.daemon = True
    ts.start()

    mainop = MainOperator(comm, ts)
    mainop.daemon = True
    mainop.start()

    while 1:
        raw_input()





    #sayer = EposSayer()
    sayer = GoogleSayer()

    rr = RSSReader(open("data/idnes.rss"))
    rr.retrieve_rss()
    for i, title in enumerate(rr.get_titles()[:4]):
        sayer.say(u"%d. zpráva:" % (i + 1))
        sayer.say(title)

    sayer.save_cache()



if __name__ == '__main__':
    main()


'''
GET /translate_tts?tl=cs&q=kolob%C4%9B%C5%BEka HTTP/1.1..User-Agent: Mozilla/5.0 (Windows NT 5.1) AppleWebKit/535.2 (KHTML, like Gecko) Chrome/15.0.872.0 Safari/535.2..Host: translate.google.com..Accept: */*..Accept-Encoding: deflate, gzip....
GET /translate_tts?tl=cs&q=kolob%C4%9B%C5%BEka HTTP/1.0..User-Agent: Chrome..Accept: */*..Host: translate.google.com..Connection: Keep-Alive....


'''