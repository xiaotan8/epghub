import requests
import json
import dayjs
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz

# Extend dayjs functionality to handle UTC
dayjs.extend(dayjs.utc)

API_BASE_URL = 'https://nowplayer.now.com/tvguide/epglist'

def parse_start(item):
    return dayjs(item['start'])

def parse_stop(item):
    return dayjs(item['end'])

def parse_items(content):
    data = json.loads(content)
    if not data or not isinstance(data, list):
        return []
    return data[0] if isinstance(data[0], list) else []

def get_url(channel, date):
    diff = (date - dayjs.utc().startOf('d')).days + 1
    return f"{API_BASE_URL}?channelIdList[]={channel['site_id']}&day={diff}"

def get_headers(channel):
    return {
        'Cookie': f"LANG={channel['lang']}; Expires=null; Path=/; Domain=nowplayer.now.com"
    }

def parse_programs(content):
    programs = []
    items = parse_items(content)
    for item in items:
        programs.append({
            'title': item['name'],
            'start': parse_start(item),
            'stop': parse_stop(item)
        })
    return programs

def get_channels(lang):
    url = 'https://nowplayer.now.com/channels'
    response = requests.get(url, headers={'Accept': 'text/html'})
    soup = BeautifulSoup(response.text, 'html.parser')

    channels = []
    for el in soup.select('body > div.container > .tv-guide-s-g > div > div'):
        channel = {
            'lang': lang,
            'site_id': el.select_one('.guide-g-play > p.channel').text.replace('CH', '').strip(),
            'name': el.select_one('.thumbnail > a > span.image > p').text.strip()
        }
        channels.append(channel)
    
    return channels

# Example usage
channel = {'site_id': 'your_channel_site_id', 'lang': 'en'}
date = datetime(2023, 10, 14)  # Replace with your desired date

url = get_url(channel, date)
headers = get_headers(channel)

# Fetch data
response = requests.get(url, headers=headers)
programs = parse_programs(response.text)

print(programs)

# Get channels
channels = get_channels('en')
print(channels)
