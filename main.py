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
from bs4 import BeautifulSoup
from urlparse import urlparse
from PIL import Image
import PIL.ImageOps
import datetime
from datetime import timedelta
from rpc import RPC

plugin = Plugin()
big_list_view = False

def log(x):
    xbmc.log(repr(x))


def get_icon_path(icon_name):
    addon_path = xbmcaddon.Addon().getAddonInfo("path")
    return os.path.join(addon_path, 'resources', 'img', icon_name+".png")

def unescape( str ):
    str = str.replace("&lt;","<")
    str = str.replace("&gt;",">")
    str = str.replace("&quot;","\"")
    str = str.replace("&amp;","&")
    str = str.replace("&nbsp;"," ")
    str = str.replace("&dash;","-")
    str = str.replace("&ndash;","-")
    return str

@plugin.route('/play_channel/<station>')
def play_channel(station):
    streams = plugin.get_storage('streams')
    if station in streams and streams[station]:
        item = {'label': station,
             'path': streams[station],
             'is_playable': True,
             }
        plugin.play_video(item)
    else:
        choose_stream(station)

@plugin.route('/alternative_play/<station>')
def alternative_play(station):
    streams = plugin.get_storage('streams')
    if station in streams and streams[station]:
        xbmc.executebuiltin('XBMC.RunPlugin(%s)' % streams[station])
    else:
        choose_stream(station)

