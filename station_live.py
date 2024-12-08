from station_table import station_table_t
from train_live import service_pos_table_t
import asyncio
from datetime import datetime, timedelta
from aiorwlock import RWLock


def time_delay(original_time: str, delay: int) -> str:
    # 將原始時間轉換為 datetime 對象
    original_time_obj = datetime.strptime(original_time, "%H:%M")
    # 加上延遲時間
    delayed_time_obj = original_time_obj + timedelta(minutes=delay)
    # 格式化回 "HH:MM"
    return delayed_time_obj.strftime("%H:%M")


def time_passed(compare_time: str, day_cross=0) -> bool:
    # 取得目前系統時間，僅保留小時和分鐘
    current_time_obj = datetime.now()

    # 設定換日線為凌晨 3 點
    day_start = current_time_obj.replace(
        hour=day_cross, minute=0, second=0, microsecond=0
    )

    if current_time_obj < day_start:
        day_start -= timedelta(days=1)

    compare_time_obj = datetime.strptime(compare_time, "%H:%M")
    compare_time_obj = compare_time_obj.replace(
        year=current_time_obj.year,
        month=current_time_obj.month,
        day=current_time_obj.day,
    )

    if compare_time_obj < day_start:
        compare_time_obj += timedelta(days=1)

    return current_time_obj >= compare_time_obj


def handle_cross_day_time(compare_time: str) -> datetime:
    current_time_obj = datetime.now()
    day_start = datetime.now().replace(second=0, microsecond=0)

    if current_time_obj <= day_start:
        day_start -= timedelta(days=1)

    compare_time_obj = datetime.strptime(compare_time, "%H:%M")
    compare_time_obj = compare_time_obj.replace(
        year=current_time_obj.year,
        month=current_time_obj.month,
        day=current_time_obj.day,
    )

    if compare_time_obj <= day_start:
        compare_time_obj += timedelta(days=1)

    return compare_time_obj


class service_live_t:
    def __init__(self, service, delay=None):
        self.train_no = service.train_no
        self.train_type = service.train_type
        self.dest = service.dest
        self.scheduled_arrival = service.arrival
        self.scheduled_departure = service.departure
        self.delay = delay
        self.delayed_arrival = time_delay(
            self.scheduled_arrival, 0 if delay is None else delay
        )
        self.delayed_departure = time_delay(
            self.scheduled_departure, 0 if delay is None else delay
        )
        self.departed = (
            False if self.delay is None else time_passed(self.delayed_departure, 3)
        )  # 如果列車還在線上，則以3點為換日線，否則直接以現在時間為換日線

    def __repr__(self):
        return self.train_no


