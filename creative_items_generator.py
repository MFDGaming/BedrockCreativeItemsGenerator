import base64
from binary_utils.binary_stream import binary_stream
import json
from nbt_utils.utils.nbt_net_le_binary_stream import nbt_net_le_binary_stream
from nbt_utils.utils.nbt_le_binary_stream import nbt_le_binary_stream
from nbt_utils.tag.compound_tag import compound_tag

class BlockStateMap:
    def __init__(self, tag: compound_tag):
        self.runtime_to_state: list = []
        self.state_to_runtime: dict = {}
        metadata_counter: int = 0
        old_name: str = ""
        for runtime_id, inner_tag in enumerate(tag.value):
            name: str = inner_tag.get_tag("name").value
            if name != old_name:
                metadata_counter = 0
            self.runtime_to_state.append(f"{name} {metadata_counter}")
            self.state_to_runtime[f"{name} {metadata_counter}"] = runtime_id
            metadata_counter += 1
            old_name = name

    def get_runtime_to_state(self, runtime_id: int) -> tuple:
        if runtime_id < len(self.runtime_to_state):
            tmp: tuple = self.runtime_to_state[runtime_id].split(" ")
            return tmp[0], int(tmp[1])
        else:
            return "", 0

    def get_state_to_runtime(self, name: str, metadata: int) -> int:
        if f"{name} {metadata}" in self.state_to_runtime:
            return self.state_to_runtime[f"{name} {metadata}"]
        else:
            return -1

class ItemStateMap:
    def __init__(self, states: list):
        self.runtime_to_state: dict = {}
        self.state_to_runtime: dict = {}
        for state in states:
            self.runtime_to_state[state["runtime_id"]] = state["name"]
            self.state_to_runtime[state["name"]] = state["runtime_id"]

    def get_runtime_to_state(self, runtime_id: int) -> str:
        if runtime_id in self.runtime_to_state:
            return self.runtime_to_state[runtime_id]
        else:
            return ""

    def get_state_to_runtime(self, name: str) -> int:
        if name in self.state_to_runtime:
            return self.state_to_runtime[name]
        else:
            return 0

def create_block_state_map() -> BlockStateMap:
    file = open("block_states.nbt", "rb")
    stream: nbt_net_le_binary_stream = nbt_net_le_binary_stream(file.read())
    file.close()
    tag: compound_tag = compound_tag()
    tag.read(stream)
    return BlockStateMap(tag)

def create_item_state_map() -> ItemStateMap:
    file = open("item_states.json", "rt")
    data: list = json.loads(file.read())
    file.close()
    return ItemStateMap(data)

def decode_creative_content_packet(stream: binary_stream) -> list:
    stream.read_var_int() # PACKET_ID
    items: list = []
    for _ in range(stream.read_var_int()):
        stream.read_var_int()
        network_id: int = stream.read_signed_var_int()
        if network_id != 0:
            count: int = stream.read_unsigned_short_le()
            metadata: int = stream.read_var_int()
            block_runtime_id: int = stream.read_signed_var_int()
            temp_stream: binary_stream = binary_stream(stream.read(stream.read_var_int()))
            with_nbt: bool = True if temp_stream.read_unsigned_short_le() == 0xffff else False
            nbt: compound_tag = None
            nbt_version: int = 0
            if with_nbt:
                nbt_version = temp_stream.read_unsigned_byte()
                nbt_stream: nbt_le_binary_stream = nbt_le_binary_stream(temp_stream.data, temp_stream.pos)
                nbt = nbt_stream.read_root_tag()
                temp_stream.pos = nbt_stream.pos
                # Todo can_place & can_break
            items.append({
                "network_id": network_id,
                "count": count,
                "metadata": metadata,
                "block_runtime_id": block_runtime_id,
                "with_nbt": with_nbt,
                "nbt_version": nbt_version,
                "nbt": nbt
            })
    return items

def create_creative_content() -> list:
    file = open("creative_content.pk", "rb")
    stream: binary_stream = binary_stream(file.read())
    file.close()
    return decode_creative_content_packet(stream)

block_states: BlockStateMap = create_block_state_map()
item_states: ItemStateMap = create_item_state_map()
creative_content: list = create_creative_content()
creative_items: list = []
for item in creative_content:
    creative_item: dict = {}
    creative_item["name"] = item_states.get_runtime_to_state(item["network_id"])
    if item["metadata"] != 0:
        creative_item["metadata"] = item["metadata"]
    if item["with_nbt"]:
        stream: nbt_le_binary_stream = nbt_le_binary_stream()
        stream.write_root_tag(item["nbt"])
        creative_item["nbt_b64"] = base64.b64encode(stream.data).decode()
    if item["network_id"] < 256:
        state: tuple = block_states.get_runtime_to_state(item["block_runtime_id"])
        creative_item["block_state_name"] = state[0]
        creative_item["block_state_metadata"] = state[1]
    else:
        if item["block_runtime_id"] != 0:
            print(creative_item["name"])
    creative_items.append(creative_item)

file = open("creative_items.json", "wt")
file.write(json.dumps(creative_items, indent = 4))
file.close()
