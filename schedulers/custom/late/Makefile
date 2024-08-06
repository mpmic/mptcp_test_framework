obj-m = mptcp_late.o
KERNEL = $(shell uname -r)
all:
	make -C /lib/modules/$(KERNEL)/build M=$(PWD) modules
clean:
	make -C /lib/modules/$(KERNEL)/build M=$(PWD) clean
