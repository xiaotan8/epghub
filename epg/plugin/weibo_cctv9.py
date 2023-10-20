from .__weibo_search import search as weibo_search
from .__weibo_search import headers

from datetime import date, datetime, timedelta
from epg.model import Channel, Program
import re
import requests
import json

keyword = "#每日央视纪录片精选#"

def update_programs(programs: list[Program], programs_new: list[Program]) -> int:
    """
    Update programs with new programs.

    Args:
        programs (list[Program]): The programs to update.
        programs_new (list[Program]): The new programs.

    Returns:
        int: The number of programs updated.
    """
    num_updated_programs = 0
    for program_new in programs_new:
        for program in programs:
            if program_new.start_time - program.start_time < timedelta(minutes=5):
                program.title = program_new.title
                num_updated_programs += 1
                break
    return num_updated_programs

def update(channel: Channel, date: date) -> int:
    '''
    Update programs of a channel.

    Args:
        channel (Channel): The channel to update.
        date (date): The date of programs to update.

    Returns:
        int: The number of programs updated.
    '''
    num_updated_programs = 0
    weibo_list = weibo_search(keyword, 1)
    programs = []
    for weibo in weibo_list:
        created_at = datetime.strptime(weibo["created_at"], "%a %b %d %H:%M:%S %z %Y")
        if created_at.date() == date:
            # 获取微博正文
            text_weibo = weibo['text']
            text_url_suffix = re.findall(r'href="(.*?)"', text_weibo)[-1]
            text_url = 'https://m.weibo.cn' + text_url_suffix
            try:
                r = requests.get(text_url, headers=headers, timeout=5)
            except:
                continue
            render_data = re.findall(r'.*var \$render_data = (.*\}\])\[0\]', r.text, re.S)
            render_data = json.loads(render_data[0])
            text = render_data[0]['status']['text']
            # 获取节目列表文本
            program_list = re.findall(r'(\d\d:\d\d)\s+(.*?)<br />', text)
            # 生成节目列表
            for program in program_list:
                start_time = datetime.strptime(f'{created_at.date()} {program[0]} +08:00', '%Y-%m-%d %H:%M %z')
                title = program[1]
                title = title.replace('  ', ' ')
                programs.append(Program(title, start_time, None, "cctv9@weibo"))
    title_dict = {}
    for program in channel.programs:
        if program.sub_title != '':
            title_dict[program.sub_title] = program.title
    for program_new in programs:
        for program in channel.programs:
            if timedelta(minutes=-5) < program_new.start_time - program.start_time < timedelta(minutes=5) and program_new.title != program.title:
                title_dict[program.title] = program_new.title
        # find today's program and process "第x-y集" if ther is empty sub_title
        # todo
    for program in channel.programs:
        if title_dict.get(program.title):
            if program.sub_title == '':
                program.sub_title = program.title
                program.title = title_dict[program.title]
                program.scraper_id = "cctv9@weibo"
                num_updated_programs += 1
    if num_updated_programs > 0:
        channel.metadata["last_scraper"] += "+weibo_cctv9"
    return num_updated_programs