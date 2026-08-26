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

# PX4 v1.16.0: 容器内 git clone(需 .git 元数据) + 叠加 workflow 补丁
COPY docker/patches /root/patches
COPY docker/px4-src.tar.gz /tmp/px4-src.tar.gz
COPY docker/px4-gitfiles.tar.gz /tmp/px4-gitfiles.tar.gz
RUN mkdir /root/PX4-Autopilot && tar xzf /tmp/px4-src.tar.gz -C /root/PX4-Autopilot \
 && tar xzf /tmp/px4-gitfiles.tar.gz -C /root/PX4-Autopilot \
 && rm /tmp/px4-src.tar.gz /tmp/px4-gitfiles.tar.gz \
 && cd /root/PX4-Autopilot && git init -q && git config --global --add safe.directory /root/PX4-Autopilot && git add -A \
 && git -c user.email=workflow@local -c user.name=workflow commit -qm "v1.16.0 offline" && git tag -f v1.16.0 \
 && cp /root/patches/px4-rc.params ROMFS/px4fmu_common/init.d-posix/ \
 && sed -i 's/\tpx4-rc.simulator/\tpx4-rc.params\n\tpx4-rc.simulator/' ROMFS/px4fmu_common/init.d-posix/CMakeLists.txt

# 子模块 .git 指针文件悬空 -> 转成真实 mini 仓库(版本查询与 ninja 依赖都要求有效)
RUN cd /root/PX4-Autopilot && find . -name ".git" -type f | while read g; do \
      d=$(dirname "$g"); rm -f "$g"; \
      git config --global --add safe.directory "$d" || true; \
      (cd "$d" && git init -q && git add -A && git -c user.email=w@l -c user.name=w commit -qm sub) || true; done; true

# 依赖(独立层: 失败重跑不回退到 clone)
RUN cd /root/PX4-Autopilot && ./Tools/setup/ubuntu.sh --no-nuttx || true

# 子模块(网络瞬断自动重试, 三轮兜底)
RUN cd /root/PX4-Autopilot \
 && git submodule update --init --recursive || git submodule update --init --recursive || git submodule update --init --recursive

# 编译(限 8 并发 + 降优先级, 保护桌面)
RUN cd /root/PX4-Autopilot && nice -n 10 make -j8 px4_sitl

# uXRCE-DDS Agent(静态链接)
RUN git clone https://github.com/eProsima/Micro-XRCE-DDS-Agent.git /root/Micro-XRCE-DDS-Agent \
 && cmake -S /root/Micro-XRCE-DDS-Agent -B /root/Micro-XRCE-DDS-Agent/build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
 && make -C /root/Micro-XRCE-DDS-Agent/build -j$(nproc)

# px4_msgs 工作区: 直接复用宿主机预编译产物(同 22.04+humble 二进制兼容;
# 容器内 colcon 编译 px4_msgs 会无限挂起, 原因未明, 见 WORKFLOW.md 已知问题)
COPY docker/px4_ros2_ws /root/px4_ros2_ws

# 工作流编排与任务
COPY launch /root/work/launch
COPY scripts /root/work/scripts
WORKDIR /root/work
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && source /root/px4_ros2_ws/install/setup.bash && export ROS_DOMAIN_ID=77 && ros2 launch launch/sim_stack.launch.py"]