class station_live_t:
    def __init__(self, station_id, station, station_tomorrow, service_pos_table):
        self.station_id = station_id
        self.service_lives = {}
        self.service_lives_sorted = None
        self.directions = {}
        self.directions_sorted = {}
        self.station = station
        self.station_tomorrow = station_tomorrow
        self.service_pos_table = service_pos_table
        self.lock = RWLock()

    async def fetch(self):
        async with self.lock.writer_lock:
            self.service_lives = {}
            self.directions = {}
            for direction, station_direction in self.station.directions.items():
                if not direction in self.directions:
                    self.directions[direction] = {}
                for train_no, service in station_direction.items():
                    service_live = service_live_t(
                        service,
                        (
                            None
                            if not await self.service_pos_table.__contains__(train_no)
                            else (await self.service_pos_table[train_no]).delay
                        ),
                    )
                    if not time_passed(service_live.delayed_departure, 0):
                        self.service_lives[train_no] = service_live
                        self.directions[direction][train_no] = service_live
            for (
                direction,
                station_direction,
            ) in self.station_tomorrow.directions.items():
                if not direction in self.directions:
                    self.directions[direction] = {}
                for train_no, service in station_direction.items():
                    service_live = service_live_t(
                        service,
                        (
                            None
                            if not await self.service_pos_table.__contains__(train_no)
                            else (await self.service_pos_table[train_no]).delay
                        ),
                    )
                    if time_passed(service_live.delayed_departure, 0):
                        self.service_lives[train_no] = service_live
                        self.directions[direction][train_no] = service_live
            for direction in self.directions.keys():
                self.directions_sorted[direction] = sorted(
                    self.directions[direction].values(),
                    key=lambda s: handle_cross_day_time(s.delayed_departure),
                )
            self.service_lives_sorted = sorted(
                self.service_lives.values(),
                key=lambda s: handle_cross_day_time(s.delayed_departure),
            )
        return self

    async def values(self, direction=None):
        async with self.lock.reader_lock:
            lives = (
                self.service_lives if direction is None else self.directions[direction]
            )
            return lives.values()

    async def items(self, direction=None):
        async with self.lock.reader_lock:
            lives = (
                self.service_lives if direction is None else self.directions[direction]
            )
            return lives.items()

    async def sorted(self, direction=None):
        async with self.lock.reader_lock:
            lives_sorted = (
                self.service_lives_sorted
                if direction is None
                else self.directions_sorted[direction]
            )
            return lives_sorted

    async def __contains__(self, train_no, direction=None):
        async with self.lock.reader_lock:
            lives = (
                self.service_lives if direction is None else self.directions[direction]
            )
            return train_no in lives

    async def __getitem__(self, train_no, direction=None):
        async with self.lock.reader_lock:
            lives = (
                self.service_lives if direction is None else self.directions[direction]
            )
            return lives[train_no]


class station_live_table_t:
    def __init__(self, station_table, tomorrow_station_table, service_pos_table):
        self.table = {}
        self.station_table = station_table
        self.tomorrow_station_table = tomorrow_station_table
        self.service_pos_table = service_pos_table
        self.lock = RWLock()

    async def fetch(self):
        async with self.lock.writer_lock:
            for station_id in await self.station_table.keys():
                self.table[station_id] = await station_live_t(
                    station_id,
                    await self.station_table[station_id],
                    await self.tomorrow_station_table[station_id],
                    self.service_pos_table,
                ).fetch()
        return self

    async def __contains__(self, station_id):
        async with self.lock.reader_lock:
            return station_id in self.table

    async def __getitem__(self, station_id):
        async with self.lock.reader_lock:
            return self.table[station_id]

    async def get(self, station_id):
        async with self.lock.reader_lock:
            return self.table[station_id]

    async def values(self):
        async with self.lock.reader_lock:
            return self.table.values()

    async def items(self):
        async with self.lock.reader_lock:
            return self.table.items()


# 主函數，啟動異步請求並輸出各站時刻表
async def main(station_id="1000"):
    import tdx_requester
    from station_map import station_id_translator_t
    from train_type import train_types_translator_t

    requester = tdx_requester.tdx_requester()

    (
        station_table,
        station_table_tomorrow,
        service_pos_table,
        id_translator,
        type_translator,
    ) = await asyncio.gather(
        station_table_t(requester).fetch(),
        station_table_t(
            requester, (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        ).fetch(),
        service_pos_table_t(requester).fetch(),
        station_id_translator_t(requester).fetch(),
        train_types_translator_t().fetch(),
    )
    station_live_table = await station_live_table_t(
        station_table, station_table_tomorrow, service_pos_table
    ).fetch()
    for service_live in await (await station_live_table[station_id]).sorted():
        sl = service_live
        # 判斷未發車的條件為: 延遲時間為 None 或 列車已發車
        print(
            f"{sl.train_no}\t{id_translator[sl.dest]}\t{type_translator[sl.train_type]}\t{sl.scheduled_departure}\t{'未發車'if sl.delay is None or service_live.departed else f'晚{sl.delay}分' if sl.delay > 0 else '準點'}"
        )


# 執行異步主函數
if __name__ == "__main__":
    import sys

    station_id = str(sys.argv[1]) if len(sys.argv) > 1 else "1000"
    asyncio.run(main(station_id))
