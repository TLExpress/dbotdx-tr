# Ailas needed for display but TDX doesn't provide one,
# therefore always pull from local

import asyncio
import tdx_requester
from train_type_ailas import *

QUERY_PATH = "/v3/Rail/TRA/TrainType"


class TrainType:
    def __init__(self, id, code, name, ailas):
        self.id = id
        self.code = code
        self.name = name
        self.ailas = ailas

    def __repr__(self):
        return self.id


def parse_train_types(data):
    train_types = {}
    for item in data:
        train_type = TrainType(
            id=item["TrainTypeID"],
            code=item["TrainTypeCode"],
            name=item["TrainTypeName"],
            ailas=(
                character_train_ailas
                if item["TrainTypeID"] in character_train_ailas
                else train_type_ailas[item["TrainTypeCode"]]
            ),
        )
        train_types[train_type.id] = train_type
    return train_types


async def fetch_train_type(requester):
    data = await requester.get(QUERY_PATH)
    data = data["TrainTypes"]
    return parse_train_types(data)


class TrainTypeTranslator:
    def __init__(self, lang="zh", data=None, ailas=False):
        self.lang = lang
        self.fetched = False
        self.train_types = None
        self._ailas = ailas
        self.parse(data) if data else None

    async def fetch(self, requester):
        self.train_types = await fetch_train_type(requester)
        self.fetched = True
        return self
    
    def parse(self, data):
        self.train_types = parse_train_types(data)
        self.fetched = True
        return self

    def assert_fetched(self):
        if not self.fetched:
            raise Exception("Train type not fetched")

    def chinese(self, id):
        self.assert_fetched()
        return self.train_types[id].name["Zh_tw"]

    def english(self, id):
        self.assert_fetched()
        return self.train_types[id].name["En"]

    def chinese_ailas(self, id):
        self.assert_fetched()
        return self.train_types[id].ailas["Zh_tw"]

    def english_ailas(self, id):
        self.assert_fetched()
        return self.train_types[id].ailas["En"]

    def full(self, id):
        return self.english(id) if self.lang == "en" else self.chinese(id)

    def ailas(self, id):
        return self.english_ailas(id) if self.lang == "en" else self.chinese_ailas(id)

    def trans(self, id):
        self.assert_fetched()
        return self.ailas(id) if self._ailas else self.full(id)

    def __getitem__(self, id):
        return self.trans(id)


async def main():
    requester = tdx_requester.TDXRequester()
    translator = await TrainTypeTranslator(ailas=True).fetch(requester)
    print(translator["1100"])


if __name__ == "__main__":
    # 運行異步主程式
    asyncio.run(main())
