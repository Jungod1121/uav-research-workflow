# UAV Research Workflow 仿真栈镜像 — 可复现层
# 构建(仓库根目录): docker build -t uav-sim:humble -f docker/Dockerfile .
# 要点: ros:humble 基镜像(避开 px4-dev-base 无 gz target 的 #26153) + 自装 Harmonic
FROM ros:humble

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl lsb-release gnupg wget ca-certificates git python3-pip cmake ninja-build \
 && curl -fsSL https://packages.osrfoundation.org/gazebo.gpg -o /usr/share/keyrings/pkgs-osrf-archive-keyrings.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyrings.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" > /etc/apt/sources.list.d/gazebo-stable.list \
 && apt-get update && apt-get install -y --no-install-recommends gz-harmonic \
 && rm -rf /var/lib/apt/lists/*

# PX4 v1.16.0 源码(含 workflow 改动: px4-rc.params 无头三件套 + CMakeLists 注册)
COPY docker/px4-src /root/PX4-Autopilot
RUN cd /root/PX4-Autopilot && ./Tools/setup/ubuntu.sh --no-nuttx || true \
 && make px4_sitl

# uXRCE-DDS Agent(静态链接)
RUN git clone https://github.com/eProsima/Micro-XRCE-DDS-Agent.git /root/Micro-XRCE-DDS-Agent \
 && cmake -S /root/Micro-XRCE-DDS-Agent -B /root/Micro-XRCE-DDS-Agent/build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
 && make -C /root/Micro-XRCE-DDS-Agent/build -j$(nproc)

# 工作流编排与任务
COPY launch /root/work/launch
COPY scripts /root/work/scripts
WORKDIR /root/work
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && export ROS_DOMAIN_ID=77 && ros2 launch launch/sim_stack.launch.py"]
