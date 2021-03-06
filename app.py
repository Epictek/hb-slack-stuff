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
import redis
import random
import os
from flask.ext.sqlalchemy import SQLAlchemy

insults = ("you weeb", "you scrub", "you neckbeard", "you pleb", "you newb", "dani stop fapping please", "nuck broke it", "sucks to be you", "dani pls", "no", "the cake is probably a lie", "STOP IT PLS", "pomf", "you wop")

redis = redis.StrictRedis(host='localhost', port=6379)


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
db = SQLAlchemy(app)
limiter = Limiter(app, strategy="moving-window", storage_uri="redis://localhost:6379",  key_func = lambda :  request.args['user_name'])

def verify_command(key):
    if key == token_key:
        return True
    else:
        return False

lastfm_network = pylast.LastFMNetwork(api_key=config.lastfm_api_key, api_secret=config.lastfm_api_secret)

@app.errorhandler(429)
def ratelimit_handler(e):
    return random.choice(insults) + ", ratelimit exceeded %ss" % e.description, 429

@limiter.request_filter
def channel_whitelist():
    return request.args['channel_name'] == "random"


gif_limit = limiter.shared_limit("1/2 minute", scope="gif")

def resetlimit(user, limit, channel):
    if channel != "random":
        key = "LIMITER/" + request.args['user_name'] + "/" + limit + "/*"
        os.system('redis-cli KEYS ' + key + ' | xargs redis-cli DEL')

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80))
    lastfm = db.Column(db.String(80))
    hummingbird = db.Column(db.String(80))
    def __init__(self, username, lastfm=None, hummingbird=None):
        self.username = username
        self.lastfm = lastfm
        self.hummingbird = hummingbird
    def __repr__(self):
        return '<User %r>' % self.username

@app.route("/lf", methods=['GET'])
def lf():
    if request.args['text'] == "":
        return "please enter a valid user"
    user = User.query.filter_by(username=request.args['user_name']).first()
    if user == None:
        user = User(request.args['user_name'], lastfm=request.args['text'])
        db.session.add(user)
    else:
        user.lastfm = lastfm=request.args['text']
    db.session.commit()
    return "added lastfm user"

@limiter.limit("2/minute")
@app.route("/np", methods=['GET'])
def np():
    username = "@" + request.args['user_name']
    channel = "#" + request.args['channel_name']
    userid = request.args['text']
    if userid == "":
       userid = User.query.filter_by(username=request.args['user_name']).first()
       if userid == None:
           return "", 200
       userid = userid.lastfm
       if userid == None:
           return "", 200
    np = lastfm_network.get_user(userid).get_now_playing()
    if np == None:
        return "No song playing, " + random.choice(insults), 200
    print(np)
