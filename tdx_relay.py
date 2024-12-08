import asyncio
import flask
import logging
import schedule
from datetime import datetime, timedelta
from flask import jsonify, redirect

from tdx_requester import TDXRequester
import config


# Configuration
STATION_MAP_PATH = "/v3/Rail/TRA/Station"
STATION_MAP_ARGS = "StationID,StationName,StationClass"
STATION_TABLE_TODAY_PATH = "/v3/Rail/TRA/DailyStationTimetable/Today"
STATION_TABLE_PATH_DATE = "/v3/Rail/TRA/DailyStationTimetable/TrainDate"
STATION_TABLE_ARGS = "StationID,Direction,TimeTables"
TRAIN_TABLE_TODAY_PATH = "/v3/Rail/TRA/DailyTrainTimetable/Today"
TRAIN_TABLE_PATH_DATE = "/v3/Rail/TRA/DailyTrainTimetable/TrainDate"
TRAIN_LIVE_PATH = "/v3/Rail/TRA/TrainLiveBoard"
TRAIN_LIVE_ARGS = "TrainNo,TrainTypeID,StationId,DelayTime"

app = flask.Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CacheManager:
    def __init__(self, requester: TDXRequester):
        self.requester = requester
        self.station_map = None
        self.station_table_today = None
        self.station_table_tomorrow = None
        self.train_table_today = None
        self.train_live = None

    async def fetch_init(self):
        await asyncio.gather(self.fetch_daily(), self.fetch_live())

    async def fetch_daily(self):
        station_table_tomorrow_path = f"{STATION_TABLE_PATH_DATE}/{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}"
        train_table_tomorrow_path = f"{TRAIN_TABLE_PATH_DATE}/{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}"
        try:
            (
                self.station_map,
                self.station_table_today,
                self.station_table_tomorrow,
                self.train_table_today,
                self.train_table_tomorrow,
            ) = await asyncio.gather(
                self.requester.get(
                    f"{STATION_MAP_PATH}?{STATION_MAP_ARGS}", no_relay=True
                ),
                self.requester.get(
                    f"{STATION_TABLE_TODAY_PATH}?{STATION_TABLE_ARGS}", no_relay=True
                ),
                self.requester.get(
                    f"{station_table_tomorrow_path}?{STATION_TABLE_ARGS}",
                    no_relay=True,
                ),
                self.requester.get(TRAIN_TABLE_TODAY_PATH, no_relay=True),
                self.requester.get(train_table_tomorrow_path,no_relay=True),
                
            )
            logger.debug("Daily data fetched successfully")
        except Exception as e:
            logger.error(f"Error fetching daily data: {e}")            

    async def fetch_live(self):
        try:
            self.train_live = await self.requester.get(
                f"{TRAIN_LIVE_PATH}?{TRAIN_LIVE_ARGS}", no_relay=True
            )
            logger.debug("Live data fetched successfully")
        except Exception as e:
            logger.error(f"Error fetching live data: {e}")


@app.route(STATION_MAP_PATH)
def station_map():
    args = flask.request.args
    if (
        len(args) == 2
        and args["$select"] == STATION_MAP_ARGS
        and '$format' in args and args["$format"] == "JSON"
        and cache_manager.station_map is not None
    ):
        logger.info("Returning station map")
        return jsonify(cache_manager.station_map)
    return catch_all(f"{STATION_MAP_PATH}?{args.to_dict(flat=False)}")


@app.route(STATION_TABLE_TODAY_PATH)
def station_table():
    args = flask.request.args
    if (
        len(args) == 2
        and args["$select"] == STATION_TABLE_ARGS
        and '$format' in args and args["$format"] == "JSON"
        and cache_manager.station_table_today is not None
    ):
        return jsonify(cache_manager.station_table_today)
    else:
        return catch_all(f"{STATION_TABLE_TODAY_PATH}?{args.to_dict(flat=False)}")


@app.route(f"{STATION_TABLE_PATH_DATE}<date>")
def station_table_date(date):
    args = flask.request.args
    if (
        len(args) == 1
        and datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")
        == (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        and args.get("$select") == STATION_TABLE_ARGS
        and cache_manager.station_table_tomorrow is not None
    ):
        return jsonify(cache_manager.station_table_tomorrow)
    else:
        return catch_all(f"{STATION_TABLE_PATH_DATE}{date}?{args.to_dict(flat=False)}")


@app.route(TRAIN_TABLE_TODAY_PATH)
def train_table():
    if (
        len(flask.request.args) == 0 
        and cache_manager.train_table_today is not None
    ):
        return jsonify(cache_manager.train_table_today)
    else:
        return catch_all(f"{TRAIN_TABLE_TODAY_PATH}?{flask.request.args.to_dict(flat=False)}")
    
@app.route(f"{TRAIN_TABLE_PATH_DATE}<date>")
def train_table_date(date):
    args = flask.request.args
    if (
        len(args) == 1
        and datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")
        == (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        and args.get("$select") == STATION_TABLE_ARGS
        and cache_manager.train_table_tomorrow is not None
    ):
        return jsonify(cache_manager.train_table_tomorrow)
    else:
        return catch_all(f"{TRAIN_TABLE_PATH_DATE}{date}?{args.to_dict(flat=False)}")


@app.route(TRAIN_LIVE_PATH)
def train_live():
    args = flask.request.args
    if (
        len(args) == 1
        and args.get("$select") == TRAIN_LIVE_ARGS
        and cache_manager.train_live is not None
    ):
        return jsonify(cache_manager.train_live)
    else:
        return catch_all(f"{TRAIN_LIVE_PATH}?{args.to_dict(flat=False)}")


@app.route("/<path:path>")
def catch_all(path):
    return redirect(f"https://tdx.transportdata.tw/api/basic{path}", code=302)


async def main():
    global cache_manager
    cache_manager = CacheManager(TDXRequester(api_root=config.tdx_api_root))
    await cache_manager.fetch_init()

    def fetch_daily_task():
        asyncio.run(cache_manager.fetch_daily())

    def fetch_live_task():
        asyncio.run(cache_manager.fetch_live())

    # Schedule tasks
    schedule.every().day.at("00:00").do(fetch_daily_task)
    schedule.every(20).seconds.do(fetch_live_task)

    # Run Flask app in a separate thread
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, app.run, None, config.tdx_relay_server_port, False)

    # Keep the scheduler running
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
