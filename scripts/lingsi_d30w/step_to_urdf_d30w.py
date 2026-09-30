"""D30W STEP -> URDF+STL 自动转换（含 4 轮关节）。

分组契约：
  坐标系 STEP: x=前(+), y=左(+), z=下(+)；单位 mm。URDF 单位 m。
  顶层映射: NAUO1-4=base, NAUO5=hip_hl, NAUO6=hip_fl, NAUO7=hip_hr, NAUO8=hip_fr,
            NAUO9=腿fl, NAUO10=腿fr, NAUO11=腿hl, NAUO12=腿hr
  腿内按叶零件 bbox z 中心: z<150=thigh, 150<=z<400=calf, z>=400=wheel
  关节轴: hip 侧摆 axis=(1,0,0); thigh/calf 俯仰、wheel 旋转 axis=(0,1,0)
  关节原点: P_hip=hip组件bbox中心; P_knee=防油30202轴承对中心;
            P_wheel=D30W_W_WAIFA子树bbox中心; P_thigh=大腿板顶端(估计,待标定)
"""
import json
import os

from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDF import TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
try:
    from OCP.collections import Sequence_TDF_Label
except ImportError:  # cadquery-ocp 7.9.x exposes sequence types as XxxSequence (no OCP.collections module)
    from OCP.TDF import TDF_LabelSequence as Sequence_TDF_Label
from OCP.TopLoc import TopLoc_Location
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Trsf, gp_Vec
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.StlAPI import StlAPI_Writer

# 资产路径相对脚本自身推导（<repo>/scripts/lingsi_d30w/ -> <repo>/），两个工作区均可直接运行
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STEP = os.path.join(_REPO, "geesun_dog_urdf", "geesun-dog", "lingsi_d30w", "D30W轮足外发.STEP")
OUT = os.path.join(_REPO, "geesun_dog_urdf", "geesun-dog", "lingsi_d30w")
# URDF 内 mesh 引用保持绝对路径（加载契约：package:// 重写只认 dog1/dog921 前缀）
MESH_ABS = os.path.abspath(f"{OUT}/meshes")

reader = STEPCAFControl_Reader()
reader.SetNameMode(True)
reader.ReadFile(STEP)
doc = TDocStd_Document(TCollection_ExtendedString("d"))
reader.Transfer(doc)
st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

def name_of(label):
    attr = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), attr):
        return attr.Get().ToExtString()
    return "?"

def bbox(shape):
    b = Bnd_Box()
    BRepBndLib.Add_s(shape, b)
    lo, hi = b.CornerMin(), b.CornerMax()
    return [(lo.X()+hi.X())/2, (lo.Y()+hi.Y())/2, (lo.Z()+hi.Z())/2], \
           [hi.X()-lo.X(), hi.Y()-lo.Y(), hi.Z()-lo.Z()]

leaves = []  # (top, name, shape_global, center, size)
def walk(label, loc, top):
    comps = Sequence_TDF_Label()
    if st.IsAssembly_s(label):
        st.GetComponents_s(label, comps)
        for i in range(1, comps.Length() + 1):
            comp = comps.Value(i)
            child_loc = loc.Multiplied(st.GetLocation_s(comp))
            ref = TDF_Label()
            st.GetReferredShape_s(comp, ref)
            walk(ref, child_loc, top)
    else:
        shape = st.GetShape_s(label).Moved(loc)
        c, s = bbox(shape)
        leaves.append((top, name_of(label), shape, c, s))

free = Sequence_TDF_Label()
st.GetFreeShapes(free)
root = free.Value(1)
comps = Sequence_TDF_Label()
st.GetComponents_s(root, comps)
for i in range(1, comps.Length() + 1):
    comp = comps.Value(i)
    ref = TDF_Label()
    st.GetReferredShape_s(comp, ref)
    walk(ref, st.GetLocation_s(comp), f"NAUO{i}")
print(f"leaves={len(leaves)}", flush=True)

