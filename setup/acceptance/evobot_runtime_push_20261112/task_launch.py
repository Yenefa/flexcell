"""Task-scoped Runtime launch; shipped launch files remain unchanged."""
import ast
import hashlib
from pathlib import Path


def materialize(launch_directory,out,backend):
    directory=Path(launch_directory);out=Path(out)
    week=directory/'week1.launch.py';original=directory/'trusted_sim.launch.py'
    tree=ast.parse(week.read_text());seen=[]
    removed={'pick_server','place_server','verify_server'}
    if backend=='finger_tcp':removed.add('push_server')
    class Select(ast.NodeTransformer):
        def visit_Call(self,node):
            if isinstance(node.func,ast.Name) and node.func.id=='Node':
                name=next(k.value.value for k in node.keywords if k.arg=='name')
                seen.append(name)
                if name in removed:return None
            return self.generic_visit(node)
    tree=Select().visit(tree)
    if set(seen)!={'observe_server','carry_server','push_server','task_fsm_server','pick_server','place_server','verify_server'}:
        raise ValueError('unexpected installed skill graph')
    if backend=='finger_tcp':
        launch=next(n for n in ast.walk(tree) if isinstance(n,ast.Call)
                    and isinstance(n.func,ast.Name) and n.func.id=='LaunchDescription')
        launch.args[0].elts.append(ast.parse("Node(package='flexcell_skills', executable='contact_push_server', name='contact_push_server', output='screen', parameters=[LaunchConfiguration('params_file')])",mode='eval').body)
    ast.fix_missing_locations(tree)
    scoped=out/'runtime_week1.launch.py';scoped.write_text(ast.unparse(tree)+'\n')
    needle="str(skills / 'launch/week1.launch.py')";source=original.read_text()
    if source.count(needle)!=1:raise ValueError('unexpected trusted_sim include')
    task=out/'runtime_sim.launch.py';task.write_text(source.replace(needle,repr(str(scoped))))
    for p in (task,scoped):compile(p.read_text(),str(p),'exec')
    return task,dict(kind='TASK_SCOPED_RUNTIME_LAUNCH',backend=backend,
        retained=sorted((set(seen)-removed)|({'contact_push_server'} if backend=='finger_tcp' else set())),
        removed_unused=sorted(removed),
        coordinator_clock='task_fsm and ContactPush coordinator use wall clock; worker uses simulation clock',
        sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (week,original,scoped,task)})
