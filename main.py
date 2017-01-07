from xbmcswift2 import Plugin
import os
import re
import requests
import xbmc,xbmcaddon,xbmcvfs,xbmcgui
import xbmcplugin
import json
import hashlib
import zipfile
import time
import os
#import xml.etree.ElementTree as ET
#from HTMLParser import HTMLParser
from bs4 import BeautifulSoup
from urlparse import urlparse
from PIL import Image
import PIL.ImageOps
import datetime
from datetime import timedelta


plugin = Plugin()

def log(x):
    xbmc.log(repr(x))


def unescape( str ):
    str = str.replace("&lt;","<")
    str = str.replace("&gt;",">")
    str = str.replace("&quot;","\"")
    str = str.replace("&amp;","&")
    str = str.replace("&nbsp;"," ")
    str = str.replace("&dash;","-")
    str = str.replace("&ndash;","-")
    str = str.replace("script async","script")
    return str

@plugin.route('/stations_list/<stations>')
def stations_list(stations):   
    items = []
    
    for station in stations.split(','):
        items.append(
        {
            'label': station.strip(),
            'path': plugin.url_for('stations_list', stations=stations),
            'thumbnail': 'special://home/addons/plugin.program.fixtures/icon.png',
        })

    return items
    
@plugin.route('/listing/<url>')
def listing(url):
    parsed_uri = urlparse(url)
    domain = '{uri.scheme}://{uri.netloc}'.format(uri=parsed_uri)
    data = requests.get(url).content
    if not data:
        return
    items = []
    matches = data.split('<div class="match')
    images = {}
    for match_div in matches[1:]:
        soup = BeautifulSoup('<div class="match'+match_div)
        sport_div = soup.find(class_=re.compile("sport"))
        if sport_div:
            sport = sport_div.img["alt"]
            icon = sport_div.img["src"]
            if icon:
                icon = domain+icon
                images[icon] = "special://profile/addon_data/icons/%s" % icon.rsplit('/',1)[-1]
                local_icon = images[icon]
            else:
                icon = ''
        match_time = soup.find(class_=re.compile("time"))
        if match_time:
            match_time = unescape(' '.join(match_time.stripped_strings))
        else:
            pass
            #log(soup)
        competition = soup.find(class_=re.compile("competition"))
        if competition:
            competition = ' '.join(competition.stripped_strings)
        fixture = soup.find(class_=re.compile("fixture"))
        if fixture:
            fixture = ' '.join(fixture.stripped_strings)
        stations = soup.find(class_=re.compile("stations"))
        if stations:
            stations = ', '.join(stations.stripped_strings)
        if match_time:
            items.append({
                'label' : "%s [COLOR dimgray]%s[/COLOR] %s [COLOR dimgray]%s[/COLOR] %s" % (match_time, sport, fixture, competition, stations),
                'thumbnail': local_icon,
                'path': plugin.url_for('stations_list', stations=stations.encode("utf8"))
            })
    xbmcvfs.mkdirs("special://profile/addon_data/icons/")
    for image in images:
        local_image = images[image]
        if not xbmcvfs.exists(local_image):
            xbmcvfs.copy(image,local_image)
            png = Image.open(xbmc.translatePath(local_image))
            png.load() # required for png.split()
            background = Image.new("RGB", png.size, (255, 255, 255))
            background.paste(png, mask=png.split()[3]) # 3 is the alpha channel
            background.save(xbmc.translatePath(local_image))


    return items
  
@plugin.route('/sports_index/<day>')
def sports_index(day):
    items = []
    
    sports = [
    "any Sport",
    "american football",
    "baseball",
    "basketball",
    "cricket",
    "cycling",
    "football",
    "golf",
    "ice hockey",
    "motorsports",
    "rugby",
    "tennis",
    "other",
    ]
    country = plugin.get_setting('country')
    for sport in sports:
        id = sport.replace(' ','')
        name = sport.title()
        items.append(
        {
            'label': name,
            'path': plugin.url_for('listing', url='http://www.getyourfixtures.com/%s/live/%s/%s' % (country,day,id)),
            'thumbnail': 'special://home/addons/plugin.program.fixtures/icon.png',
        })
    return items  


@plugin.route('/')
def index():
    items = []
    dates = []
    now = datetime.datetime.now()
    for i in range(2,26):
        day = datetime.datetime.now() + timedelta(days=i)
        date = day.strftime("%d-%m-%Y")
        dates.append(date)
    for day in ["Today","Tomorrow"]+dates:
        items.append(
        {
            'label': day,
            'path': plugin.url_for('sports_index', day=day.lower()),
            'thumbnail': 'special://home/addons/plugin.program.fixtures/icon.png',
        })

    return items

if __name__ == '__main__':
    plugin.run()
    plugin.set_view_mode(51)