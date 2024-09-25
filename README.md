

``` bash
litex_sim --csr-data-width=32 \
              --integrated-rom-size=0x100000 \
              --integrated-main-ram-size=0x10000000 \
              --cpu-type=vexriscv_smp \
              --cpu-variant=standard \
              --with-ethernet \
              --timer-uptime \
              --with-gpio \
              --rom-init $TOCK_BINARY_PATH
```
