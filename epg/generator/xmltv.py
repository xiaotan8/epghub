import re
from lxml import etree
from epg.model import Channel
from datetime import datetime

def clean_text(text: str) -> str:
    """Remove all control characters except for newline and tab. Returns an empty string if input is None."""
    if text is None:
        return ""  # Return an empty string if text is None
    return re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)

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
            display_name.text = name
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
            )  # astimezone() is necessary
            program_element.set(
                "stop", program.end_time.astimezone().strftime("%Y%m%d%H%M%S %z")
            )  # astimezone() is necessary
            program_element.set("channel", channel.id)
            title = etree.SubElement(program_element, "title")
            title.text = program.title
            if program.sub_title != "":
                sub_title = etree.SubElement(program_element, "sub-title")
                sub_title.text = program.sub_title
            if program.desc != "":
                desc = etree.SubElement(program_element, "desc")
                desc.text = clean_text(program.desc)  # Clean description text here
    tree.write(filepath, pretty_print=True, xml_declaration=True, encoding="utf-8")
    return True
