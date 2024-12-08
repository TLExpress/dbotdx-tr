import asyncio
import tdx_requester
from aiorwlock import RWLock

query_path = "/v3/Rail/TRA/DailyStationTimetable/Today"
query_path_date = "/v3/Rail/TRA/DailyStationTimetable/TrainDate/"
query_args = "$select=StationID,Direction,TimeTables"


class service_t:
    def __init__(self, service_data):
        self.train_no = service_data["TrainNo"]
        self.arrival = service_data["ArrivalTime"]
        self.departure = service_data["DepartureTime"]
        self.dest = service_data["DestinationStationID"]
        self.train_type = service_data["TrainTypeID"]
        self.train_level = service_data["TrainTypeCode"]

    def __repr__(self):
        return self.train_no


class station_t:
    def __init__(self, station_id, date):
        self.station_id = station_id
        self.date = date
        self.services = {}
        self.directions = {}

    def append(self, direction, service_data):
        service = service_t(service_data)
        train_no = service_data["TrainNo"]
        self.services[train_no] = service
        if direction not in self.directions:
            self.directions[direction] = {}
        self.directions[direction][train_no] = service

    def __repr__(self):
        return self.station_id

    def __contains__(self, train_no):
        return train_no in self.services

    def __getitem__(self, train_no):
        return self.services[train_no]

    def values(self):
        return self.services.values()

    def items(self):
        return self.services.items()


async def fetch_station_table(requester, date=None):
    if date is None:
        data = await requester.get(query_path + "?" + query_args)
    else:
        data = await requester.get(query_path_date + date + "?" + query_args)
    date = data["TrainDate"]
    stations = {}

    for station_timetable in data["StationTimetables"]:
        station_id = station_timetable["StationID"]
        direction = station_timetable["Direction"]

        if station_id not in stations:
            station = station_t(station_id, date)

        for service_data in station_timetable["TimeTables"]:
            station.append(direction, service_data)
        stations[station_id] = station
    return stations


class station_table_t:
    def __init__(self, requester, date=None):
        self.requester = requester
        self.stations = None
        self.fetched = False
        self.date = date
        self.lock = RWLock()

    async def fetch(self):
        async with self.lock.writer_lock:
            self.stations = await fetch_station_table(self.requester, self.date)
            self.fetched = True
        return self

    def assert_fetched(self):
        if not self.fetched:
            raise RuntimeError("Data not fetched yet")

    async def __contains__(self, station_id):
        async with self.lock.reader_lock:
            self.assert_fetched()
            return station_id in self.stations

    async def __getitem__(self, station_id):
        async with self.lock.reader_lock:
            self.assert_fetched()
            return self.stations[station_id]

    async def stops(self, station_id, train_no):
        async with self.lock.reader_lock:
            self.assert_fetched()
            return train_no in self[station_id].services

    async def items(self):
        async with self.lock.reader_lock:
            self.assert_fetched()
            return self.stations.items()

    async def values(self):
        async with self.lock.reader_lock:
            self.assert_fetched()
            return self.stations.values()

    async def keys(self):
        async with self.lock.reader_lock:
            self.assert_fetched()
            return self.stations.keys()


async def main():
    requester = tdx_requester.TDXRequester()
    table = await station_table_t(requester).fetch()
    print("408" in await table["1000"])


if __name__ == "__main__":
    asyncio.run(main())
