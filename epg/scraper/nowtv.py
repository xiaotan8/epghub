import asyncio
import datetime
import json
import re
import httpx
from epg.model import Channel, Program
from . import tz_hong_kong

API_CHANNELS = "https://now-tv.now.com/gw-epg/epg/channelMapping.zh-TW.js"
API_EPG = "https://now-tv.now.com/gw-epg/epg/zh_tw/{date}/prf136/resp-ch/ch_{channel_id}.json"
API_PROGRAM_DETAILS = "https://nowplayer.now.com/tvguide/epgprogramdetail?programId={program_id}"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.79 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest',
    'Accept': 'application/json, text/javascript, */*',
}

async def fetch_json(url):
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()

async def get_channels():
    response = await fetch_json(API_CHANNELS)
    match = re.search(r'var ChannelMapping=(.*)var GenreToChanne', response, re.DOTALL)
    if not match:
        return []
    channels_data = json.loads(match.group(1)[:-2])
    channels = [
        {"site_id": ch_id, "name": data['name'], "id0": ch_id, "lang": "zh"}
        for ch_id, data in channels_data.items() if "name" in data
    ]
    return channels

async def fetch_programs(site_channel, date):
    channel_id = site_channel["id0"]
    url = API_EPG.format(date=date.strftime('%Y%m%d'), channel_id=channel_id)
    try:
        data = await fetch_json(url)
        programs = []
        ch_programs = data['data']['chProgram'].get(channel_id, [])
        
        for item in ch_programs:
            start = datetime.datetime.fromtimestamp(item['start'] / 1000, tz=tz_hong_kong)
            stop = datetime.datetime.fromtimestamp(item['end'] / 1000, tz=tz_hong_kong)
            title = item['name']
            
            # Fetch detailed description
            program_id = item.get('vimProgramId')
            desc = ""
            if program_id:
                details = await fetch_json(API_PROGRAM_DETAILS.format(program_id=program_id))
                desc = details.get('chiSynopsis', '')
            
            programs.append({
                "title": title,
                "description": desc,
                "start": start,
                "stop": stop,
            })
        return programs
    except Exception as e:
        print(f"Error fetching EPG for {site_channel['site_id']}: {e}")
        return []

async def update(channel: Channel, scraper_id: str | None = None, dt: datetime.date = datetime.datetime.today().date()):
    channel_id = channel.id if scraper_id is None else scraper_id
    lang = channel.metadata.get("lang", "zh")
    channel.flush(dt)  # 清空当天节目
    
    site_channel = {"site_id": channel_id, "id0": channel_id, "lang": lang}
    programs = await fetch_programs(site_channel, dt)
    
    for program in programs:
        channel.programs.append(Program(
            program["title"],
            program["start"],
            program["stop"],
            f"{channel_id}@nowtv",
            program["description"]
        ))
    
    channel.metadata.update({"last_update": datetime.datetime.now().astimezone()})
    return True