@plugin.route('/choose_stream/<station>')
def choose_stream(station):
    streams = plugin.get_storage('streams')
    d = xbmcgui.Dialog()
    addons_ini = plugin.get_setting('addons.ini')
    data = xbmcvfs.File(addons_ini,'rb').read()
    no_addons_ini = False
    if not data:
        no_addons_ini = True
    lines = data.splitlines()
    addons = {}
    addon = ""
    for line in lines:
        if line.startswith('['):
            addon = line.strip('[] ')
            if addon not in addons:
                addons[addon] = {}
        elif not line.startswith('#'):
            channel_url = line.split('=',1)
            if addon and len(channel_url) == 2:
                addons[addon][channel_url[0]] = channel_url[1].lstrip('@')
    if no_addons_ini:
        guess = "Guess (needs addons.ini)"
    else:
        guess = "Guess"
    addon_labels = [guess, "Browse", "Playlist", "PVR", "Favourites", "Clear"]+sorted(addons)
    addon = d.select("Addon: "+station,addon_labels)
    if addon == -1:
        return
    s = station.lower().replace(' ','')
    sword = s.replace('1','one')
    sword = sword.replace('2','two')
    sword = sword.replace('4','four')
    found_streams = {}
    if addon == 0:
        if no_addons_ini:
            plugin.open_settings()
            return
        for a in sorted(addons):
            for c in sorted(addons[a]):
                n = c.lower().replace(' ','')
                if n:
                    label = "[%s] %s" % (a,c)
                    if (s.startswith(n) or n.startswith(s)):
                        found_streams[label] = addons[a][c]
                    elif (sword.startswith(n) or n.startswith(sword)):
                        found_streams[label] = addons[a][c]

        stream_list = sorted(found_streams)
        if stream_list:
            choice = d.select(station,stream_list)
            if choice == -1:
                return
            streams[station] = found_streams[stream_list[choice]]
            item = {'label': stream_list[choice],
                 'path': streams[station],
                 'is_playable': True,
                 }
            plugin.play_video(item)
            return
    elif addon == 1:
        try:
            response = RPC.addons.get_addons(type="xbmc.addon.video",properties=["name", "thumbnail"])
        except:
            return
        if "addons" not in response:
            return
        found_addons = response["addons"]
        if not found_addons:
            return
        name_ids = sorted([(a['name'],a['addonid']) for a in found_addons])
        names = [x[0] for x in name_ids]
        selected_addon = d.select("Addon: "+station,names)
        if selected_addon == -1:
            return
        id = name_ids[selected_addon][1]
        path = "plugin://%s" % id
        while True:
            try:
                response = RPC.files.get_directory(media="files", directory=path, properties=["thumbnail"])
            except:
                return
            files = response["files"]
            dirs = sorted([[f["label"],f["file"],] for f in files if f["filetype"] == "directory"])
            links = sorted([[f["label"],f["file"]] for f in files if f["filetype"] == "file"])
            labels = ["[COLOR blue]%s[/COLOR]" % a[0] for a in dirs] + ["%s" % a[0] for a in links]
            selected = d.select("Addon: "+station,labels)
            if selected == -1:
                return
            if selected < len(dirs):
                dir = dirs[selected]
                path = dir[1]
            else:
                link = links[selected]
                streams[station] = link[1]
                name = link[0]
                item = {'label': name,
                     'path': streams[station],
                     'is_playable': True,
                     }
                plugin.play_video(item)
                return
    elif addon == 2:
        playlist = d.browse(1, 'Playlist: %s' % station, 'files', '', False, False)
        if not playlist:
            return
        data = xbmcvfs.File(playlist,'rb').read()
        matches = re.findall(r'#EXTINF:.*?,(.*?)\n(.*?)\n',data,flags=(re.DOTALL | re.MULTILINE))
        names = []
        urls =[]
        for name,url in matches:
            names.append(name.strip())
            urls.append(url.strip())
        if names:
            index = d.select("Choose stream: %s" % station,names)
            if index != -1:
                stream = urls[index]
                stream_name = names[index]
                streams[station] = stream
                item = {'label': stream_name,
                     'path': streams[station],
                     'is_playable': True,
                     }
                plugin.play_video(item)
                return
    elif addon == 3:
        index = 0
        urls = []
        channels = {}
        for group in ["radio","tv"]:
            urls = urls + xbmcvfs.listdir("pvr://channels/%s/All channels/" % group)[1]
        for group in ["radio","tv"]:
            groupid = "all%s" % group
            json_query = RPC.PVR.get_channels(channelgroupid=groupid, properties=[ "thumbnail", "channeltype", "hidden", "locked", "channel", "lastplayed", "broadcastnow" ] )
            if "channels" in json_query:
                for channel in json_query["channels"]:
                    channelname = channel["label"]
                    streamUrl = urls[index]
                    index = index + 1
                    url = "pvr://channels/%s/All channels/%s" % (group,streamUrl)
                    channels[channelname] = url
        labels = sorted(channels)
        selected_channel = d.select('PVR: %s' % station,labels)
        if selected_channel == -1:
            return
        stream_name = labels[selected_channel]
        stream = channels[stream_name]
        streams[station] = stream
        item = {'label': stream_name,
             'path': streams[station],
             'is_playable': True,
             }
        plugin.play_video(item)
        return
    elif addon == 4:
        data = xbmcvfs.File('special://profile/favourites.xml','rb').read()
        matches = re.findall(r'<favourite.*?name="(.*?)".*?>(.*?)<',data,flags=(re.DOTALL | re.MULTILINE))
        favourites = {}
        for name,value in matches:
            if value[0:11] == 'PlayMedia("':
                value = value[11:-2]
            elif value[0:10] == 'PlayMedia(':
                value = value[10:-1]
            elif value[0:22] == 'ActivateWindow(10025,"':
                value = value[22:-9]
            elif value[0:21] == 'ActivateWindow(10025,':
                value = value[22:-8]
            else:
                continue
            favourites[name] = re.sub('&quot;','',value)
        names = sorted(favourites)
        fav = d.select('PVR: %s' % station,names)
        if fav == -1:
            return
        stream_name = names[fav]
        stream = favourites[stream_name]
        streams[station] = stream
        item = {'label': stream_name,
             'path': streams[station],
             'is_playable': True,
             }
        plugin.play_video(item)
        return
    elif addon == 5:
        streams[station] = None
        xbmc.executebuiltin("Container.Refresh")
        return
    else:
        addon_id = addon_labels[addon]
        channel_labels = sorted(addons[addon_id])
        channel = d.select("["+addon_id+"] "+station,channel_labels)
        if channel == -1:
            return
        streams[station] = addons[addon_id][channel_labels[channel]]
        item = {'label': channel_labels[channel],
             'path': streams[station],
             'is_playable': True,
             }
        plugin.play_video(item)



@plugin.route('/stations_list/<stations>')
def stations_list(stations):
    streams = plugin.get_storage('streams')
    items = []

    for station in stations.split(','):
        station = station.strip()
        context_items = []
        context_items.append(('[COLOR yellow]Choose Stream[/COLOR]', 'XBMC.RunPlugin(%s)' % (plugin.url_for(choose_stream, station=station))))
        context_items.append(('[COLOR yellow]Alternative Play[/COLOR]', 'XBMC.RunPlugin(%s)' % (plugin.url_for(alternative_play, station=station))))
        if station in streams and streams[station]:
            label = "[COLOR yellow]%s[/COLOR]" % station.strip()
        else:
            label = station.strip()
        items.append(
        {
            'label': label,
            'path': plugin.url_for('play_channel', station=station),
            'thumbnail': 'special://home/addons/plugin.program.fixtures/icon.png',
            'context_menu': context_items,
        })

    return items

