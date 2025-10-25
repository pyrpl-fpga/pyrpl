import vitis

client = vitis.create_client()
client.set_workspace(path="./vitis_proj")

status = client.add_embedded_sw_repo(level="LOCAL", path=["../../../device-tree-xlnx-xilinx-v2024.2"])
overlay = client.create_advanced_options_dict(dt_overlay = "true" )
platform = client.create_platform_component(
    name = "redpitaya",
    hw_design = "./sdk/red_pitaya.xsa",
    os = "standalone",
    cpu = "ps7_cortexa9_0")
status = platform.add_domain(cpu = "ps7_cortexa9_0", name="Full", generate_dtb=True, dt_overlay=True)

status = platform.build()