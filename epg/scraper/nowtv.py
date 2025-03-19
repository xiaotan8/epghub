import requests
from bs4 import BeautifulSoup
import json
import yaml
from datetime import datetime, timedelta, timezone
from dateutil import tz

# 香港时区
HONGKONG_TZ = tz.gettz('Asia/Hong_Kong')

def load_config(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)

def get_url(channel, date):
    """生成指定频道和日期的EPG请求URL，考虑香港时区"""
    # 将目标日期转换为香港时区的日期
    target_date = date.astimezone(HONGKONG_TZ).date()
    # 当前香港时区的日期
    now_hk = datetime.now(HONGKONG_TZ)
    today_hk = now_hk.replace(hour=0, minute=0, second=0, microsecond=0).date()
    # 计算日期差
    diff = (target_date - today_hk).days
    return f"https://nowplayer.now.com/tvguide/epglist?channelIdList[]={channel['site_id']}&day={diff}"

def get_headers(channel):
    return {
        "Cookie": f"LANG={channel['lang']}; Expires=null; Path=/; Domain=nowplayer.now.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

def parse_time(timestamp):
    """解析时间戳并转换为香港时区的时间感知对象"""
    dt = datetime.fromisoformat(timestamp)
    if dt.tzinfo is None:
        # 假设原始时间为香港时区
        dt = dt.replace(tzinfo=HONGKONG_TZ)
    return dt

def parse_items(content):
    try:
        data = json.loads(content)
        # 检查数据结构，假设有效数据为列表且第一个元素为节目列表
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
            return data[0]
        return []
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"解析JSON失败: {e}")
        return []

def parse_programs(content, site_channel, date):
    programs = []
    items = parse_items(content)
    for item in items:
        try:
            programs.append({
                "title": item["name"],
                "start": parse_time(item['start']),
                "stop": parse_time(item['end']),
                "description": item.get("description", ""),
                "episode": item.get("episode", "")
            })
        except KeyError as e:
            print(f"节目项缺少必要字段 {e}: {item}")
            continue
    return programs

def get_channels(lang):
    url = "https://nowplayer.now.com/channels"
    headers = {
        "Accept": "text/html",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html = response.text
    except requests.RequestException as e:
        print(f"请求频道列表失败: {e}")
        return []
    
    channels = []
    soup = BeautifulSoup(html, "html.parser")
    channel_elements = soup.select(".tv-guide-s-g div.row")  # 更宽松的选择器
    for el in channel_elements:
        try:
            site_id_el = el.select_one(".channel")
            name_el = el.select_one(".thumbnail p")
            if site_id_el and name_el:
                site_id = site_id_el.text.strip().replace("CH", "")
                name = name_el.text.strip()
                channels.append({
                    "lang": lang,
                    "site_id": site_id,
                    "name": name,
                    "programs": [],
                    "last_update": None
                })
        except AttributeError as e:
            print(f"解析频道元素失败: {e}")
            continue
    return channels

def update(channel, scraper_id=None, dt=None):
    """更新指定频道的节目数据，dt为时区感知的datetime对象"""
    if dt is None:
        dt = datetime.now(HONGKONG_TZ)  # 默认使用当前香港时间
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=HONGKONG_TZ)  # 确保有时区信息
    
    channel_id = channel.get('site_id') if scraper_id is None else scraper_id
    lang = channel.get("lang", "tc")
    
    channel["programs"] = []  # 清空旧数据
    
    site_channel = {
        "site_id": channel_id,
        "lang": lang,
    }
    
    try:
        url = get_url(site_channel, dt)
        headers = get_headers(site_channel)
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.text
    except requests.RequestException as e:
        print(f"请求EPG数据失败 {channel_id}: {e}")
        return False
    
    programs = parse_programs(data, site_channel, dt)
    for program in programs:
        # 转换时间为UTC存储
        start_utc = program['start'].astimezone(timezone.utc)
        stop_utc = program['stop'].astimezone(timezone.utc)
        channel["programs"].append({
            "title": program["title"],
            "start": start_utc.isoformat(),
            "stop": stop_utc.isoformat(),
            "source": f"{channel_id}@nowplayer.now.com",
            "description": program["description"],
            "episode": program["episode"],
        })
    
    channel["last_update"] = datetime.now(timezone.utc).isoformat()
    return True
