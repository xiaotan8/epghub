import requests
from bs4 import BeautifulSoup
import json
import yaml
from datetime import datetime, timedelta

def load_config(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)

def get_url(channel, date):
    diff = (date - datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)).days + 1
    return f"https://nowplayer.now.com/tvguide/epglist?channelIdList[]={channel['site_id']}&day={diff}"

def get_headers(channel):
    return {
        "Cookie": f"LANG={channel['lang']}; Expires=null; Path=/; Domain=nowplayer.now.com"
    }

def parse_start(item):
    return datetime.fromisoformat(item['start'])

def parse_stop(item):
    return datetime.fromisoformat(item['end'])

def parse_items(content):
    try:
        data = json.loads(content)
        if not isinstance(data, list) or not data:
            return []
        return data[0] if isinstance(data[0], list) else []
    except json.JSONDecodeError:
        return []

def parse_programs(content, site_channel, date):
    programs = []
    items = parse_items(content)
    for item in items:
        programs.append({
            "title": item["name"],
            "start": parse_start(item),
            "stop": parse_stop(item),
            "description": item.get("description", ""),
            "episode": item.get("episode", "")
        })
    return programs

def get_channels(lang):
    url = "https://nowplayer.now.com/channels"
    headers = {"Accept": "text/html"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        html = response.text
    except requests.RequestException as e:
        print(e)
        return []
    
    channels = []
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.select("body > div.container > .tv-guide-s-g > div > div"):
        site_id = el.select_one(".guide-g-play > p.channel")
        name = el.select_one(".thumbnail > a > span.image > p")
        if site_id and name:
            channels.append({
                "lang": lang,
                "site_id": site_id.text.replace("CH", ""),
                "name": name.text
            })
    
    return channels

def update(channel, scraper_id=None, dt=None):
    """更新指定频道的节目数据"""
    if dt is None:
        dt = datetime.today().date()
    
    channel_id = channel['site_id'] if scraper_id is None else scraper_id
    lang = channel.get("lang", "zh_tw")
    
    channel["programs"] = []  # 清空旧数据
    
    site_channel = {
        "site_id": channel_id,
        "lang": lang,
    }
    
    try:
        url = get_url(site_channel, dt)
        headers = get_headers(site_channel)
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.text
    except requests.RequestException as e:
        print(f"Error fetching EPG data for {channel_id}: {e}")
        return False
    
    programs = parse_programs(data, site_channel, dt)
    for program in programs:
        channel["programs"].append({
            "title": program["title"],
            "start": program["start"],
            "stop": program["stop"],
            "source": f"{channel_id}@nowplayer.now.com",
            "description": program["description"],
            "episode": program["episode"],
        })
    
    channel["last_update"] = datetime.now().astimezone()
    return True
