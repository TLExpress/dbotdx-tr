import asyncio
import tdx_requester

QUERY_PATH = "/v3/Rail/TRA/DailyStationTimetable/Today"
QUERY_PATH_DATE = "/v3/Rail/TRA/DailyStationTimetable/TrainDate"
QUERY_ARGS = "$select=StationID,Direction,TimeTables"

class Train:
    def __init__(self, train_data):
        self.train_no = train_data["TrainNo"]
        self.arrival = train_data["ArrivalTime"]
        self.departure = train_data["DepartureTime"]
        self.dest = train_data["DestinationStationID"]
        self.train_type = train_data["TrainTypeID"]
        self.train_level = train_data["TrainTypeCode"]

    def __repr__(self):
        return self.train_no

class Station:
    def __init__(self, station_id, date=None):
        self.station_id = station_id
        self.date = date
        self.trains = {}
        self.directions = {}

    def append(self, direction, train: Train):
        train_no = train.train_no
        self.trains[train_no] = train
        if direction not in self.directions:
            self.directions[direction] = {}
        self.directions[direction][train_no] = train

    def __repr__(self):
        return self.station_id

    def __contains__(self, train_no):
        return train_no in self.trains

    def __getitem__(self, train_no):
        return self.trains[train_no]

    def values(self):
        return self.trains.values()

    def items(self):
        return self.trains.items()

def parse_station_table(data,date):
    stations = {}
    for station_timetable in data["StationTimetables"]:
        station_id = station_timetable["StationID"]
        direction = station_timetable["Direction"]

        if station_id not in stations:
            station = Station(station_id, date)

        for train_data in station_timetable["TimeTables"]:
            station.append(direction, Train(train_data))
        stations[station_id] = station
    return stations

async def fetch_station_table(requester, date=None):
    if date is None:
        data = await requester.get(QUERY_PATH + "?" + QUERY_ARGS)
    else:
        data = await requester.get(f"{QUERY_PATH_DATE}/{date}?{QUERY_ARGS}")
    return parse_station_table(data, data["TrainDate"])


class StationTable:
    def __init__(self, date=None, data=None):
        self.stations = None
        self.fetched = False
        self.date = date
        self.parse(data) if data else None

    async def fetch(self, requester):
        self.stations = await fetch_station_table(requester, self.date)
        self.fetched = True
        return self
    
    def parse(self, data):
        self.stations = parse_station_table(data)
        self.fetched = True
        return self

    def assert_fetched(self):
        if not self.fetched:
            raise RuntimeError("Data not fetched yet")

    def __contains__(self, station_id):
        self.assert_fetched()
        return station_id in self.stations

    def __getitem__(self, station_id):
        self.assert_fetched()
        return Station(station_id) if not self.__contains__(station_id) else self.stations[station_id]

    def stops(self, station_id, train_no):
        self.assert_fetched()
        return train_no in self[station_id].trains

    def items(self):
        self.assert_fetched()
        return self.stations.items()

    def values(self):
        self.assert_fetched()
        return self.stations.values()

    def keys(self):
        self.assert_fetched()
        return self.stations.keys()

async def main():
    requester = tdx_requester.TDXRequester()
    table = await StationTable().fetch(requester)
    print("410" in table["0990"])

if __name__ == "__main__":
    asyncio.run(main())
