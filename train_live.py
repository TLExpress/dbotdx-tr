import time
from datetime import datetime
from aiorwlock import RWLock

query_path = "/v3/Rail/TRA/TrainLiveBoard"
query_args = "$select=TrainNo,TrainTypeID,StationId,DelayTime"


def iso_to_timestamp(iso_string):
    # 解析 ISO 8601 格式的字符串为 datetime 对象
    dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    # 将 datetime 对象转换为时间戳
    return int(dt.timestamp())


class service_pos_t:
    def __init__(self, train_info):
        self.train_no = train_info["TrainNo"]
        self.station_id = train_info["StationID"]
        self.delay = train_info["DelayTime"]
        self.update_time = train_info["UpdateTime"]

    def __repr__(self):
        return self.train_no


async def fetch_service_pos(requester):
    data = await requester.get(query_path + "?" + query_args)
    return data


class service_pos_table_t:
    def __init__(self, requester):
        self.requester = requester
        self.table = {}
        self.last_fetched_time = None
        self.update_time = None
        self.src_update_time = None
        self.lock = RWLock()

    async def fetch(self):
        async with self.lock.writer_lock:
            data = await fetch_service_pos(self.requester)
            self.last_fetched_time = time.time()
            self.update_time = iso_to_timestamp(data["UpdateTime"])
            self.src_update_time = iso_to_timestamp(data["SrcUpdateTime"])
            for service_pos_data in data["TrainLiveBoards"]:
                self.table[service_pos_data["TrainNo"]] = service_pos_t(
                    service_pos_data
                )
        return self

    def assert_fetched(self):
        if self.last_fetched_time is None:
            raise Exception("Service position not fetched")

    async def __contains__(self, train_no):
        async with self.lock.reader_lock:
            return train_no in self.table

    async def __getitem__(self, train_no):
        async with self.lock.reader_lock:
            return self.table[train_no]

    async def values(self):
        async with self.lock.reader_lock:
            return list(self.table.values())


async def main():
    import tdx_requester
    from station_map import station_id_translator_t

    requester = tdx_requester.TDXRequester()
    table = await service_pos_table_t(requester).fetch()
    translator = await station_id_translator_t(requester).fetch()
    for service_live in await table.values():
        print(
            f"{service_live}現在在{translator[service_live.station_id]}，{f'晚{service_live.delay}分' if service_live.delay > 0 else '準點'}"
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
