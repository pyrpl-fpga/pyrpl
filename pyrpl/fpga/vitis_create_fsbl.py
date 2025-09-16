import vitis

client = vitis.create_client()
client.set_workspace(path="./vitis_proj")

status = client.set_sw_repo(level="LOCAL", path=["../../../device-tree-xlnx-xilinx-v2024.2"])

platform = client.create_platform_component(
    name = "redpitaya",
    hw = "./sdk/red_pitaya.xsa",
    os = "standalone",
    cpu = "ps7_cortexa9_0")

status = platform.build()

vitis.dispose()
