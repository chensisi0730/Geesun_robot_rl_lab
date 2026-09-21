实体机器人是G1 edu u6-zl旗舰版D ，配备因时五指灵巧手RH56DFTP，12个自由度，上半身手臂14个DOF;下半身腿部12个DOF，腰部3个DOF，整机自由度是41。,有深度相机Intel Realsense D435i 和3D激光雷达LIVOX-MID360，
GO2是GO2 EDU-ZL ，3D激光雷达MI3-360,
在CONDA环境env_isaaclab_sim51中，训练G1和GO2在复杂地形行走和速度跟踪的能力，评估启用 height_scanner的收益和风险。
守护进程scripts/monitor_tb_check.py，每4个小时监控TensorBoard里面的各项训练曲线，发现训练曲线恶化后，自动停止训练，并修改代码，调整超参数，重新训练。
要求改动尽量小，方便做消融对照实验。
GeesunDog的URDF文件有问题，不要训练。
训练完成后，如何验证训练结果？`unitree_rl_lab` 的 editable 安装实际没有指向本仓库的问题还存在吗
用中文思考和回答。考虑更新文档手册README.md，添加验证训练结果的步骤。
每次回答最后回复“汪汪”。
总结整个地形和terrain_levels 和lin_vel_cmd_levels的设计逻辑，使用图表展示；
terrain_levels 和lin_vel_cmd_levels的升级和降级的逻辑是什么？他们之间的关系是什么？如何稳定提高terrain_levels和lin_vel_cmd_levels？


检查TensorBoard里面的各项训练曲线，列出每种地形的情况下，训练的情况，给出改进方案。Loss/value_function曲线增大才是正常的吗？

