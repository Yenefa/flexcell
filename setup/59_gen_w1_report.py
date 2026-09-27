# -*- coding: utf-8 -*-
"""Generate Week-1 acceptance report docx for project-033-flexcell (for 大统领)."""
import os

from docx import Document
from docx.shared import Pt

OUT = r"C:\Users\fuker\Desktop\workspace\project-033-flexcell\docs\验收报告-project-033-flexcell-week1-20260926.docx"

doc = Document()
style = doc.styles["Normal"]
style.font.size = Pt(10.5)

doc.add_heading("project-033-flexcell Week-1 验收报告 · Deterministic Skills + FSM", level=0)
doc.add_paragraph("日期：2026-09-26　|　上游：Yenefa/flexcell @ a6b00e7 + 本地 Week-1 实现　|　环境：本机 WSL2 Ubuntu-24.04（user ros）")
doc.add_paragraph(
    "结论速览：机器人现在能自己干完整活——观察世界、抓起方块、搬到指定点、放下并实测验证，"
    "全程无 LLM、无人工干预，18-23 秒一轮，落点真值误差 4.9-6.5mm。负路径全部类型化拒绝，Day-2 回归 10/10 零退化。"
)

doc.add_heading("一、验收结论", level=1)
doc.add_paragraph(
    "上游路线图 Week-1 要求在 Day-2 单一运动技能之上，建立 observe / pick / place / verify 四个确定性技能和一个任务级 FSM。"
    "本次为本机首次实现（上游仓库尚无该部分代码），并在真实 Gazebo 物理环境中全量验收通过："
    "主链多次运行落点真值误差稳定在 5-7mm（容差 60mm），所有失败模式都能给出诚实的类型化结果而不是假装成功。"
    "这标志着 flexcell 的「确定性机器人基线」正式成立——按上游铁律，这是任何 LLM/Task Policy 工作的前置条件。"
)

doc.add_heading("二、Week-1 DoD 验收表（7/7 + 回归 10/10）", level=1)
rows = [
    ("#", "用例", "实测结果", "判定"),
    ("1", "observe 世界快照", "SUCCEEDED：revision、target_box 真值位姿、EE 位姿、关节数齐全", "PASS"),
    ("2", "task 全链 happy path", "SUCCEEDED：OBSERVE→PICK→PLACE→VERIFY，落点真值误差 5.6mm，22.8s", "PASS"),
    ("3", "verify 独立验证", "VERIFIED：实测与期望差 5.3mm（容差 50mm）", "PASS"),
    ("4", "pick 未知物体", "OBJECT_UNKNOWN（gz 侧无此模型，~1s 快败）", "PASS"),
    ("5", "place 未携带", "NOT_CARRIED（规划场景核查，39ms；电池轮次偶发客户端挂起已手动复验）", "PASS"),
    ("6", "任务互斥", "第一任务 SUCCEEDED（6.5mm），并发第二任务正确收到 RESOURCE_BUSY", "PASS"),
    ("7", "place 不可达", "PLACE 的 IK_NO_IK_SOLUTION 类型化传播为 SKILL_FAILED，方块诚实保留在臂上", "PASS"),
    ("R", "Day-2 回归（10 用例）", "happy×2 + INVALID×3 + STALE + IK + TIMEOUT + CANCELED + Day-1 回归全数通过", "PASS"),
]
t = doc.add_table(rows=len(rows), cols=4)
t.style = "Table Grid"
for i, r in enumerate(rows):
    for j, cell in enumerate(r):
        t.rows[i].cells[j].text = cell