@plugin.route('/listing/<url>')
def listing(url):
    global big_list_view
    big_list_view = True
    streams = plugin.get_storage('streams')
    parsed_uri = urlparse(url)
    domain = '{uri.scheme}://{uri.netloc}'.format(uri=parsed_uri)
    timezone = plugin.get_setting('timezone')
    if timezone != "None":
        s = requests.Session()
        r = s.get("http://www.getyourfixtures.com/setCookie.php?offset=%s" % timezone)
        data = s.get(url).content
    else:
        data = requests.get(url).content
    if not data:
        return
    items = []
    matches = data.split('<div class="match')
    images = {}
    for match_div in matches[1:]:
        soup = BeautifulSoup('<div class="match'+match_div)
        sport_div = soup.find(class_=re.compile("sport"))
        sport = "unknown"
        if sport_div:
            sport = sport_div.img["alt"]
            icon = sport_div.img["src"]
            if icon:
                icon = domain+icon
                images[icon] = "special://profile/addon_data/plugin.program.fixtures/icons/%s" % icon.rsplit('/',1)[-1]
                local_icon = images[icon]
            else:
                icon = ''
        match_time = soup.find(class_=re.compile("time"))
        if match_time:
            match_time = unescape(' '.join(match_time.stripped_strings))
            match_time = match_time.replace("script async","script")
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
        playable = False
        if stations:
            stations = stations.stripped_strings
            stations = list(stations)
            for s in stations:
                if s not in streams:
                    streams[s] = ""
                elif streams[s]:
                    playable = True
            stations = ', '.join(stations)

        if match_time:
            if playable:
                colour = "blue"
            else:
                colour = "dimgray"
            if plugin.get_setting('channels') == 'true':
                if '/anySport' in url:
                    label =  "[COLOR %s]%s[/COLOR] %s [COLOR dimgray]%s[/COLOR] %s [COLOR dimgray]%s[/COLOR]" % (colour, match_time, fixture, competition, sport, stations)
                else:
                    label =  "[COLOR %s]%s[/COLOR] %s [COLOR dimgray]%s[/COLOR] %s" % (colour, match_time, fixture, competition, stations )
            else:
                if '/anySport' in url:
                    label =  "[COLOR %s]%s[/COLOR] %s [COLOR dimgray]%s[/COLOR] %s" % (colour, match_time, fixture, competition, sport)
                else:
                    label =  "[COLOR %s]%s[/COLOR] %s [COLOR dimgray]%s[/COLOR]" % (colour, match_time, fixture, competition)

            items.append({
                'label' : label,
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
    global big_list_view
    big_list_view = True
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
        '''
        image = 'http://www.getyourfixtures.com/gfx/disciplines/%s.png' % id
        local_image = 'special://profile/addon_data/plugin.program.fixtures/icons/%s.png' % id
        xbmcvfs.copy(image,local_image)
        png = Image.open(xbmc.translatePath(local_image))
        png.load() # required for png.split()
        background = Image.new("RGB", png.size, (255, 255, 255))
        background.paste(png, mask=png.split()[3]) # 3 is the alpha channel
        background.save(xbmc.translatePath(local_image))
        '''
        items.append(
        {
            'label': name,
            'path': plugin.url_for('listing', url='http://www.getyourfixtures.com/%s/live/%s/%s' % (country,day,id)),
            'thumbnail': get_icon_path(id),
        })
    return items

@plugin.route('/export_mapping')
def export_mapping():
    streams = plugin.get_storage('streams')
    f = xbmcvfs.File('special://profile/addon_data/plugin.program.fixtures/channels.ini','wb')
    for channel in sorted(streams):
        stream = streams[channel]
        s = "%s=%s\n" % (channel,stream)
        f.write(s.encode("utf8"))
    f.close()

@plugin.route('/import_mapping')
def import_mapping():
    streams = plugin.get_storage('streams')
    f = xbmcvfs.File('special://profile/addon_data/plugin.program.fixtures/channels.ini','rb')
    lines = f.read().splitlines()
    for line in lines:
        channel_stream = line.split('=',1)
        if len(channel_stream) == 2:
            channel = channel_stream[0]
            stream = channel_stream[1]
            streams[channel] = stream

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
    if big_list_view:
        plugin.set_view_mode(51)