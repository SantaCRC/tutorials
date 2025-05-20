set_device -name GW1NR-9C GW1NR-LV9QN88PC6/I5
add_file sipeed_tang_nano_9k.cst
add_file sipeed_tang_nano_9k.sdc
add_file /home/fabian/Documents/litex/pythondata-cpu-vexriscv/pythondata_cpu_vexriscv/verilog/VexRiscv.v
add_file /home/fabian/Documents/litex_demo/build/sipeed_tang_nano_9k/gateware/sipeed_tang_nano_9k.v
set_option -use_mspi_as_gpio 1
run all