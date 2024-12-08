import asyncio
from station_table import station_table_t
from train_table import service_table_t
from train_live import service_pos_table_t
from station_map import station_id_translator_t
from train_type import train_types_translator_t
from station_live import station_live_table_t
from datetime import datetime, timedelta


class resource_provider_t:
    def __init__(self, requester):
        self._requester = requester
        self.station_table = None
        self.train_table = None
        self.train_live = None
        self.station_id_translator = None
        self.train_type_translator = None
        self.station_live_table = None

    async def fetch_init(self):
        (
            self.station_table,
            self.station_table_tomorrow,
            self.train_table,
            self.train_live,
            self.station_id_translator,
            self.train_type_translator,
        ) = await asyncio.gather(
            station_table_t(self._requester).fetch(),
            station_table_t(
                self._requester,
                (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            ).fetch(),
            service_table_t(self._requester).fetch(),
            service_pos_table_t(self._requester).fetch(),
            station_id_translator_t(self._requester).fetch(),
            train_types_translator_t(self._requester).fetch(),
        )
        if (
            self.station_table is None
            or self.train_table is None
            or self.train_live is None
            or self.station_id_translator is None
        ):
            raise ValueError("Failed to fetch initial resources")
        self.station_live_table = await station_live_table_t(
            self.station_table, self.station_table_tomorrow, self.train_live
        ).fetch()
        return self

    async def fetch_daily(self):
        self.station_table, self.station_table_tomorrow, self.train_table = (
            await asyncio.gather(
                station_table_t(self._requester).fetch(),
                station_table_t(
                    self._requester,
                    (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                ).fetch(),
                service_table_t(self._requester).fetch(),
            )
        )
        self.station_live_table = await station_live_table_t(
            self._station_table, self.station_table_tomorrow, self.train_live
        ).fetch()
        return self

    async def fetch_live(self):
        self.train_live = await service_pos_table_t(self._requester).fetch()
        self.station_live_table = await station_live_table_t(
            self.station_table, self.station_table_tomorrow, self.train_live
        ).fetch()
        return self