# MPTCP Flexbed
## Project Overview
This project implements a testbed for evaluating and comparing different MultiPath TCP (MPTCP) schedulers, including both built-in and reinforcement learning-based schedulers. It also integrates various TCP congestion control algorithms. The testbed is designed to work with MPTCP v0.96 and a custom RL kernel (for reinforcement learning-based schedulers, use custom kernel) and provides a flexible framework for testing and analyzing scheduler performance.
## Features
- Integration with MPTCP v0.96
- Support for multiple schedulers (built-in and RL-based)
- Various TCP congestion control algorithms
- Automated testing framework
- Performance evaluation based on throughput measurements
- Visualization of results
## Prerequisites
- Ubuntu 20.04 LTS or Ubuntu 20.04.4 LTS
- Python 3.8+
- Git
## Prerequisites for Development
### 1. Create an SSH key for Git
```bash
ssh-keygen
```
### 2. Set up Git
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
ssh-keygen -t rsa -b 4096 -C "your.email@example.com"
```
### 3. MPTCP Installation
#### Installing Out-of-tree Linux Kernel implementation of MultiPath TCP
To install the kernel, download all .deb files from the [releases](https://github.com/multipath-tcp/mptcp/releases/tag/v0.96) page of the Out-of-tree Linux Kernel implementation of MultiPath TCP. Follow instructions in Linux Kernel MultiPath TCP project's [official website](https://multipath-tcp.org/pmwiki.php/Users/AptRepository)
#### Installing custom kernel for Reinforcement Learning support
To use RL schedulers configured in this repo, you must download the custom kernel (contact: Hansini Vijayaraghavan).

After installing the headers, change GRUB settings to load the new kernel on boot:

- Find the name of the menu entry of the kernel in `/boot/grub/grub.cfg`
- Add this as the default in grub:

    ```bash
    sudo nano /etc/default/grub
    ```
    Change to:
    ```
    GRUB_DEFAULT="Ubuntu, with Linux 5.4.230.mptcp"
    ```
    (your kernel name may differ)

- Update grub and restart:

    ```bash
    sudo update-grub
    sudo reboot
    ```

- Verify with:

    ```bash
    uname -r
    ```

### 4. Mininet and Dependencies
Follow the instructions in Mininet's [downloads page](http://mininet.org/download/). Use "Option 2: Native Installation from Source" to setup Mininet with `-a` for all options and support for Python 3. Version `2.3.1b2` of Mininet was used due to issues with Python 2.6 in `2.3.0`.
### 5. Install mptcpd
The Multipath TCP Daemon (mptcpd) is a daemon for Linux-based operating systems that performs multipath TCP path management related operations in the user space. It contains `mptcpize`, used to force legacy applications to use mptcp.
Repo with install instructions are [here](https://github.com/multipath-tcp/mptcpd).

Install the dependencies, especially `autoconf-archive` and `ell >= v0.30` (not 0.3, but rather 0.30)

#### Installing `autoconf-archive`:
```bash
sudo apt install autoconf-archive
```

#### Installing Embedded Linux Library >= v0.30:
```bash
git clone https://git.kernel.org/pub/scm/libs/ell/ell.git
git checkout -b v0.30 tags/0.30
./bootstrap && ./configure && make
sudo make install
```

#### Installing mptcpd:
Now install mptcpd:
```bash
git clone https://github.com/multipath-tcp/mptcpd.git
cd mptcpd
./bootstrap && ./configure && make
sudo make install
```

### 6. Project Setup
Clone the repository and install project-specific dependencies:
```bash
# Clone the repository
git clone <repository-url>
# Navigate to the project directory
cd <project-directory>
# Create a virtual environment
python3 -m venv .venv
# Activate the virtual environment
source .venv/bin/activate
# Install dependencies
pip3 install -r requirements.txt
# Run main.py using sudo -E
sudo -E python3 main.py
```
## Configuration
### Setting up Network Links in Mininet

Edit the `config.yaml` file to define your network topology (see `sample_config.yaml`):

```yaml
topology:
mininet:
links:
- name: wifi
client_ip: 10.0.1.1/24
server_ip: 10.0.1.2/24
bw: 100
delay: 20ms
loss: 0.1
- name: lifi
client_ip: 10.0.2.1/24
server_ip: 10.0.2.2/24
bw: 1000
delay: 5ms
loss: 0.01
```


### Running a Test: Real World Application Example

This section provides a step-by-step guide on how to configure and run a test on a physical testbed as an example.


1. Create a `config.yaml` file in the project root directory with the following content:

    ```yaml
    name: "Real World Application"
    network_env: "physical"

    topology:
    physical:
        client:
        hostname: <ip_address_client>
        username: lifi-client
        password: <password>
        store_location: "~"
        server:
        hostname: <ip_address_server>
        username: lifi-server
        password: <password>
        store_location: "~"

    schedulers:
    - name: MinRTTScheduler
    - name: RoundRobinScheduler
    - name: ECFScheduler
    - name: BLESTScheduler
    - name: LATEScheduler
    - name: FALCONScheduler
    - name: RELESScheduler


    congestion_controls:
    - olia
    - wvegas

    test:
    checkpoint: true
    num_iterations: 30
    server_port: 8080
    file_size:
        - 64K
        - 2M
        - 32M

    results:
    dir: results/
    plot:
        figsize:
        - 10
        - 6
        title: Throughput Distribution by Scheduler
        xlabel: Scheduler
        ylabel: Throughput (Mbps)

    logging:
    file_level: DEBUG
    stdout_level: INFO
    ```

2. Run the main script
    ```bash
    sudo -E python3 main.py
    ```

3. After the test completes, results will be saved in the `results/` directory with name as specified in the `config.yaml` file.

### Running a Test: Asymmetric Paths Example

This section provides a step-by-step guide on how to configure and run a test using Mininet as an example. 


1. Create or update your `config.yaml` file in the project root directory with the following content:

    ```yaml
    name: "Asymmetric Paths"
    network_env: "mininet"

    topology:
    mininet:
        links:
        - name: path1
            client_ip: 10.0.1.1/24
            server_ip: 10.0.1.2/24
            bw: 100
            delay: 30ms
            loss: 0.1
        - name: path2
            client_ip: 10.0.2.1/24
            server_ip: 10.0.2.2/24
            bw: 100
            delay: 90ms
            loss: 0.01

    schedulers:
    - name: MinRTTScheduler
    - name: RoundRobinScheduler
    - name: ECFScheduler
    - name: BLESTScheduler
    - name: RedundantScheduler
    - name: LATEScheduler
    - name: FALCONScheduler
    - name: RELESScheduler

    congestion_controls:
    - olia
    - wvegas

    test:
    checkpoint: true
    num_iterations: 30
    server_port: 8080
    file_size: 
        - 2M

    results:
    dir: results/
    plot:
        figsize: [10, 6]
        title: "Throughput Distribution for Asymmetric Paths"

    logging:
    file_level: DEBUG
    stdout_level: INFO
    ```

2. Run the main script
    ```bash
    sudo -E python3 main.py
    ```

3. After the test completes, results will be saved in the `results/` directory with name as specified in the `config.yaml` file.

## Adding New Schedulers
### Kernel-space schedulers:

- Place kernel object files in `schedulers/custom/<scheduler_name>/`.
- Create a Makefile in the scheduler directory.
- Implement a new class in `schedulers/built_in_scheduler.py`:

    ```python
    class NewScheduler(BuiltInScheduler):
        def __init__(self, client, server):
            super().init(
            name="new_scheduler",
            client=client,
            server=server,
            syscall_name="new_sched"  # if different from name
            )
    ```

- Update `schedulers/scheduler_factory.py` to include the new scheduler.

### User-space schedulers:

- Implement the scheduler logic in `servers/payload/<scheduler_name>/`.
- Create a new server class in `servers/reinforcement_learning_server.py`.
- Update `servers/server_factory.py` to include the new server.

## Adding Congestion Control Algorithms

- Implement a new class in `congestion_control/built_in_congestion_control.py`:

    ```python
    class NewCC(BaseCongestionControl):
        def init(self, client, server):
            super().init(name="new_cc", client=client, server=server)
    ```

- Update `congestion_control/congestion_control_factory.py` to include the new algorithm.

## Managing Python Dependencies

- Add new dependencies to `requirements.in`.
- Compile requirements:

    ```bash
    pip-compile requirements.in
    ```

- Install updated requirements:

    ```bash
    pip install -r requirements.txt
    ```
