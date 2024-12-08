from datetime import datetime, timedelta

import tdx_requester
from station_table import StationTable, Train, Station
from train_live import TrainPositionTable

def time_delay(original_time: str, delay: int) -> str:
    original_time_obj = datetime.strptime(original_time, "%H:%M")
    delayed_time_obj = original_time_obj + timedelta(minutes=delay)
    return delayed_time_obj.strftime("%H:%M")

def time_passed(compare_time: str, day_cross=0) -> bool:
    current_time_obj = datetime.now()
    day_start = current_time_obj.replace(
        hour=day_cross, minute=0, second=0, microsecond=0
    )
    # 如果當前時間在當天的00:00之前，則將day_start設置為前一天的00:00
    # 這樣可以確保在跨日的情況下，當前時間仍然能夠正確比較
    # 例如：當前時間是23:59，day_cross是0，則day_start會設置為前一天的00:00
    # 這樣可以確保當前時間在比較時不會錯過當天的00:00
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


class TrainLive:
    def __init__(self, train: Train, delay=None):
        self.train_no = train.train_no
        self.train_type = train.train_type
        self.dest = train.dest
        self.scheduled_arrival = train.arrival
        self.scheduled_departure = train.departure
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


class StationLive:
    def __init__(self, station_id, station:Station, station_tomorrow:Station, train_pos_table):
        self.station_id = station_id
        self.train_lives = {}
        self.train_lives_sorted = None
        self.directions = {}
        self.directions_sorted = {}
        self.station = station
        self.station_tomorrow = station_tomorrow
        self.train_pos_table = train_pos_table

        for direction, station_direction in self.station.directions.items():
            if not direction in self.directions:
                self.directions[direction] = {}
            for train_no, train in station_direction.items():
                train_live = TrainLive(
                    train,
                    (
                        None
                        if not train_no in self.train_pos_table
                        else self.train_pos_table[train_no].delay
                    ),
                )
                if not time_passed(train_live.delayed_departure, 0):
                    self.train_lives[train_no] = train_live
                    self.directions[direction][train_no] = train_live
        for (
            direction,
            station_direction,
        ) in self.station_tomorrow.directions.items():
            if not direction in self.directions:
                self.directions[direction] = {}
            for train_no, train in station_direction.items():
                train_live = TrainLive(
                    train,
                    (
                        None
                        if not train_no in self.train_pos_table
                        else self.train_pos_table[train_no].delay
                    ),
                )
                if time_passed(train_live.delayed_departure, 0):
                    self.train_lives[train_no] = train_live
                    self.directions[direction][train_no] = train_live
        for direction in self.directions.keys():
            self.directions_sorted[direction] = sorted(
                self.directions[direction].values(),
                key=lambda s: handle_cross_day_time(s.delayed_departure),
            )
        self.train_lives_sorted = sorted(
            self.train_lives.values(),
            key=lambda s: handle_cross_day_time(s.delayed_departure),
        )

    def values(self, direction=None):
        lives = self.train_lives if direction is None else self.directions[direction]
        return lives.values()

    def items(self, direction=None):
        lives = self.train_lives if direction is None else self.directions[direction]
        return lives.items()

    def sorted(self, direction=None):
        lives_sorted = (
            self.train_lives_sorted
            if direction is None
            else self.directions_sorted[direction]
        )
        return lives_sorted

    def __contains__(self, train_no, direction=None):
        lives = self.train_lives if direction is None else self.directions[direction]
        return train_no in lives

    def __getitem__(self, train_no, direction=None):
        lives = self.train_lives if direction is None else self.directions[direction]
        return lives[train_no]


class StationLiveTable:
    def __init__(self, station_table:StationTable, tomorrow_station_table:StationTable, train_pos_table):
        self.table = {}
        self.station_table = station_table
        self.tomorrow_station_table = tomorrow_station_table
        self.train_pos_table = train_pos_table
        
        for station_id in set(self.station_table.keys()).union(self.tomorrow_station_table.keys()):
            self.table[station_id] = StationLive(
                station_id,
                self.station_table[station_id],
                self.tomorrow_station_table[station_id],
                self.train_pos_table,
            )

    def __contains__(self, station_id):
        return station_id in self.table

    def __getitem__(self, station_id):
        return self.table[station_id]

    def get(self, station_id):
        return self.table[station_id]

    def values(self):
        return self.table.values()

    def items(self):
        return self.table.items()

# 主函數，啟動異步請求並輸出各站時刻表
async def main(station_id="1000"):
    from station_map import StationTrainslator
    from train_type import TrainTypeTranslator
    
    requester = tdx_requester.TDXRequester()

    (
        station_table,
        station_table_tomorrow,
        train_pos_table,
        id_translator,
        type_translator,
    ) = await asyncio.gather(
        StationTable().fetch(requester),
        StationTable((datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")).fetch(requester),
        TrainPositionTable().fetch(requester),
        StationTrainslator().fetch(requester),
        TrainTypeTranslator(ailas=True).fetch(requester),
    )
    station_live_table = StationLiveTable(
        station_table, station_table_tomorrow, train_pos_table
    )
    for train_live in station_live_table[station_id].sorted():
        sl = train_live
        # 判斷未發車的條件為: 延遲時間為 None 或 列車已發車
        print(
            f"{sl.train_no}\t{id_translator[sl.dest]}\t{type_translator[sl.train_type]}\t{sl.scheduled_departure}\t{'未發車'if sl.delay is None or train_live.departed else f'晚{sl.delay}分' if sl.delay > 0 else '準點'}"
        )


# 執行異步主函數
if __name__ == "__main__":
    import asyncio
    import sys

    station_id = str(sys.argv[1]) if len(sys.argv) > 1 else "1000"
    asyncio.run(main(station_id))
