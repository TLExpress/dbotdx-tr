import asyncio
from datetime import datetime, timedelta
import logging

import flask
from flask import jsonify, redirect

from tdx_requester import TDXRequester
from update_interval_manager import UpdateIntervalManager
import config

# Configuration
STATION_MAP_PATH = "/v3/Rail/TRA/Station"
STATION_MAP_ARGS = "StationID,StationName,StationClass"
STATION_TABLE_PATH = "/v3/Rail/TRA/DailyStationTimetable/Today"
STATION_TABLE_PATH_DATE = "/v3/Rail/TRA/DailyStationTimetable/TrainDate/"
STATION_TABLE_ARGS = "StationID,Direction,TimeTables"
TRAIN_TABLE_PATH = "/v3/Rail/TRA/DailyTrainTimetable/Today"
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
        self.station_table = None
        self.station_table_date = None
        self.train_table = None
        self.train_live = None
        self.station_id_translator = None
        self.train_type_translator = None

    async def fetch_init(self):
        try:
            (
                self.station_map,
                self.station_table,
                self.station_table_date,
                self.train_table,
                self.train_live,
            ) = await asyncio.gather(
                self.requester.get(f"{STATION_MAP_PATH}?{STATION_MAP_ARGS}",no_relay=True),
                self.requester.get(f"{STATION_TABLE_PATH}?{STATION_TABLE_ARGS}",no_relay=True),
                self.requester.get(
                    f'{STATION_TABLE_PATH_DATE}{(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")}?{STATION_TABLE_ARGS}',
                    no_relay=True
                ),
                self.requester.get(TRAIN_TABLE_PATH,no_relay=True),
                self.requester.get(f"{TRAIN_LIVE_PATH}?{TRAIN_LIVE_ARGS}",no_relay=True),
            )
            logger.info("Initial data fetched successfully")
        except Exception as e:
            logger.error(f"Error fetching initial data: {e}")

    async def fetch_daily(self):
        try:
            self.station_table, self.station_table_date, self.train_table = (
                await asyncio.gather(
                    self.requester.get(f"{STATION_TABLE_PATH}?{STATION_TABLE_ARGS}",no_relay=True),
                    self.requester.get(
                        f'{STATION_TABLE_PATH_DATE}{(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")}?{STATION_TABLE_ARGS}',
                        no_relay=True
                    ),
                    self.requester.get(TRAIN_TABLE_PATH,no_relay=True),
                )
            )
            logger.info("Daily data fetched successfully")
        except Exception as e:
            logger.error(f"Error fetching daily data: {e}")

    async def fetch_live(self):
        try:
            self.train_live = await self.requester.get(
                f"{TRAIN_LIVE_PATH}?{TRAIN_LIVE_ARGS}",
                no_relay=True
            )
            logger.info("Live data fetched successfully")
        except Exception as e:
            logger.error(f"Error fetching live data: {e}")


@app.route(STATION_MAP_PATH)
def station_map():
    args = flask.request.args
    if (
        len(args) == 1
        and args.get("$select") == STATION_MAP_ARGS
        and cache_manager.station_map is not None
    ):
        return jsonify(cache_manager.station_map)
    else:
        return catch_all(f"{STATION_MAP_PATH}?{args.to_dict(flat=False)}")


@app.route(STATION_TABLE_PATH)
def station_table():
    args = flask.request.args
    if (
        len(args) == 1
        and args.get("$select") == STATION_TABLE_ARGS
        and cache_manager.station_table is not None
    ):
        return jsonify(cache_manager.station_table)
    else:
        return catch_all(f"{STATION_TABLE_PATH}?{args.to_dict(flat=False)}")


@app.route(f"{STATION_TABLE_PATH_DATE}<date>")
def station_table_date(date):
    args = flask.request.args
    if (
        len(args) == 1
        and datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")
        == (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        and args.get("$select") == STATION_TABLE_ARGS
        and cache_manager.station_table_date is not None
    ):
        return jsonify(cache_manager.station_table_date)
    else:
        return catch_all(f"{STATION_TABLE_PATH_DATE}{date}?{args.to_dict(flat=False)}")


@app.route(TRAIN_TABLE_PATH)
def train_table():
    if len(flask.request.args) == 0 and cache_manager.train_table is not None:
        return jsonify(cache_manager.train_table)
    else:
        return catch_all(f"{TRAIN_TABLE_PATH}?{flask.request.args.to_dict(flat=False)}")


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
    return redirect(f"https://tdx.transportdata.tw/api/basic/{path}", code=302)


async def main():
    global cache_manager
    update_interval_manager = UpdateIntervalManager()
    cache_manager = CacheManager(TDXRequester(api_root=config.tdx_api_root))
    await cache_manager.fetch_init()
    await update_interval_manager.register_task(
        "fetch_daily",
        seconds=[0],
        minutes=[0],
        hours=[0],
        task_function=cache_manager.fetch_daily,
    )
    await update_interval_manager.register_task(
        "fetch_live", seconds=[0,20,40], task_function=cache_manager.fetch_live
    )
    await asyncio.to_thread(app.run, port=config.tdx_relay_server_port, use_reloader=False)

if __name__ == "__main__":
    asyncio.run(main())