# ---- 分组 ----
LEG = {"NAUO9": "fl", "NAUO10": "fr", "NAUO11": "hl", "NAUO12": "hr"}
HIP = {"NAUO6": "fl", "NAUO8": "fr", "NAUO5": "hl", "NAUO7": "hr"}
groups = {k: [] for k in ["base"] + [f"hip_{l}" for l in LEG.values()] +
          [f"{p}_{l}" for p in ("thigh", "calf", "wheel") for l in LEG.values()]}
for top, name, shape, c, s in leaves:
    if top in ("NAUO1", "NAUO2", "NAUO3", "NAUO4"):
        groups["base"].append((name, shape, c, s))
    elif top in HIP:
        groups[f"hip_{HIP[top]}"].append((name, shape, c, s))
    elif top in LEG:
        leg = LEG[top]
        if "D30W_W_WAIFA" in name or "HZYX" in name or c[2] >= 400:
            groups[f"wheel_{leg}"].append((name, shape, c, s))
        elif c[2] >= 150:
            groups[f"calf_{leg}"].append((name, shape, c, s))
        else:
            groups[f"thigh_{leg}"].append((name, shape, c, s))
    else:
        groups["base"].append((name, shape, c, s))

# ---- 关节原点 ----
def group_bbox(items):
    lo = [min(c[i]-s[i]/2 for _, _, c, s in items) for i in range(3)]
    hi = [max(c[i]+s[i]/2 for _, _, c, s in items) for i in range(3)]
    return [(lo[i]+hi[i])/2 for i in range(3)], [hi[i]-lo[i] for i in range(3)]

origins = {}  # (part, leg) -> [x,y,z] mm
for leg in LEG.values():
    hip_c, _ = group_bbox(groups[f"hip_{leg}"])
    origins[("hip", leg)] = hip_c
    wheel_c, _ = group_bbox(groups[f"wheel_{leg}"])
    origins[("wheel", leg)] = wheel_c
    # 膝关节 = 防油30202 轴承对中心（名字含 30202 / 96326CB9）
    bear = [c for n, _, c, _ in groups[f"calf_{leg}"] if "30202" in n or "96326CB9" in n or "KOYO" in n]
    if not bear:  # MIR 变体名被截断时按几何取膝部零件（轴承/垫套/销轴均在 z<260）
        bear = [c for _, _, c, _ in groups[f"calf_{leg}"] if c[2] < 260]
    origins[("calf", leg)] = [sum(x[i] for x in bear)/len(bear) for i in range(3)]
    # 大腿俯仰轴(估计) = thigh 组 bbox 中心 x、y，z 取 thigh 组 z 上端+30mm
    th_items = groups[f"thigh_{leg}"]
    th_c, th_s = group_bbox(th_items)
    origins[("thigh", leg)] = [th_c[0], th_c[1], th_c[2]-th_s[2]/2+30]

# ---- 导出 STL（mesh 坐标 = (全局mm - P_link)/1000，URDF 中 joint origin 用全局差）----
os.makedirs(MESH_ABS, exist_ok=True)
writer = StlAPI_Writer()
writer.ASCIIMode = False
for link, items in groups.items():
    if link == "base":
        P = [0.0, 0.0, 0.0]
    else:
        part, leg = link.split("_")
        P = origins[(part, leg)]
    comp = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(comp)
    for _, shape, _, _ in items:
        builder.Add(comp, shape)
    trsf_s = gp_Trsf()
    trsf_s.SetScaleFactor(0.001)
    trsf_t = gp_Trsf()
    trsf_t.SetTranslation(gp_Vec(-P[0]/1000.0, -P[1]/1000.0, -P[2]/1000.0))
    moved = BRepBuilderAPI_Transform(comp, trsf_t.Multiplied(trsf_s), True).Shape()
    BRepMesh_IncrementalMesh(moved, 0.001, False, 0.2, True)
    stl_name = "base" if link == "base" else f"link_{link.split('_')[1]}_{link.split('_')[0]}"
    path = f"{MESH_ABS}/{stl_name}.stl"
    writer.Write(moved, path)
    print(f"{link:12s} parts={len(items):2d} stl={os.path.getsize(path)//1024}KB P={P}", flush=True)

