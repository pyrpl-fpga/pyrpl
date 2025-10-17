# 0 "c:\\Xilinx\\Vitis\\2024.2\\tps\\win64\\lopper-1.1.0\\env\\Lib\\site-packages\\lopper\\lops\\lop-cpu-oslist.dts"
# 0 "<built-in>"
# 0 "<command-line>"
# 1 "c:\\Xilinx\\Vitis\\2024.2\\tps\\win64\\lopper-1.1.0\\env\\Lib\\site-packages\\lopper\\lops\\lop-cpu-oslist.dts"
# 10 "c:\\Xilinx\\Vitis\\2024.2\\tps\\win64\\lopper-1.1.0\\env\\Lib\\site-packages\\lopper\\lops\\lop-cpu-oslist.dts"
/dts-v1/;

/ {
        compatible = "system-device-tree-v1,lop";
        lops {
                compatible = "system-device-tree-v1,lop";
                lop_0 {
                      compatible = "system-device-tree-v1,lop,select-v1";
                      select_1;
                      select_2 = "/.*:device_type:cpu";
                      lop_0_1 {
                              compatible = "system-device-tree-v1,lop,code-v1";
                              code = "
                                     import yaml
                                     yaml_dict = {}
                                     for node in __selected__:
                                        cpu_ip_name = node.propval('xlnx,ip-name')[0]
                                        yaml_dict[node.label] = {'ip_name' : '','supported_os' : []}
                                        yaml_dict[node.label]['ip_name'] = cpu_ip_name
                                        if 'cortex' in cpu_ip_name or cpu_ip_name == 'microblaze':
                                            yaml_dict[node.label]['supported_os'] = ['standalone','freertos']
                                        else:
                                            yaml_dict[node.label]['supported_os'] = ['standalone']
                                     with open('cpulist.yaml', 'w') as fd:
                                         fd.write(yaml.dump(yaml_dict, indent = 4))
                                     ";
                      };
                };
                lop_1 {
                       compatible = "system-device-tree-v1,lop,select-v1";
                       select_1;
                       select_2 = "/.*:xlnx,ip-name:ai_engine";
                       lop_1_1 {
                               compatible = "system-device-tree-v1,lop,code-v1";
                               code = "
                                      import yaml
                                      with open('cpulist.yaml', 'r') as fd:
                                        yaml_data = yaml.safe_load(fd)
                                      for node in __selected__:
                                         yaml_data[node.label] = {'ip_name' : 'ai_engine','supported_os' : ['aie_runtime']}
                                      with open('cpulist.yaml', 'w') as fd:
                                          fd.write(yaml.dump(yaml_data, indent = 4))
                                      ";
                               };
                };
        };
};
