import time
from datetime import datetime

import tdx_requester
from station_map import StationTrainslator

query_path = "/v3/Rail/TRA/TrainLiveBoard"
query_args = "$select=TrainNo,TrainTypeID,StationId,DelayTime"


def iso_to_timestamp(iso_string):
    dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    return int(dt.timestamp())


class TrainPosition:
    def __init__(self, train_pos_data):
        self.train_no = train_pos_data["TrainNo"]
        self.station_id = train_pos_data["StationID"]
        self.delay = train_pos_data["DelayTime"]
        self.update_time = train_pos_data["UpdateTime"]

    def __repr__(self):
        return self.train_no


async def fetch_train_position(requester):
    data = await requester.get(query_path + "?" + query_args)
    return data


class TrainPositionTable:
    def __init__(self):
        self.table = {}
        self.last_fetched_time = None
        self.update_time = None
        self.src_update_time = None

    async def fetch(self, requester):
        data = await fetch_train_position(requester)
        self.last_fetched_time = time.time()
        self.update_time = iso_to_timestamp(data["UpdateTime"])
        self.src_update_time = iso_to_timestamp(data["SrcUpdateTime"])
        for train_pos_data in data["TrainLiveBoards"]:
            self.table[train_pos_data["TrainNo"]] = TrainPosition(train_pos_data)
        return self

    def assert_fetched(self):
        if self.last_fetched_time is None:
            raise Exception("Service position not fetched")

    def __contains__(self, train_no):
        return train_no in self.table

    def __getitem__(self, train_no):
        return self.table[train_no]

    def values(self):
        return list(self.table.values())


async def main():

    requester = tdx_requester.TDXRequester()
    table = await TrainPositionTable().fetch(requester)
    translator = await StationTrainslator().fetch(requester)
    for service_live in table.values():
        print(
            f"{service_live}現在在{translator[service_live.station_id]}，{f'晚{service_live.delay}分' if service_live.delay > 0 else '準點'}"
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
