import asyncio
import tdx_requester

QUERY_PATH = "/v3/Rail/TRA/DailyTrainTimetable/Today"
QUERY_PATH_DATE = "/v3/Rail/TRA/DailyTrainTimetable/TrainDate"
query_args = ""


class Stop:
    def __init__(self, stop_data):
        self.stop_sequence = stop_data["StopSequence"]
        self.station_id = stop_data["StationID"]
        self.arrival = stop_data["ArrivalTime"]
        self.departure = stop_data["DepartureTime"]

    def __repr__(self):
        return self.station_id


class StopTable:
    def __init__(self, stop_table_data):
        self.table = {}
        for stop_data in stop_table_data:
            self.table[stop_data["StationID"]] = Stop(stop_data)

    def __contains__(self, station_id):
        return station_id in self.table

    def __getitem__(self, station_id):
        return self.table[station_id]


class Train:
    def __init__(self, train_data):
        train_info_data = train_data["TrainInfo"]
        self.train_no = train_info_data["TrainNo"]
        self.direction = train_info_data["Direction"]
        self.train_type_id = train_info_data["TrainTypeID"]
        self.start_station_id = train_info_data["StartingStationID"]
        self.end_station_id = train_info_data["EndingStationID"]
        self.trip_line = train_info_data["TripLine"]
        self.suspended = train_info_data["SuspendedFlag"]
        self.stop_table = StopTable(train_data["StopTimes"])
        self.overnight_id = (
            train_info_data["OverNightStationID"]
            if "OverNightStationID" in train_info_data
            else None
        )

    def __repr__(self):
        return self.train_no

    def __contains__(self, station_id):
        return station_id in self.stop_table

    def __getitem__(self, station_id):
        return self.stop_table[station_id]

def parse_train_data(data):
    trains = {}
    for train_data in data["TrainTimetables"]:
        trains[train_data["TrainInfo"]["TrainNo"]] = Train(train_data)
    return trains


async def fetch_train_table(requester, date=None):
    if date is None:
        data = await requester.get(QUERY_PATH)
    else:
        data = await requester.get(f"{QUERY_PATH_DATE}/{date}")
    return parse_train_data(data)


class TrainTable:
    def __init__(self, date=None, data=None):
        self.trains = None
        self.fetched = False
        self.date = date
        self.parse(data) if data else None

    async def fetch(self, requester):
        self.trains = await fetch_train_table(requester, self.date)
        self.fetched = True
        return self
    
    def parse(self, data):
        self.trains = parse_train_data(data)
        self.fetched = True
        return self

    def assert_fetched(self):
        if not self.fetched:
            raise Exception("Train table not fetched")

    def __contains__(self, train_no):
        return train_no in self.trains

    def __getitem__(self, train_no):
        return self.trains[train_no]

    def values(self):
        return list(self.trains.values())


# Main function
async def main():
    requester = tdx_requester.TDXRequester()
    train_table = await TrainTable().fetch(requester)
    for train in train_table.values():
        if train.overnight_id is not None:
            print(f"{train}是跨日班次")


# Run the program
if __name__ == "__main__":
    asyncio.run(main())
