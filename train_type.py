# Ailas needed for display but TDX doesn't provide one,
# therefore always pull from local

import json
import asyncio
import aiofiles

file_path = "train_type_static.json"


async def load_train_types_map(file_path):
    async with aiofiles.open(file_path, mode="r", encoding="utf-8") as json_file:
        content = await json_file.read()
        return json.loads(content)


class train_types_translator_t:
    def __init__(self, lang="zh", ailas=True):
        self.lang = lang
        self._ailas = ailas
        self.fetched = False
        self.train_types_map = None

    async def fetch(self):
        self.train_types_map = await load_train_types_map(file_path)
        self.fetched = True
        return self

    def assert_fetched(self):
        if not self.fetched:
            raise Exception("Train type not fetched")

    def chinese(self, id):
        self.assert_fetched()
        return self.train_types_map[id]["TrainTypeName"]["Zh_tw"]

    def english(self, id):
        self.assert_fetched()
        return self.train_types_map[id]["TrainTypeName"]["En"]

    def chinese_ailas(self, id):
        self.assert_fetched()
        return self.train_types_map[id]["TrainTypeAilas"]["Zh_tw"]

    def english_ailas(self, id):
        self.assert_fetched()
        return self.train_types_map[id]["TrainTypeAilas"]["En"]

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
    translator = await train_types_translator_t(ailas=True).fetch()
    print(translator["1100"])


if __name__ == "__main__":
    # 運行異步主程式
    asyncio.run(main())
