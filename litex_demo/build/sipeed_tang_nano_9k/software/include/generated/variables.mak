PACKAGES=libc libcompiler_rt libbase libfatfs liblitespi liblitedram libliteeth liblitesdcard liblitesata bios
PACKAGE_DIRS=/home/fabian/Documents/litex/litex/litex/soc/software/libc /home/fabian/Documents/litex/litex/litex/soc/software/libcompiler_rt /home/fabian/Documents/litex/litex/litex/soc/software/libbase /home/fabian/Documents/litex/litex/litex/soc/software/libfatfs /home/fabian/Documents/litex/litex/litex/soc/software/liblitespi /home/fabian/Documents/litex/litex/litex/soc/software/liblitedram /home/fabian/Documents/litex/litex/litex/soc/software/libliteeth /home/fabian/Documents/litex/litex/litex/soc/software/liblitesdcard /home/fabian/Documents/litex/litex/litex/soc/software/liblitesata /home/fabian/Documents/litex/litex/litex/soc/software/bios
LIBS=libc libcompiler_rt libbase libfatfs liblitespi liblitedram libliteeth liblitesdcard liblitesata
TRIPLE=riscv64-unknown-elf
CPU=vexriscv
CPUFAMILY=riscv
CPUFLAGS=-march=rv32i2p0_m     -mabi=ilp32 -D__vexriscv__
CPUENDIANNESS=little
CLANG=0
CPU_DIRECTORY=/home/fabian/Documents/litex/litex/litex/soc/cores/cpu/vexriscv
SOC_DIRECTORY=/home/fabian/Documents/litex/litex/litex/soc
PICOLIBC_DIRECTORY=/home/fabian/Documents/litex/pythondata-software-picolibc/pythondata_software_picolibc/data
PICOLIBC_FORMAT=integer
COMPILER_RT_DIRECTORY=/home/fabian/Documents/litex/pythondata-software-compiler_rt/pythondata_software_compiler_rt/data
export BUILDINC_DIRECTORY
BUILDINC_DIRECTORY=/home/fabian/Documents/litex_demo/build/sipeed_tang_nano_9k/software/include
LIBC_DIRECTORY=/home/fabian/Documents/litex/litex/litex/soc/software/libc
LIBCOMPILER_RT_DIRECTORY=/home/fabian/Documents/litex/litex/litex/soc/software/libcompiler_rt
LIBBASE_DIRECTORY=/home/fabian/Documents/litex/litex/litex/soc/software/libbase
LIBFATFS_DIRECTORY=/home/fabian/Documents/litex/litex/litex/soc/software/libfatfs
LIBLITESPI_DIRECTORY=/home/fabian/Documents/litex/litex/litex/soc/software/liblitespi
LIBLITEDRAM_DIRECTORY=/home/fabian/Documents/litex/litex/litex/soc/software/liblitedram
LIBLITEETH_DIRECTORY=/home/fabian/Documents/litex/litex/litex/soc/software/libliteeth
LIBLITESDCARD_DIRECTORY=/home/fabian/Documents/litex/litex/litex/soc/software/liblitesdcard
LIBLITESATA_DIRECTORY=/home/fabian/Documents/litex/litex/litex/soc/software/liblitesata
BIOS_DIRECTORY=/home/fabian/Documents/litex/litex/litex/soc/software/bios
LTO=0
BIOS_CONSOLE_FULL=1