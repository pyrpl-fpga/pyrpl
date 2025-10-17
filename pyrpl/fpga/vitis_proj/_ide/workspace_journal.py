# 2025-10-17T14:39:05.448598500
import vitis

client = vitis.create_client()
client.set_workspace(path="vitis_proj")

status = client.set_embedded_sw_repo(level="LOCAL", path=["C:\Users\croquette\GitHub\device-tree-xlnx-xilinx-v2024.2"])

platform = client.create_platform_component(name = "redpitaya",hw_design = "$COMPONENT_LOCATION/../../sdk/red_pitaya.xsa",os = "standalone",cpu = "ps7_cortexa9_0",domain_name = "standalone_ps7_cortexa9_0",generate_dtb = True)

platform = client.get_component(name="redpitaya")
domain = platform.add_domain(cpu = "ps7_cortexa9_0",os = "standalone",name = "Full")

status = platform.build()

vitis.dispose()

