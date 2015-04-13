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

app = Flask(__name__)
limiter = Limiter(app, strategy="moving-window", key_func = lambda :  request.args['user_name'])

def verify_command(key):
    if key == token_key:
        return True
    else:
        return False

@app.errorhandler(429)
def ratelimit_handler(e):
    return "ratelimit exceeded %s" % e.description, 429

@limiter.request_filter
def channel_whitelist():
    return request.args['channel_name'] == "random"

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
            "color": "#F35A00"
        }]
        }
        r = requests.post(config.webhook_url, data=json.dumps(payload))
        return "", 200
    return "User not found", 200

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

    if gifs:
        return unquote(gifs[0])
    else:
        return "No result"

@limiter.limit("1/minute")
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
    payload = {
        "channel": channel,
        "username": "GIF",
        "icon_url": "http://lh4.googleusercontent.com/-v0soe-ievYE/AAAAAAAAAAI/AAAAAAAC9I4/mrS2pJ4axaQ/photo.jpg?sz=48",
        "attachments": [{
            "fallback": username + " gif for:" + text + " " + gif,
            "text": username + ' Gif for: "' + text + '"',
            "image_url": gif
         }]
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
    payload = {
        "channel": channel,
        "username": "Giphy",
        "icon_url": "https://api.giphy.com/img/api_giphy_logo.png",
        "text": username + ' Gif for: "' + text + '"\n' + giph.url,
        }
    r = requests.post(config.webhook_url, data=json.dumps(payload))
    return "", 200

if __name__ == "__main__":
        app.run(debug=True, host='0.0.0.0')
