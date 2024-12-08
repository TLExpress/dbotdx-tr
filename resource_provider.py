import asyncio
from station_table import StationTable
from train_table import TrainTable
from train_live import TrainPositionTable
from station_map import StationTrainslator
from train_type import TrainTypeTranslator
from station_live import StationLiveTable
from datetime import datetime, timedelta


class ResourceProvider:
    def __init__(self, requester):
        self._requester = requester
        self.station_table = None
        self.station_table_tomorrow = None
        self.train_table = None
        self.train_table_tomorrow = None
        self.train_live = None
        self.station_id_translator = None
        self.train_type_translator = None
        self.station_live_table = None

    async def fetch_init(self):
        await self.fetch_daily()
        await self.fetch_live()
        return self

    async def fetch_daily(self):
        (
            self.station_table,
            self.station_table_tomorrow,
            self.train_table,
            self.train_table_tomorrow,
            self.station_id_translator,
            self.train_type_translator,
        ) = await asyncio.gather(
                StationTable().fetch(self._requester),
                StationTable(
                    (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                ).fetch(self._requester),
                TrainTable().fetch(self._requester),
                TrainTable(
                    (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                ).fetch(self._requester),
                StationTrainslator().fetch(self._requester),
                TrainTypeTranslator(ailas=True).fetch(self._requester),
        )
        return self

    async def fetch_live(self):
        self.train_live = await TrainPositionTable().fetch(self._requester)
        self.station_live_table = StationLiveTable(
            self.station_table, self.station_table_tomorrow, self.train_live
        )
        return self