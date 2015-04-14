from flask import Flask, request
import requests
import osu_apy
import decimal
import json
from urllib.parse import quote, unquote
import re
from random import shuffle
from giphypop import translate
from flask_limiter import Limiter
import config
from datetime import datetime, timedelta
import pylast
import soundcloud

client = soundcloud.Client(client_id=config.soundcloud_client_id)

app = Flask(__name__)
limiter = Limiter(app, strategy="moving-window", key_func = lambda :  request.args['user_name'])

def verify_command(key):
    if key == token_key:
        return True
    else:
        return False

lastfm_network = pylast.LastFMNetwork(api_key=config.lastfm_api_key, api_secret=config.lastfm_api_secret)

@app.errorhandler(429)
def ratelimit_handler(e):
    return "ratelimit exceeded %s" % e.description, 429

@limiter.request_filter
def channel_whitelist():
    return request.args['channel_name'] == "random"


@limiter.limit("2/minute")
@app.route("/np", methods=['GET'])
def np():
    username = "@" + request.args['user_name']
    channel = "#" + request.args['channel_name']
    userid = request.args['text']
    if userid == "":
       return "", 200
    np = lastfm_network.get_user(userid).get_now_playing()
    if np == None:
        return "No song playing", 200
    tracks = client.get('/tracks', q=np.artist.name + " " + np.title)
    try:
        url = tracks[0].permalink_url
    except:
        url = ""
    payload = {
        "channel": channel,
        "username": "last.fm",
        "icon_url": "https://a.pomf.se/lxwffj.png",
        "text": username + ": <http://last.fm/user/" + userid + "|" +  userid + "> is currently listening to " + np.artist.name + " - " + np.title + "\n" ,
         "unfurl_links": False
    }
    r = requests.post(config.webhook_url, data=json.dumps(payload))
    payload = {
        "channel": channel,
        "username": "last.fm",
        "icon_url": "https://a.pomf.se/lxwffj.png",
        "text": url,
        "unfurl_links": True
    }
    r = requests.post(config.webhook_url, data=json.dumps(payload))
    return "", 200


@limiter.limit("2/minute")
@app.route("/osu", methods=['GET'])
def osu():
    username = "@" + request.args['user_name']
    channel = "#" + request.args['channel_name']
    userid = request.args['text']
    osu = json.loads(osu_apy.get_user(config.osukey, userid, 0, "", 1).decode('utf8'))
    if osu != []:
        osu = osu[0]
        osu['accuracy'] = '{:.2f}%'.format(float(osu['accuracy']))
        payload = {
        "channel": channel,
        "username": "Osu!",
        "icon_url": "http://a.ppy.sh/" + osu['user_id'] + "_1.png",
        "attachments": [{
                "fallback": username + " Osu! stats for:" + osu['username'] + "\n Accuracy:" + osu['accuracy'] + " Rank: " + osu['pp_rank'] + " PP:" + osu['pp_raw'] + " Plays:" +osu['playcount'],
                "text": username + " Osu! stats for: <https://osu.ppy.sh/u/" + osu['username'] + "|" + osu['username'] + ">:" + osu['country'] + ":",
                "title" : osu['username'],
                "fields": [{
                    "title": "Rank",
                    "value": osu['pp_rank'],
                    "short": True
                }, {
                    "title": "Accuracy",
                    "value": osu['accuracy'],
                    "short": True
                }, {
                    "title": "PP",
                    "value": osu['pp_raw'],
                    "short": True
                }, {
                    "title": "Play count",
                    "value": osu['playcount'],
                    "short": True
                }],
            "color": "#FF66A9"
        }]
        }
        r = requests.post(config.webhook_url, data=json.dumps(payload))
        return "", 200
    return "User not found", 200

intervals = (
    ('years', 525600),
    ('month', 43200),
    ('days', 1440),   
    ('hours', 60),
    ('minutes', 1),
    )

