import asyncio
import tdx_requester
import re

query_path = "/v3/Rail/TRA/Station"
query_args = "$select=StationID,StationName,StationClass"


def check_input_type(input_str):
    if re.fullmatch(r"\d+", input_str):
        return "number"
    elif re.fullmatch(r'[a-zA-Z\s\.,;!?\'"()\[\]{}:]+', input_str):
        return "en"
    elif re.fullmatch(r"[\u4e00-\u9fff]+", input_str):
        return "zh"
    else:
        return "invalid"

def parse_station_data(data):
    station_namemap = {}
    station_namemap_zh = {}
    station_namemap_en = {}

    for station in data["Stations"]:
        station_id = station["StationID"]
        station_name_zh = station["StationName"]["Zh_tw"]
        station_name_en = station["StationName"]["En"]
        station_class = station["StationClass"]
        station_namemap[station_id] = (station_name_zh, station_name_en, station_class)
        station_namemap_zh[station_name_zh] = station_id
        station_namemap_en[station_name_en] = station_id
    return station_namemap, station_namemap_zh, station_namemap_en

async def fetch_station_data(requester):
    data = await requester.get(query_path + "?" + query_args)
    return parse_station_data(data)


class StationTrainslator:
    def __init__(self, lang="zh", data=None):
        self.station_namemap = None
        self.station_namemap_zh = None
        self.station_namemap_en = None
        self.lang = lang
        self.fetched = False
        self.parse(data) if data else None

    async def fetch(self, requester):
        self.station_namemap, self.station_namemap_zh, self.station_namemap_en = (
            await fetch_station_data(requester)
        )
        self.fetched = True
        return self
    
    def parse(self, data):
        self.station_namemap, self.station_namemap_zh, self.station_namemap_en = (
            parse_station_data(data)
        )
        self.fetched = True
        return self

    def assert_fetched(self):
        if not self.fetched:
            raise Exception("Station map not fetched")

    def __contains__(self, id):
        self.assert_fetched()
        itype = check_input_type(id)
        if itype == "number":
            return id in self.station_namemap
        elif itype == "en":
            return id in self.station_namemap_en
        elif itype == "zh":
            return id in self.station_namemap_zh
        else:
            return False

    def __getitem__(self, id):
        self.assert_fetched()
        itype = check_input_type(id)
        if itype == "number":
            if id not in self.station_namemap:
                raise Exception(f"Search failed: id={id}")
            return self.station_namemap[id][1 if self.lang == "en" else 0]
        elif itype == "en":
            if id not in self.station_namemap_en:
                raise Exception(f"Search failed: en={id}")
            return self.station_namemap_en[id]
        elif itype == "zh":
            if id not in self.station_namemap_zh:
                raise Exception(f"Search failed: zh={id}")
            return self.station_namemap_zh[id]
        else:
            raise Exception(f"Invalid input: {id}")

    def id(self, id):
        self.assert_fetched()
        if id in self.station_namemap:
            return id
        elif id in self.station_namemap_zh:
            return self.station_namemap_zh[id]
        elif id in self.station_namemap_en:
            return self.station_namemap_en[id]
        else:
            raise Exception(f"Search failed: id={id}")

    def station_class(self, id):
        self.assert_fetched()
        if id in self.station_namemap:
            return self.station_namemap[id][2]
        else:
            raise Exception(f"Search failed: id={id}")

    def items(self):
        self.assert_fetched()
        return self.station_namemap.items()


async def main():
    requester = tdx_requester.TDXRequester()
    translator = await StationTrainslator().fetch(requester)
    
    for station_id, names in translator.items():
        print(
            f"StationID: {station_id}, 中文站名: {names[0]}, 英文站名: {names[1]}, 站等: {names[2]}"
        )

if __name__ == "__main__":
    asyncio.run(main())
