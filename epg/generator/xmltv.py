import re
from lxml import etree
from xml.sax.saxutils import escape  # 导入escape函数

# 清理非法字符
def clean_text(text: str) -> str:
    # 移除非打印字符，包括 NULL 字节等
    return re.sub(r'[\x00-\x1f\x7f]', '', text)

def write(filepath: str, channels: list[Channel], info: str = "") -> bool:
    root = etree.Element("tv")
    tree = etree.ElementTree(root)
    tree.docinfo.system_url = "xmltv.dtd"
    root.set("generator-info-name", info)
    last_update_time_list = []
    
    for channel in channels:
        last_update_time_list.append(channel.metadata["last_update"])
        channel_element = etree.SubElement(root, "channel")
        channel_element.set("id", channel.id)
        for name in channel.metadata["name"]:
            display_name = etree.SubElement(channel_element, "display-name")
            display_name.text = escape(name)  # 使用escape来转义

    last_update_time = max(last_update_time_list)
    root.set(
        "date",
        datetime(
            last_update_time.year,
            last_update_time.month,
            last_update_time.day,
            tzinfo=last_update_time.tzinfo,
        ).strftime("%Y%m%d%H%M%S %z"),
    )

    for channel in channels:
        channel.programs.sort(key=lambda x: x.start_time)
        for program in channel.programs:
            program_element = etree.SubElement(root, "programme")
            program_element.set(
                "start", program.start_time.astimezone().strftime("%Y%m%d%H%M%S %z")
            )
            program_element.set(
                "stop", program.end_time.astimezone().strftime("%Y%m%d%H%M%S %z")
            )
            program_element.set("channel", channel.id)
            title = etree.SubElement(program_element, "title")
            title.text = escape(program.title)  # 转义标题
            if program.sub_title != "":
                sub_title = etree.SubElement(program_element, "sub-title")
                sub_title.text = escape(program.sub_title)  # 转义副标题
            if program.desc != "":
                desc = etree.SubElement(program_element, "desc")
                desc.text = escape(clean_text(program.desc))  # 清理并转义描述

    tree.write(filepath, pretty_print=True, xml_declaration=True, encoding="utf-8")
    return True