def format_minutes(minutes):
    result = []

    for name, count in intervals:
        value = minutes // count
        if value:
            minutes -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append("{} {}".format(value, name))
    return ', '.join(result)


@limiter.limit("2/minute")
@app.route("/hb", methods=['GET'])
def hb():
    username = "@" + request.args['user_name']
    channel = "#" + request.args['channel_name']
    userid = request.args['text']
    r = requests.get("https://hummingbird.me/user_infos/" + userid)
    if r.status_code == 404:
        return "User not found", 200
    hb = r.json()
    user = hb['users'][0]
    info = hb['user_info']
    avatar = user['avatar_template'].replace("{size}", "thumb")
    time = info['life_spent_on_anime']
    payload = {
        "channel": channel,
        "username": "Hummingbird",
        "icon_url": avatar,
        "text" : username,
        "attachments": [{
                "fallback": username + " Hummingbird: https://hummingbird.me/" + user['id'],
                "title":"<https://hummingbird.me/u/" + user['id'] + "|" + user['id'] + ">",
                "text": user['bio'],
                "fields": [{
                    "title": user['waifu_or_husbando'],
                    "value": user['waifu'],
                    "short": False
                }, {
                    "title": "Life spent on cartoons",
                    "value": format_minutes(time),
                    "short": False
                }, {
                    "title": "Anime Watched",
                    "value": info['anime_watched'],
                    "short": True
                }],
            "color": "#EC8661"
        }]
        }
    r = requests.post(config.webhook_url, data=json.dumps(payload))
    return "", 200

#gif code modified from https://github.com/llimllib/limbo/blob/master/limbo/plugins/gif.py

def getgif(searchterm, unsafe=False):
    searchterm = quote(searchterm)
    safe = "&safe=" if unsafe else "&safe=active"
    searchurl = "https://www.google.com/search?tbs=itp:animated&tbm=isch&q={0}{1}".format(searchterm, safe)

    # this is an old iphone user agent. Seems to make google return good results.
    useragent = "Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_0 like Mac OS X; en-us) AppleWebKit/532.9 (KHTML, like Gecko) Versio  n/4.0.5 Mobile/8A293 Safari/6531.22.7"

    result = requests.get(searchurl, headers={"User-agent": useragent}).text

    gifs = re.findall(r'imgurl.*?(http.*?)\\', result)
    shuffle(gifs)

    if len(gifs) > 1:
        return unquote(gifs[0])
    else:
        return "No result"

@limiter.limit("1/minute")
@app.route("/gif", methods=['GET'])
def gigif():
    unsafe = False
    username = "@" + request.args['user_name']
    if username == "@xnaas":
        return "ey b0ss fuck you man", 200
    channel = "#" + request.args['channel_name']
    if channel in config.nsfw_channels:
        unsafe = True
    text = request.args['text']
    if text == "":
        return "", 200
    gif = getgif(text, unsafe)
    payload = {
        "channel": channel,
        "username": "GIF",
        "icon_url": "https://a.pomf.se/ghfazr.jpg",
        "text": username + ' "' + text + '" ' + gif
        }
    r = requests.post(config.webhook_url, data=json.dumps(payload))
    return "", 200

@limiter.limit("1/minute")
@app.route("/giphy", methods=['GET'])
def giphy():
    username = "@" + request.args['user_name']
    channel = "#" + request.args['channel_name']
    text = request.args['text']
    if text == "":
        return "", 200
    giph = translate(text)
    if giph == None:
       return "no giphy found", 200
    payload = {
        "channel": channel,
        "username": "Giphy",
        "icon_url": "https://api.giphy.com/img/api_giphy_logo.png",
        "text": username + ' "' + text + '"\n' + giph.url,
        }
    r = requests.post(config.webhook_url, data=json.dumps(payload))
    return "", 200

if __name__ == "__main__":
        app.run(debug=True, host='0.0.0.0')