# ---- URDF ----
# 关节原点(全局, m)与父子
JOINTS = []  # (name, parent, child, P_child, axis, lower, upper)
for leg, hip in [("fl", "fl"), ("fr", "fr"), ("hl", "hl"), ("hr", "hr")]:
    JOINTS.append((f"joint_{leg}_hip", "base_link", f"link_{leg}_hip", origins[("hip", leg)], "1 0 0", -0.8, 0.8))
    JOINTS.append((f"joint_{leg}_thigh", f"link_{leg}_hip", f"link_{leg}_thigh", origins[("thigh", leg)], "0 1 0", -2.0, 2.5))
    JOINTS.append((f"joint_{leg}_calf", f"link_{leg}_thigh", f"link_{leg}_calf", origins[("calf", leg)], "0 1 0", -2.5, 0.5))
    JOINTS.append((f"joint_{leg}_wheel", f"link_{leg}_calf", f"link_{leg}_wheel", origins[("wheel", leg)], "0 1 0", None, None))

parent_P = {"base_link": [0.0, 0.0, 0.0]}
lines = ['<?xml version="1.0"?>', '<robot name="lingsi_d30w">',
         '  <!-- Auto-generated from D30W轮足外发.STEP by scripts/lingsi_d30w/step_to_urdf_d30w.py',
         '       坐标系: x=前(+), y=左(+), z=下(+)；STL 与 joint origin 单位 m；关节原点待实测标定 -->']
MASS = {"base": 15.0, "hip": 2.0, "thigh": 2.5, "calf": 2.0, "wheel": 3.0}
INERT = {"base": 0.15, "hip": 0.02, "thigh": 0.03, "calf": 0.03, "wheel": 0.02}

def link_xml(name, kind):
    m, i = MASS[kind], INERT[kind]
    return f"""  <link name="{name}">
    <visual>
      <geometry><mesh filename="{MESH_ABS}/{name if name != 'base_link' else 'base'}.stl" scale="1 1 1"/></geometry>
    </visual>
    <collision>
      <geometry><mesh filename="{MESH_ABS}/{name if name != 'base_link' else 'base'}.stl" scale="1 1 1"/></geometry>
    </collision>
    <inertial>
      <mass value="{m}"/>
      <inertia ixx="{i}" ixy="0" ixz="0" iyy="{i}" iyz="0" izz="{i}"/>
    </inertial>
  </link>"""

lines.append(link_xml("base_link", "base"))
for part in ("hip", "thigh", "calf", "wheel"):
    for leg in ("fl", "fr", "hl", "hr"):
        lines.append(link_xml(f"link_{leg}_{part}", part))

for name, parent, child, P, axis, lo, hi in JOINTS:
    Pp = parent_P[parent]
    rel = [(P[i]-Pp[i])/1000.0 for i in range(3)]
    parent_P[child] = P
    lim = f'<limit lower="{lo}" upper="{hi}" effort="60" velocity="25"/>' if lo is not None else \
          '<limit effort="60" velocity="25"/>'
    jtype = "revolute" if lo is not None else "continuous"
    lines.append(f"""  <joint name="{name}" type="{jtype}">
    <parent link="{parent}"/>
    <child link="{child}"/>
    <origin xyz="{rel[0]:.6f} {rel[1]:.6f} {rel[2]:.6f}" rpy="0 0 0"/>
    <axis xyz="{axis}"/>
    {lim}
  </joint>""")
lines.append("</robot>")

os.makedirs(f"{OUT}/urdf", exist_ok=True)
urdf_path = f"{OUT}/urdf/lingsi_d30w.urdf"
open(urdf_path, "w").write("\n".join(lines) + "\n")
print("URDF:", urdf_path, f"{os.path.getsize(urdf_path)//1024}KB")
json.dump({f"{k[0]}_{k[1]}": v for k, v in origins.items()}, open(f"{OUT}/joint_origins.json", "w"))
print("DONE")