doc.add_heading("三、方案要点（本机实现）", level=1)
for line in [
    "技能组合而非重复造轮：pick/place 内部复用 Day-2 MoveToPose 动作（运动规划仍由 MoveIt 负责），技能层只做观察、夹爪、规划场景附着与实测校验。",
    "承载方案 = 传送伺服磁性抓取：carry_server 节点以 10Hz 调 Gazebo /world/empty/set_pose 服务，把 target_box 钉在末端执行器实测偏移处（pick 冻结偏移、place 释放）。DetachableJoint 插件方案三连败（订阅者消失/关节静默失败/一次性发布丢消息）后弃用，实录见踩坑日记 A 级条目。",
    "高度几何先验算：EE 安全区 z≳0.16m——低位目标会让朝向不受控的长夹爪扫进方块/地面（实测差 4-7cm）；悬停点先按臂展包络 sqrt(x²+y²+(z-0.02)²)≲0.35 验算，本次曾因 hover 0.3575m 超臂展被 IK 正确拒绝。",
    "测量诚实性贯穿：盒子上升量不足 → GRASP_FAILED 并自动释放；place 落点超差 → PLACE_FAILED 如实报告；plan 扫飞方块 → POSE_NOT_REACHED 拦截。",
    "世界文件 flexcell_world.sdf 预置 target_box（无任何 gz 插件），50 脚本重启即得确定性初始态。",
]:
    doc.add_paragraph(line, style="List Bullet")

doc.add_heading("四、技能接口清单（给 agent 的能力面）", level=1)
for line in [
    "/observe — 世界快照（revision + 物体真值位姿 + EE/关节），同步发布 /flexcell/world_state",
    "/pick_object — 观察→悬停→下降→合爪→伺服承载→提升，实测上升量校验",
    "/place_object — 携带校验→悬停→下降→释放→落点实测→退避",
    "/verify_object — 真值位姿 vs 期望位姿（位置误差 + VERIFIED/MISMATCH）",
    "/run_pick_place — 任务 FSM：OBSERVE→PICK→PLACE→VERIFY，单任务互斥，阶段反馈，fsm_trace 全程留痕",
    "全部动作返回类型化 outcome + 错误码分类 + evidence_id，JSONL 结构化日志可审计可回放",
]:
    doc.add_paragraph(line, style="List Bullet")

doc.add_heading("五、复验步骤（大统领操作）", level=1)
for line in [
    "1) 查活（预期 gz sim/move_group/rviz2 + 6 个技能服务器进程）：",
    "   wsl -d Ubuntu-24.04 -u ros -- pgrep -af \"move_group|gz sim|rviz2|_server\"",
    "2) 若栈已停：wsl -d Ubuntu-24.04 -u ros -- bash /mnt/f/flexcell-stage/setup/50_start_detached.sh（自带 move_group 验活重试），然后手动拉起技能层（命令见 project-033-flexcell README）。",
    "3) Week-1 全量电池（自包含清洁跑，含两次栈重启，约 8 分钟）：",
    "   wsl -d Ubuntu-24.04 -u ros -- bash -c 'tr -d \"\\r\" < /mnt/f/flexcell-stage/setup/47_w1_acceptance.sh > /tmp/w1bat.sh; tr -d \"\\r\" < /mnt/f/flexcell-stage/setup/50_start_detached.sh > /tmp/50start.sh && bash /tmp/w1bat.sh'",
    "4) 判定：w1_2（全链 SUCCEEDED，落点误差 <0.06）、w1_6（第二任务 RESOURCE_BUSY）、w1_7（PLACE IK 失败传播）；Day-2 回归见 32 电池 10/10。",
]:
    doc.add_paragraph(line)

doc.add_heading("六、踩坑摘要（详见 踩坑日记/开发踩坑.md，今日 +2 条）", level=1)
for line in [
    "DetachableJoint 三连败（A 级）：机器人级插件首轮 detach 后订阅者消失；世界级关节创建静默失败；一次性 gz topic 发布存在发现竞态整条丢消息——终态改用 set_pose 传送伺服，可观测、零状态、跨会话稳定。",
    "wsl.exe interop 四副新面孔（B 级）：裸路径被 MSYS 转换、循环变量丢失、pkill 命中自身重定向路径自杀、&&/& 优先级吞 source——一切复杂命令落脚本文件执行。",
    "验收负路径的高度/距离参数先按臂展包络验算再写死；「启动命令返回 ≠ 进程活着」教训两度复发，50 脚本已内置验活重试。",
]:
    doc.add_paragraph(line, style="List Bullet")

doc.save(OUT)
print("saved:", OUT, os.path.getsize(OUT), "bytes")
