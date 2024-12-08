import asyncio
import tdx_requester
from aiorwlock import RWLock

query_path = "/v3/Rail/TRA/DailyTrainTimetable/Today"
query_args = ""


class stop_t:
    def __init__(self, stop_data):
        self.stop_seq = stop_data["StopSequence"]
        self.station_id = stop_data["StationID"]
        self.arrival = stop_data["ArrivalTime"]
        self.departure = stop_data["DepartureTime"]

    def __repr__(self):
        return self.station_id


class stop_table_t:
    def __init__(self, stop_table_data):
        self.table = {}
        for stop_data in stop_table_data:
            self.table[stop_data["StationID"]] = stop_t(stop_data)

    def __contains__(self, station_id):
        return station_id in self.table

    def __getitem__(self, station_id):
        return self.table[station_id]


class service_t:
    def __init__(self, service_data):
        service_info_data = service_data["TrainInfo"]
        self.train_no = service_info_data["TrainNo"]
        self.direction = service_info_data["Direction"]
        self.train_type_id = service_info_data["TrainTypeID"]
        self.start_station_id = service_info_data["StartingStationID"]
        self.end_station_id = service_info_data["EndingStationID"]
        self.overnight_id = None
        if "OverNightStationID" in service_info_data:
            self.overnight_id = service_info_data["OverNightStationID"]
        self.trip_line = service_info_data["TripLine"]
        self.suspended = service_info_data["SuspendedFlag"]
        self.stop_table = stop_table_t(service_data["StopTimes"])

    def __repr__(self):
        return self.train_no

    def __contains__(self, station_id):
        return station_id in self.stop_table

    def __getitem__(self, station_id):
        return self.stop_table[station_id]


async def fetch_train_table(requester):
    data = await requester.get(query_path + "?" + query_args)
    services = {}
    for service_data in data["TrainTimetables"]:
        services[service_data["TrainInfo"]["TrainNo"]] = service_t(service_data)
    return services


class service_table_t:
    def __init__(self, requester):
        self.requester = requester
        self.services = None
        self.fetched = False
        self.lock = RWLock()

    async def fetch(self):
        async with self.lock.writer_lock:
            self.services = await fetch_train_table(self.requester)
            self.fetched = True
        return self

    def assert_fetched(self):
        if not self.fetched:
            raise Exception("Train table not fetched")

    async def __contains__(self, train_no):
        async with self.lock.reader_lock:
            return train_no in self.services

    async def __getitem__(self, train_no):
        async with self.lock.reader_lock:
            return self.services[train_no]

    async def values(self):
        async with self.lock.reader_lock:
            return list(self.services.values())


# Main function
async def main():
    requester = tdx_requester.tdx_requester()
    service_table = await service_table_t(requester).fetch()
    for service in await service_table.values():
        if service.overnight_id is not None:
            print(f"{service}是跨日班次")


# Run the program
if __name__ == "__main__":
    asyncio.run(main())
