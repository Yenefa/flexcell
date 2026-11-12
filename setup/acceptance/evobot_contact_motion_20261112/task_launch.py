"""Generate a task-scoped copy of the pinned launch; installed defaults stay intact."""
import ast
import hashlib
from pathlib import Path


REMOVED={'pick_server','place_server','verify_server','task_fsm_server'}
RETAINED={'observe_server','carry_server','push_server'}


def materialize(launch_directory,out):
    launch_directory=Path(launch_directory);out=Path(out)
    original=launch_directory/'trusted_sim.launch.py';week=launch_directory/'week1.launch.py'
    source=week.read_text();tree=ast.parse(source)
    def server(node):
        if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Name) or node.func.id!='Node':return None
        name=next((k.value for k in node.keywords if k.arg=='name'),None)
        if not isinstance(name,ast.Constant) or not isinstance(name.value,str):raise ValueError('unpinned server declaration')
        return name.value
    before=[server(n) for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='Node']
    if set(before)!=REMOVED|RETAINED or len(before)!=7:raise ValueError('unexpected pinned week1 graph')
    class Filter(ast.NodeTransformer):
        def visit_Call(self,node):
            if server(node) in REMOVED:return None
            return self.generic_visit(node)
    tree=Filter().visit(tree);ast.fix_missing_locations(tree)
    scoped=out/'contact_week1.launch.py'
    scoped.write_text(ast.unparse(tree)+'\n')
    source=original.read_text();needle="str(skills / 'launch/week1.launch.py')"
    if source.count(needle)!=1:raise ValueError('unexpected pinned trusted_sim include')
    task=out/'contact_sim.launch.py';task.write_text(source.replace(needle,repr(str(scoped))))
    compile(task.read_text(),str(task),'exec');compile(scoped.read_text(),str(scoped),'exec')
    return task,dict(kind='TASK_SCOPED_LAUNCH',retained=sorted(RETAINED),removed_unused=sorted(REMOVED),
        physics_robot_controllers_and_moveit_launch='unchanged; only week1 include replaced',
        sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (original,week,task,scoped)})
