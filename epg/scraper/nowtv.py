import requests
from bs4 import BeautifulSoup
import json
import yaml
from datetime import datetime, date, timezone
from dateutil import tz
from typing import Union

# 配置常量
HONGKONG_TZ = tz.gettz('Asia/Hong_Kong')
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
REQUEST_TIMEOUT = 15

def load_config(file_path: str) -> dict:
    """加载YAML配置文件"""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)
    except Exception as e:
        print(f"配置文件加载失败: {e}")
        return {}

def get_url(channel: dict, target_date: Union[date, datetime]) -> str:
    """生成EPG请求URL"""
    # 统一转换为香港时区datetime对象
    if isinstance(target_date, date):
        target_dt = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            tzinfo=HONGKONG_TZ
        )
    else:
        target_dt = target_date.astimezone(HONGKONG_TZ)
    
    # 计算日期差
    now_hk = datetime.now(HONGKONG_TZ)
    today_hk = now_hk.replace(hour=0, minute=0, second=0, microsecond=0)
    day_diff = (target_dt - today_hk).days
    
    return f"https://nowplayer.now.com/tvguide/epglist?channelIdList[]={channel['site_id']}&day={day_diff}"

def get_headers(channel: dict) -> dict:
    """构建请求头"""
    return {
        "Cookie": f"LANG={channel['lang']}; Path=/; Domain=nowplayer.now.com",
        "User-Agent": USER_AGENT,
        "Accept": "application/json"
    }

def parse_timestamp(ts: str) -> datetime:
    """解析时间戳为香港时区时间"""
    dt = datetime.fromisoformat(ts)
    return dt.astimezone(HONGKONG_TZ) if dt.tzinfo else dt.replace(tzinfo=HONGKONG_TZ)

def validate_program_item(item: dict) -> bool:
    """验证节目数据有效性"""
    required_fields = ['name', 'start', 'end']
    return all(field in item for field in required_fields)

def parse_programs(raw_data: str) -> list:
    """解析节目数据"""
    try:
        data = json.loads(raw_data)
        if not isinstance(data, list) or len(data) < 1:
            return []
        return [item for item in data[0] if validate_program_item(item)]
    except (json.JSONDecodeError, IndexError, TypeError) as e:
        print(f"节目解析失败: {e}")
        return []

def get_channels(lang: str = "tc") -> list:
    """获取频道列表"""
    try:
        response = requests.get(
            "https://nowplayer.now.com/channels",
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"频道列表获取失败: {e}")
        return []

    channels = []
    soup = BeautifulSoup(response.text, 'html.parser')
    
    for container in soup.select('.tv-guide-s-g div.row:has(.channel)'):
        try:
            channel_id = container.select_one('.channel').text.strip().replace('CH', '')
            name = container.select_one('.thumbnail p').text.strip()
            channels.append({
                "site_id": channel_id,
                "name": name,
                "lang": lang,
                "programs": [],
                "last_update": None
            })
        except AttributeError as e:
            print(f"频道解析异常: {e}")
            continue
    
    return channels

def convert_to_utc(dt: datetime) -> str:
    """转换为UTC时间字符串"""
    return dt.astimezone(timezone.utc).isoformat()

def update(
    channel: dict,
    scraper_id: str = None,
    dt: Union[date, datetime, None] = None
) -> bool:
    """更新频道节目数据"""
    # 处理日期输入
    if dt is None:
        target_dt = datetime.now(HONGKONG_TZ)
    elif isinstance(dt, date):
        target_dt = datetime(dt.year, dt.month, dt.day, tzinfo=HONGKONG_TZ)
    else:
        target_dt = dt.astimezone(HONGKONG_TZ) if dt.tzinfo else dt.replace(tzinfo=HONGKONG_TZ)
    
    # 准备请求参数
    channel_id = scraper_id or channel.get('site_id')
    lang = channel.get('lang', 'tc')
    channel_config = {
        'site_id': channel_id,
        'lang': lang
    }
    
    try:
        # 获取EPG数据
        response = requests.get(
            url=get_url(channel_config, target_dt),
            headers=get_headers(channel_config),
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"EPG请求失败 [{channel_id}]: {e}")
        return False

    # 解析节目数据
    channel['programs'].clear()
    for item in parse_programs(response.text):
        try:
            start_time = parse_timestamp(item['start'])
            end_time = parse_timestamp(item['end'])
            
            channel['programs'].append({
                'title': item['name'],
                'start': convert_to_utc(start_time),
                'stop': convert_to_utc(end_time),
                'description': item.get('description', ''),
                'episode': item.get('episode', ''),
                'source': f"{channel_id}@nowplayer.now.com"
            })
        except KeyError as e:
            print(f"节目数据异常: 缺失字段 {e}")
            continue
    
    # 更新最后更新时间
    channel['last_update'] = datetime.now(timezone.utc).isoformat()
    return True
