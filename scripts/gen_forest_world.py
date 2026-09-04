#!/usr/bin/env python3
"""gen_forest_world.py — 生成 Gazebo Harmonic 森林世界 (种子化圆柱障碍)。
用法: gen_forest_world.py [out=worlds/forest.sdf] [seed=42] [n=40]
约束: 障碍不落在起点(0,0)和航点(±12,0)的 2.5m 安全半径内, 柱间距 ≥2.2m
"""
import math
import random
import sys
from pathlib import Path

out = Path(sys.argv[1] if len(sys.argv) > 1 else "worlds/forest.sdf")
seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
n = int(sys.argv[3]) if len(sys.argv) > 3 else 40
rng = random.Random(seed)

SAFE = [(0, 0, 2.5), (12, 0, 2.5), (-12, 0, 2.5)]
cols = []
tries = 0
while len(cols) < n and tries < 4000:
    tries += 1
    x = rng.uniform(-16, 16)
    y = rng.uniform(-8, 8)
    r = rng.uniform(0.35, 0.6)
    if any(math.hypot(x - sx, y - sy) < sr + r + 0.8 for sx, sy, sr in SAFE):
        continue
    if any(math.hypot(x - cx, y - cy) < r + cr + 1.6 for cx, cy, cr in cols):
        continue
    cols.append((x, y, r))

model_tpl = """  <model name='tree_{i}'>
    <static>true</static>
    <pose>{x} {y} 1.5 0 0 0</pose>
    <link name='link'>
      <collision name='c'>
        <geometry><cylinder><radius>{r}</radius><length>3</length></cylinder></geometry>
      </collision>
      <visual name='v'>
        <geometry><cylinder><radius>{r}</radius><length>3</length></cylinder></geometry>
        <material><ambient>0.15 0.55 0.2 1</ambient><diffuse>0.2 0.7 0.25 1</diffuse></material>
      </visual>
    </link>
  </model>"""

body = "\n".join(model_tpl.format(i=i, x=x, y=y, r=r) for i, (x, y, r) in enumerate(cols))
world = f"""<?xml version="1.0" ?>
<sdf version="1.6">
  <world name="uavforest">
    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <gravity>0 0 -9.8066</gravity>
    <light name="sun" type="directional">
      <cast_shadows>false</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.8 0.8 0.8 1</diffuse>
      <direction>-0.5 0.1 -0.9</direction>
    </light>
    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="c"><geometry><plane><normal>0 0 1</normal><size>100 100</size></plane></geometry></collision>
        <visual name="v">
          <geometry><plane><normal>0 0 1</normal><size>100 100</size></plane></geometry>
          <material><ambient>0.6 0.6 0.6 1</ambient></material>
        </visual>
      </link>
    </model>
{body}
  </world>
</sdf>
"""
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(world)
print(f"forest.sdf: {len(cols)} 棵树 (seed={seed}, tries={tries}) -> {out}")
