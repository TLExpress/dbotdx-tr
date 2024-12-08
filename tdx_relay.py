from datetime import datetime, timedelta
import logging

from quart import jsonify, redirect
import quart

from tdx_requester import TDXRequester
import config

from aiorwlock import RWLock

# Configuration
STATION_MAP_PATH = "/v3/Rail/TRA/Station"
STATION_MAP_ARGS = "StationID,StationName,StationClass"
STATION_TABLE_PATH = "/v3/Rail/TRA/DailyStationTimetable/Today"
STATION_TABLE_PATH_DATE = "/v3/Rail/TRA/DailyStationTimetable/TrainDate/"
STATION_TABLE_ARGS = "StationID,Direction,TimeTables"
TRAIN_TABLE_PATH = "/v3/Rail/TRA/DailyTrainTimetable/Today"
TRAIN_LIVE_PATH = "/v3/Rail/TRA/TrainLiveBoard"
TRAIN_LIVE_ARGS = "TrainNo,TrainTypeID,StationId,DelayTime"

app = quart.Quart(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

station_map = None
station_table = None
station_table_date = None
train_table = None
train_live = None

# Initialize RWLocks
station_map_lock = RWLock()
station_table_lock = RWLock()
station_table_date_lock = RWLock()
train_table_lock = RWLock()
train_live_lock = RWLock()

class Cache:
    def __init__(self, data, period : timedelta=None, expiry : datetime=None):
        self.data = data
        if expiry is not None:
            self.expiry = expiry
        elif period is not None:
            self.expiry = datetime.now() + period
        else:
            self.expiry = None

    def expired(self):
        return False if self.expiry is None else datetime.now() > self.expiry

@app.route(STATION_MAP_PATH)
async def get_station_map():
    global station_map
    args = quart.request.args
    logger.info(f"Request received for station map with args: {args}")
    async with station_map_lock.reader_lock:
        if (
            len(args) == 1
            and args.get("$select") == STATION_MAP_ARGS
        ):
            if (station_map is not None and
                not station_map.expired()):
                logger.info("Cache hit for station map")
                return jsonify(station_map.data)
    async with station_map_lock.writer_lock:
        logger.info("Cache miss for station map")
        station_map = Cache(
            await requester.get(f"{STATION_MAP_PATH}?{STATION_MAP_ARGS}")
        )
        logger.info("Station map data fetched and cached")
        return jsonify(station_map.data)

@app.route(STATION_TABLE_PATH)
async def get_station_table():
    global station_table
    args = quart.request.args
    logger.info(f"Request received for station table with args: {args}")
    async with station_table_lock.reader_lock:
        if (
            len(args) == 1
            and args.get("$select") == STATION_TABLE_ARGS
        ):
            if (station_table is not None and
                not station_table.expired()):
                logger.info("Cache hit for station table")
                return jsonify(station_table.data)
    async with station_table_lock.writer_lock:
        logger.info("Cache miss for station table")
        station_table = Cache(
            await requester.get(f"{STATION_TABLE_PATH}?{STATION_TABLE_ARGS}"),
            expiry=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        )
        logger.info("Station table data fetched and cached")
        return jsonify(station_table.data)

@app.route(f"{STATION_TABLE_PATH_DATE}<date>")
async def get_station_table_date(date):
    global station_table_date
    args = quart.request.args
    logger.info(f"Request received for station table date with args: {args} and date: {date}")
    async with station_table_date_lock.reader_lock:
        if (
            len(args) == 1
            and datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")
            == (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            and args.get("$select") == STATION_TABLE_ARGS
        ):
            if (station_table_date is not None and
                not station_table_date.expired()):
                logger.info("Cache hit for station table date")
                return jsonify(station_table_date.data)
    async with station_table_date_lock.writer_lock:
        logger.info("Cache miss for station table date")
        station_table_date = Cache(
            await requester.get(
                f"{STATION_TABLE_PATH_DATE}{date}?{STATION_TABLE_ARGS}"
            ),
            expiry=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        )
        logger.info("Station table date data fetched and cached")
        return jsonify(station_table_date.data)

@app.route(TRAIN_TABLE_PATH)
async def get_train_table():
    global train_table
    logger.info("Request received for train table")
    async with train_table_lock.reader_lock:
        if len(quart.request.args) == 0:
            if train_table is not None and not train_table.expired():
                logger.info("Cache hit for train table")
                return jsonify(train_table.data)
    async with train_table_lock.writer_lock:
        logger.info("Cache miss for train table")
        train_table = Cache(
            await requester.get(TRAIN_TABLE_PATH),
            expiry=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        )
        logger.info("Train table data fetched and cached")
        return jsonify(train_table.data)

@app.route(TRAIN_LIVE_PATH)
async def get_train_live():
    global train_live
    args = quart.request.args
    logger.info(f"Request received for train live with args: {args}")
    async with train_live_lock.reader_lock:
        if (
            len(args) == 1
            and args.get("$select") == TRAIN_LIVE_ARGS
        ):
            if (train_live is not None and
                not train_live.expired()):
                logger.info("Cache hit for train live")
                return jsonify(train_live.data)
    async with train_live_lock.writer_lock:
        logger.info("Cache miss for train live")
        train_live = Cache(
            await requester.get(f"{TRAIN_LIVE_PATH}?{TRAIN_LIVE_ARGS}"),
            expiry=(datetime.now()+timedelta(seconds=20)).replace(second=0, microsecond=0) + timedelta(seconds=40)
        )
        logger.info("Train live data fetched and cached")
        return jsonify(train_live.data)

@app.route("/<path:path>")
def catch_all(path):
    logger.info(f"Redirecting to {config.tdx_api_root}{path}")
    return redirect(f"{config.tdx_api_root}{path}", code=302)

if __name__ == "__main__":
    logger.info("Starting the Quart app")
    global requester
    requester = TDXRequester(api_relay=None)
    app.run(host='0.0.0.0', port=config.tdx_relay_server_port, use_reloader=False)