#    tracks = client.get('/tracks', q=np.artist.name + " " + np.title)
#    print(tracks)
    payload = {
        "channel": channel,
        "username": "last.fm",
        "icon_url": "https://a.pomf.se/lxwffj.png",
        "text": username + ": <http://last.fm/user/" + userid + "|" +  userid + "> is currently listening to " + np.artist.name + " - " + np.title + "\n" ,
         "unfurl_links": False
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
        "icon_url": "http://a.pomf.hummingbird.moe/bnzlnp.png",
        "attachments": [{
                "thumb_url": "http://a.ppy.sh/" + osu['user_id'] + "_1.png",
                "fallback": username + " Osu! stats for:" + osu['username'] + "\n Accuracy:" + osu['accuracy'] + " Rank: " + osu['pp_rank'] + " PP:" + osu['pp_raw'] + " Plays:" +osu['playcount'],
                "text": username + " Osu! stats for: <https://osu.ppy.sh/u/" + osu['username'] + "|" + osu['username'] + "> :" + osu['country'] + ":",
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
    return "User not found you, " + random.choice(insults), 200

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


@limiter.limit("1/2 minute")
@app.route("/ud", methods=['GET'])
def ud():
    username = "@" + request.args['user_name']
    channel = "#" + request.args['channel_name']
    text = request.args['text']
    r = requests.get("http://api.urbandictionary.com/v0/define?page=1&term=" + text)
    body = r.json()
    if body['result_type'] == "no_results":
        return "No definition found, " + random.choice(insults) , 200
    body = body['list'][0]
    payload = {
        "channel": channel,
        "username": "ud",
        "icon_url": "https://pbs.twimg.com/profile_images/1164168434/ud_profile2_normal.jpg",
        "text" : username + " https://www.urbandictionary.com/define.php?term=" + body['word'].replace(" ", "+"),
        "unfurl_links": True
        }
    r = requests.post(config.webhook_url, data=json.dumps(payload))
    return ""

@limiter.limit("2/minute")
@app.route("/hb", methods=['GET'])
def hb():
    username = "@" + request.args['user_name']
    channel = "#" + request.args['channel_name']
    userid = request.args['text']
    r = requests.get("https://hummingbird.me/api/v1/users/" + userid)
    if r.status_code == 404:
        return "User not found, " + random.choice(insults) , 200
    user = r.json()
    time = user['life_spent_on_anime']

    r = requests.get("https://hummingbird.me/user_infos/" + userid)
    if r.status_code == 404:
        return "User not found", 200
    hb = r.json()
    info = hb['user_info']

    payload = {
        "channel": channel,
        "username": "Hummingbird",
        "icon_url": "https://github.com/hummingbird-me/hummingbird/raw/master/public/images/tiny-logo.jpg",
        "text" : username,
        "attachments": [{
                "thumb_url": user['avatar'],
                "fallback": username + " Hummingbird: https://hummingbird.me/" + userid,
                "title":"<https://hummingbird.me/u/" + info['id'] + "|" + info['id'] + ">",
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


@app.route("/hb", methods=['POST'])
def hummingbird():
    username = "@" + request.args['user_name']
    channel = "#" + request.args['channel_name']
    userid = request.args['text']
    r = requests.get("https://hummingbird.me/api/v1/users/" + userid)
    if r.status_code == 404:
        return "User not found, " + random.choice(insults) , 200
    user = r.json()
    time = user['life_spent_on_anime']

    r = requests.get("https://hummingbird.me/user_infos/" + userid)
    if r.status_code == 404:
        return "User not found", 200
    hb = r.json()
    info = hb['user_info']

    payload = {
        "channel": channel,
        "username": "Hummingbird",
        "icon_url": "https://github.com/hummingbird-me/hummingbird/raw/master/public/images/tiny-logo.jpg",
        "text" : username,
        "attachments": [{
                "thumb_url": user['avatar'],
                "fallback": username + " Hummingbird: https://hummingbird.me/" + userid,
                "title":"<https://hummingbird.me/u/" + info['id'] + "|" + info['id'] + ">",
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

def octal_to_html_escape(re_match):
    # an octal escape of the form '\75' (which ought to become '%3d', the
    # url-escaped form of "=". Strip the leading \
    s = re_match.group(0)[1:]

    # convert octal to hex and strip the leading '0x'
    h = hex(int(s, 8))[2:]

    return "%{0}".format(h)

def unescape(url):
    # google uses octal escapes for god knows what reason
    return re.sub(r"\\..", octal_to_html_escape, url)

def getgif(searchterm, unsafe=False):
    searchterm = quote(searchterm)

    safe = "&safe=" if unsafe else "&safe=active"
    searchurl = "https://www.google.com/search?tbs=itp:animated&tbm=isch&q={0}{1}".format(searchterm, safe)

    # this is an old iphone user agent. Seems to make google return good results.
    useragent = "Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_0 like Mac OS X; en-us) AppleWebKit/532.9 (KHTML, like Gecko) Versio  n/4.0.5 Mobile/8A293 Safari/6531.22.7"

    result = requests.get(searchurl, headers={"User-agent": useragent}).text

    gifs = list(map(unescape, re.findall(r"var u='(.*?)'", result)))
    shuffle(gifs)

    if gifs:
        return gifs[0]
    else:
        return ""


def getimg(searchterm, unsafe=False):
    searchterm = quote(searchterm)

    safe = "&safe=" if unsafe else "&safe=active"
    searchurl = "https://www.google.com/search?tbm=isch&q={0}{1}".format(searchterm, safe)

    # this is an old iphone user agent. Seems to make google return good results.
    useragent = "Mozilla/5.0 (iPhone; U; CPU iPhone OS 4_0 like Mac OS X; en-us) AppleWebKit/532.9 (KHTML, like Gecko) Versio  n/4.0.5 Mobile/8A293 Safari/6531.22.7"

    result = requests.get(searchurl, headers={"User-agent": useragent}).text

    images = list(map(unescape, re.findall(r"var u='(.*?)'", result)))
    shuffle(images)

    if images:
        return images[0]
    else:
        return ""

@gif_limit
@app.route("/gif", methods=['GET'])
def gigif():
    unsafe = False
    username = "@" + request.args['user_name']
    channel = "#" + request.args['channel_name']
    if channel in config.nsfw_channels:
        unsafe = True
    text = request.args['text']
    if text == "":
        return "", 200
    gif = getgif(text, unsafe)
    if gif == False:
        resetlimit(request.args['user_name'], "gif", request.args['channel_name'])
        return "No results for " + text  + ", " + random.choice(insults), 200
    payload = {
        "channel": channel,
        "username": "GIF",
        "icon_url": "https://a.pomf.se/ghfazr.jpg",
        "text": username + ' "' + text + '" ' + gif
        }
    r = requests.post(config.webhook_url, data=json.dumps(payload))
    return "", 200

@gif_limit
@app.route("/img", methods=['GET'])
def gimg():
    unsafe = False
    username = "@" + request.args['user_name']
    channel = "#" + request.args['channel_name']
    if channel in config.nsfw_channels:
        unsafe = True
    text = request.args['text']
    if text == "":
        return "", 200
    image = getimg(text, unsafe)
    if image == False:
        resetlimit(request.args['user_name'], "gif", request.args['channel_name'])
        return "No results for " + text  + ", " + random.choice(insults), 200
    payload = {
        "channel": channel,
        "username": "Image",
        "icon_url": "https://a.pomf.se/ghfazr.jpg",
        "text": username + ' "' + text + '" ' + image
        }
    r = requests.post(config.webhook_url, data=json.dumps(payload))
    return "", 200


@gif_limit
@app.route("/giphy", methods=['GET'])
def giphy():
    username = "@" + request.args['user_name']
    channel = "#" + request.args['channel_name']
    text = request.args['text']
    if text == "":
        return "", 200
    giph = translate(text)
    if giph == None:
       resetlimit(request.args['user_name'], "gif", request.args['channel_name'])
       return "no giphy found, " + random.choice(insults) , 200
    payload = {
        "channel": channel,
        "username": "Giphy",
        "icon_url": "https://api.giphy.com/img/api_giphy_logo.png",
        "text": username + ' "' + text + '"\n' + giph.url,
        }
    r = requests.post(config.webhook_url, data=json.dumps(payload))
    return "", 200


def youtube(searchterm):
    url = "https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&key=" + config.gapi + "&q=" + searchterm
    r = requests.get(url)
    r = r.json()
    if r['pageInfo']['totalResults'] == 0:
        return False
    ytid = "https://www.youtube.com/watch?v=" + r['items'][0]['id']['videoId']
    return ytid


@app.route("/yt", methods=['GET'])
def yt():
    username = "@" + request.args['user_name']
    channel = "#" + request.args['channel_name']
    text = request.args['text']

    video = youtube(text)
    if video == False:
#        resetlimit(request.args['user_name'], "gif", request.args['channel_name'])
        return "No results for " + text  + ", " + random.choice(insults), 200

    if text == "":
        return "", 200
    payload = {
        "channel": channel,
        "username": "YouTube",
        "icon_url": "https://upload.wikimedia.org/wikipedia/commons/4/41/YouTube_icon_block.png",
        "text": username + ' "' + text + '" ' + video
        }
    r = requests.post(config.webhook_url, data=json.dumps(payload))
    return "", 200

@limiter.limit("1/60 minute")
@app.route("/lenny", methods=['GET'])
def lenny():
    username = request.args['user_name']
    channel = "#" + request.args['channel_name']
    text = request.args['text']

    url = "https://slack.com/api/users.info?token=" + config.token + "&user=" + request.args['user_id']
    r = requests.get(url)
    r = r.json()
    avatar = r['user']['profile']['image_192']

    payload = {
        "channel": channel,
        "username": username,
        "icon_url": avatar,
        "text": text + " :lenn::lennn:"
        }
    r = requests.post(config.webhook_url, data=json.dumps(payload))
    return "", 200

if __name__ == "__main__":
        app.run(debug=True, host='0.0.0.0')
