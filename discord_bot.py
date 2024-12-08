import discord
from discord.ext import commands
import datetime
from resource_provider import ResourceProvider
from tdx_requester import TDXRequester as tdx_requester
import config
import json
import os
import schedule
import asyncio
import logging

# 設定日誌格式
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
# 設定日誌檔案
logging.getLogger().setLevel(logging.DEBUG)

# TDX setup

# 機器人 Token 與 API 資訊
BOT_TOKEN = config.bot_token

# Discord 機器人設定
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)


class StationMonitor:
    def __init__(
        self,
        interaction: discord.Interaction,
        station_id,
        direction=None,
        count=3,
        channel_id=None,
        message_id=None,
        destination_id=None,
    ):
        self.station_id = station_id
        self.direction = direction
        self.count = count
        self.message_id = message_id
        self.channel_id = channel_id
        self.interaction = interaction
        self.previous_display = None
        self.destination_id = destination_id

    async def start_monitor(self):
        if self.interaction is not None:
            await self.interaction.response.send_message("請稍候...")
            response = await self.interaction.original_response()
            self.message_id = response.id
            self.channel_id = response.channel.id
            schedule.every().minute.at(":00").do(
                lambda: asyncio.create_task(self.update_monitor())
            )
            schedule.every().minute.at(":20").do(
                lambda: asyncio.create_task(self.update_monitor())
            )
            schedule.every().minute.at(":40").do(
                lambda: asyncio.create_task(self.update_monitor())
            )
        
        await self.update_monitor()
        return self

    async def update_monitor(self):
        logging.debug(f"Updating monitor for station {self.station_id}")
        display = ""
        service_lives = resource_provider.station_live_table[self.station_id].sorted(self.direction)
        filtered_service_lives = []
        if self.destination_id is not None:
            for service_live in service_lives:
                service_table = resource_provider.train_table
                service_table_tomorrow = resource_provider.train_table_tomorrow
                if service_live.train_no in service_table:
                    service = service_table[service_live.train_no]
                elif service_live.train_no in service_table_tomorrow:
                    service = resource_provider.train_table_tomorrow[
                        service_live.train_no
                    ]
                else:
                    continue
                if self.destination_id in service:
                    if (
                        service[self.destination_id].stop_seq
                        > service[self.station_id].stop_seq
                    ):
                        filtered_service_lives.append(service_live)
            service_lives = filtered_service_lives
        for service_live in service_lives[: self.count]:
            train_no = service_live.train_no.ljust(7, " ")
            dest = resource_provider.station_id_translator[service_live.dest].ljust(
                4, "　"
            )
            train_type = resource_provider.train_type_translator[
                service_live.train_type
            ].ljust(4, "　")
            scheduled_departure = service_live.scheduled_departure.ljust(8, " ")
            delay_status = (
                "未發車"
                if service_live.delay is None or service_live.departed
                else f"晚{service_live.delay}分" if service_live.delay > 0 else "準點"
            )
            display += f"```{train_no} {dest} {train_type} {scheduled_departure} {delay_status}```"
        if display == self.previous_display:
            return
        title = f"{resource_provider.station_id_translator[self.station_id]}站 "
        title += f"{'' if self.direction is None else '順行 ' if self.direction == 0 else '逆行'}"
        if self.destination_id is not None:
            dest = resource_provider.station_id_translator[self.destination_id]
            title += f" 往{dest}"
        embed = discord.Embed(
            title=title,
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(),
            description=display,
        )
        channel = await bot.fetch_channel(self.channel_id)
        message = await channel.fetch_message(self.message_id)
        await message.edit(embed=embed, content=None)
        logging.info(f"Updated monitor for station {self.station_id}")
        self.previous_display = display


# /station 指令
@bot.tree.command(name="station")
async def station(
    interaction: discord.Interaction,
    station_id: str,
    direction: int = None,
    count: int = 3,
    destination_id: str = None,
):
    try:
        station_id_translator = resource_provider.station_id_translator
        station_id = station_id_translator.id(
            station_id.replace("車站", "").replace("站", "").replace("台", "臺")
        )
        destination_id = (
            station_id_translator.id(
                destination_id.replace("車站", "").replace("站", "").replace("台", "臺")
            )
            if destination_id is not None
            else None
        )
        monitor = StationMonitor(
            interaction, station_id, direction, count, destination_id=destination_id
        )
        await monitor.start_monitor()
        tasks = {}
        tasks["channel_id"] = monitor.channel_id
        tasks["message_id"] = monitor.message_id
        tasks["station_id"] = station_id
        tasks["destination_id"] = destination_id
        tasks["direction"] = direction
        tasks["count"] = count
        if json_data.get("tasks") is None:
            json_data["tasks"] = {}
        if json_data["tasks"].get("station") is None:
            json_data["tasks"]["station"] = {}
        json_data["tasks"]["station"][monitor.message_id] = tasks
        await save_tasks(json_data)

    except Exception as e:
        raise Exception(f"Failed to start monitor: {e}")


async def restore_tasks(data):
    if not os.path.exists("stored_tasks.json"):
        return

    with open("stored_tasks.json", "r", encoding="utf-8") as file:
        try:
            data.update(json.load(file))
            if not data:
                return
        except json.JSONDecodeError:
            return

    tasks = data.get("tasks", {}).get("station", {})
    for task in tasks.values():
        message_id = task["message_id"]
        channel_id = task["channel_id"]
        station_id = task["station_id"]
        if task.get("destination_id") is not None:
            destination_id = task["destination_id"]
        else:
            destination_id = None
        direction = task.get("direction")
        count = task["count"]

        monitor = StationMonitor(
            None,
            station_id,
            direction,
            count,
            channel_id,
            message_id,
            destination_id=destination_id,
        )
        await monitor.start_monitor()


async def save_tasks(data):
    with open("stored_tasks.json", "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


# 啟動機器人
@bot.event
async def on_ready():
    global resource_provider
    resource_provider = await ResourceProvider(tdx_requester()).fetch_init()
    schedule.every().day.at("00:00").do(
        lambda: asyncio.create_task(resource_provider.fetch_daily())
    ).tag("fetch_daily")
    schedule.every().minute.at(":00").do(
        lambda: asyncio.create_task(resource_provider.fetch_live())
    ).tag("fetch_live")
    schedule.every().minute.at(":20").do(
        lambda: asyncio.create_task(resource_provider.fetch_live())
    ).tag("fetch_live")
    schedule.every().minute.at(":40").do(
        lambda: asyncio.create_task(resource_provider.fetch_live())
    ).tag("fetch_live")
    await bot.tree.sync()
    print(f"Logged on as {bot.user} (ID: {bot.user.id})")
    global json_data
    json_data = {}
    await restore_tasks(json_data)
    bot.loop.create_task(schedule_task())

async def schedule_task():
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)  # 每秒檢查一次是否有任務需要執行

bot.run(BOT_TOKEN)
