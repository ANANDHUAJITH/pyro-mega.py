import os
import re
import time
import math
import traceback
import humanize

from mega import Mega
from config import Config, ERROR_TEXT
from megadl import meganzbot as client

mega = Mega()


# ------------------------------- UTILITIES ------------------------------- #

def parse_mega_link(url: str):
    """
    Detect and extract MEGA file/folder details.
    Returns:
        ("folder", folder_id, folder_key)
        ("file", file_id, file_key)
        or None if invalid
    """
    try:
        if "mega.nz/folder/" in url:
            folder_id = url.split("folder/")[1].split("#")[0]
            folder_key = url.split("#")[1]
            return "folder", folder_id, folder_key

        elif "mega.nz/file/" in url:
            file_id = url.split("file/")[1].split("#")[0]
            file_key = url.split("#")[1]
            return "file", file_id, file_key

        # old format
        m = re.match(r'^https?://mega.(co.nz|nz)/#\!(?P<id>[\w-]+)!(?P<key>[\w-]+)$', url)
        if m:
            return "file", m.group("id"), m.group("key")

        return None

    except:
        return None


def humanbytes(size):
    if not size: return "0B"
    return humanize.naturalsize(size, binary=True)


def TimeFormatter(milliseconds: int) -> str:
    try:
        seconds, milliseconds = divmod(int(milliseconds), 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        tmp = (
            (str(days) + "d, ") if days else "" +
            (str(hours) + "h, ") if hours else "" +
            (str(minutes) + "m, ") if minutes else "" +
            (str(seconds) + "s, ") if seconds else "" +
            (str(milliseconds) + "ms, ") if milliseconds else ""
        )
        return tmp[:-2]
    except:
        return "0s"


# ------------------------------- PROGRESS BAR ------------------------------- #

async def progress_for_pyrogram(current, total, ud_type, message, start):
    try:
        now = time.time()
        diff = now - start
        if diff == 0:
            diff = 1e-6

        if round(diff % 10.0) == 0 or current == total:
            percentage = (current * 100 / total)
            speed = current / diff
            eta = int((total - current) / speed) if speed != 0 else 0

            elapsed_time = TimeFormatter(diff * 1000)
            estimated_total_time = TimeFormatter((diff + eta) * 1000)

            progress = "[{0}{1}] {2}%".format(
                ''.join(["█" for i in range(math.floor(percentage / 5))]),
                ''.join(["░" for i in range(20 - math.floor(percentage / 5))]),
                round(percentage, 2)
            )

            text = (
                f"{ud_type}\n\n"
                f"{progress}\n"
                f"{humanbytes(current)} of {humanbytes(total)}\n"
                f"Speed: {humanbytes(speed)}/s\n"
                f"ETA: {estimated_total_time}"
            )

            try:
                await message.edit(text)
            except:
                pass
    except:
        pass


# ------------------------------- MAIN DOWNLOAD ------------------------------- #

async def mega_download(url: str, message):
    """
    Master function to download file or folder from MEGA.
    Returns downloaded file path (file) or folder path (folder)
    """
    parsed = parse_mega_link(url)
    if parsed is None:
        await message.edit("❌ Invalid MEGA link.")
        return None

    link_type, public_id, key = parsed

    try:
        m = mega.login()  # anonymous login: mega.login_anonymous()
    except Exception as e:
        await message.edit(f"❌ Login Error: `{e}`")
        return None

    # ------------------- FILE ------------------- #
    if link_type == "file":
        try:
            file = m.find_public_file(public_id, key)
        except Exception as e:
            await message.edit(f"❌ Failed to fetch file: `{e}`")
            return None

        filename = file.get("name", "file.bin")
        await message.edit(f"📥 Downloading File: **{filename}**")

        try:
            path = m.download(file)
        except Exception as e:
            await message.edit(f"❌ Download failed: `{e}`")
            return None

        return path

    # ------------------- FOLDER ------------------- #
    if link_type == "folder":
        await message.edit("📁 Fetching folder contents...")
        try:
            folder = m.get_public_folder(public_id, key)
        except Exception as e:
            await message.edit(f"❌ Cannot access folder: `{e}`")
            return None

        folder_name = folder.get("name", "MEGA_Folder")
        os.makedirs(folder_name, exist_ok=True)
        await message.edit(f"📁 Folder detected: **{folder_name}**\nDownloading files...")

        downloaded_files = []
        for f in folder["files"]:
            try:
                filepath = m.download(f, dest_path=folder_name)
                downloaded_files.append(filepath)
            except Exception as e:
                print("Error downloading file:", e)

        if not downloaded_files:
            await message.edit("❌ Folder is empty or no files downloaded.")
            return None

        return folder_name


# ------------------------------- LOGGING ------------------------------- #

def check_logs():
    try:
        if Config.LOGS_CHANNEL:
            try:
                client.send_message(Config.LOGS_CHANNEL, "`Mega.nz Bot Started!`")
                return True
            except:
                return False
    except:
        return False


async def send_errors(e):
    try:
        if Config.LOGS_CHANNEL:
            await client.send_message(Config.LOGS_CHANNEL, f"**#ERROR** `{e}`")
        print("ERROR:", e)
    except:
        traceback.print_exc()
