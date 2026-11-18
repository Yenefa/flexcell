"""Regression cases for archived packages leaking into active build discovery."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('repository_layout',Path(__file__).parents[1]/'check_repository_layout.py')
module=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(module)


class RepositoryLayoutTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.paths=[]
        self.layout=dict(ros_packages={'skill':'src/skill'},archive_roots=['archive'],modules=[])
        self.package('src/skill','skill');self.package('archive/snapshot','skill')
        (self.root/'archive/COLCON_IGNORE').touch()

    def package(self,path,name):
        directory=self.root/path;directory.mkdir(parents=True,exist_ok=True)
        (directory/'package.xml').write_text('<package><name>'+name+'</name></package>')
        self.paths.append(path+'/package.xml')

    def check(self):return module.audit(self.root,self.layout,self.paths)

    def write_configs(self,layout=None,baselines=None):
        config=self.root/'config';config.mkdir(exist_ok=True)
        (config/'repository_layout.json').write_text(
            json.dumps(self.layout if layout is None else layout))
        (config/'version_baselines.json').write_text(
            json.dumps({'checkpoints':{}} if baselines is None else baselines))

    def run_main(self,*extra):
        out=io.StringIO();err=io.StringIO()
        with patch.object(module,'tracked_manifests',return_value=['src/skill/package.xml']), \
                contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            code=module.main(['--root',str(self.root),*extra])
        return code,out.getvalue(),err.getvalue()

    def test_archived_duplicate_is_excluded_without_deleting_it(self):
        report=self.check()
        self.assertTrue(report['passed']);self.assertEqual(len(report['packages']),1)
        self.assertEqual(report['ignored_archive_packages'],['archive/snapshot/package.xml'])
        self.assertTrue((self.root/'archive/snapshot/package.xml').is_file())

    def test_missing_archive_marker_rejects_duplicate_discovery(self):
        (self.root/'archive/COLCON_IGNORE').unlink();report=self.check()
        self.assertFalse(report['passed'])
        self.assertTrue(any('duplicate' in p for p in report['problems']))

    def test_undeclared_live_package_is_rejected(self):
        self.package('copied_workspace/pkg','other')
        self.assertFalse(self.check()['passed'])

    def test_declared_package_cannot_be_silently_ignored(self):
        (self.root/'src/skill/COLCON_IGNORE').touch()
        self.assertFalse(self.check()['passed'])

    def test_package_name_drift_is_rejected(self):
        (self.root/'src/skill/package.xml').write_text('<package><name>renamed</name></package>')
        self.assertFalse(self.check()['passed'])

    def test_git_enumeration_failure_keeps_diagnostic(self):
        with self.assertRaisesRegex(RuntimeError,'git ls-files failed:'):
            module.tracked_manifests(self.root)

    def test_real_discovery_accepts_registry_mapping_keys_as_names(self):
        reply=SimpleNamespace(returncode=0,stdout='skill\n',stderr='')
        with patch.object(module.subprocess,'run',return_value=reply):
            self.assertTrue(module.check_colcon(self.root,'colcon',self.layout['ros_packages'])['passed'])

    def test_real_discovery_rejects_duplicate_names(self):
        reply=SimpleNamespace(returncode=0,stdout='skill\nskill\n',stderr='')
        with patch.object(module.subprocess,'run',return_value=reply):
            self.assertFalse(module.check_colcon(self.root,'colcon',self.layout['ros_packages'])['passed'])

    def test_missing_layout_config_exits_2(self):
        code,out,err=self.run_main()
        self.assertEqual((code,out),(2,''))
        self.assertIn('cannot read config',err);self.assertNotIn('Traceback',err)

    def test_malformed_layout_exits_2(self):
        for layout in ({}, {'ros_packages':{}}, {'ros_packages':{'skill':''}},
                       {'ros_packages':{'skill':'src/skill'},'archive_roots':[],
                        'modules':[{'id':'empty','paths':[]}]}):
            with self.subTest(layout=layout):
                self.write_configs(layout=layout)
                code,_,err=self.run_main()
                self.assertEqual(code,2);self.assertNotIn('Traceback',err)

    def test_missing_baseline_config_exits_2(self):
        config=self.root/'config';config.mkdir()
        (config/'repository_layout.json').write_text(json.dumps(self.layout))
        code,_,err=self.run_main()
        self.assertEqual(code,2);self.assertIn('version_baselines.json',err)

    def test_checkpoint_without_report_exits_2(self):
        self.write_configs(baselines={'checkpoints':{'t08':{'executed_source_commit':'0'*40}}})
        code,_,err=self.run_main()
        self.assertEqual(code,2);self.assertIn('t08',err)

    def test_git_enumeration_failure_exits_2_with_diagnostic(self):
        self.write_configs()
        with patch.object(module,'tracked_manifests',
                          side_effect=RuntimeError('git ls-files failed: boom')):
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()) as err:
                code=module.main(['--root',str(self.root)])
        self.assertEqual(code,2);self.assertIn('git ls-files failed: boom',err.getvalue())

    def test_colcon_timeout_and_missing_binary_are_reported(self):
        cases=(subprocess.TimeoutExpired('colcon',1.),FileNotFoundError(2,'No such file','colcon'))
        for exc in cases:
            with self.subTest(exc=type(exc).__name__):
                with patch.object(module.subprocess,'run',side_effect=exc):
                    actual=module.check_colcon(self.root,'colcon',['skill'],1.)
                self.assertFalse(actual['passed'])
                self.assertIn('error',actual)

    def test_main_reports_colcon_timeout_as_exit_1(self):
        self.write_configs()
        with patch.object(module.subprocess,'run',side_effect=subprocess.TimeoutExpired('colcon',1.)):
            code,out,err=self.run_main('--colcon','colcon','--colcon-timeout','1')
        self.assertEqual((code,err),(1,''))
        report=json.loads(out)
        self.assertFalse(report['colcon_check']['passed'])
        self.assertIn('timed out',report['colcon_check']['error'])
        self.assertTrue(any('colcon package discovery' in p for p in report['problems']))

    def test_non_positive_colcon_timeout_exits_2(self):
        self.write_configs()
        code,_,err=self.run_main('--colcon-timeout','0')
        self.assertEqual(code,2);self.assertIn('--colcon-timeout',err)

    def test_unwritable_out_exits_2(self):
        self.write_configs()
        code,_,err=self.run_main('--out',str(self.root))
        self.assertEqual(code,2);self.assertIn('cannot write',err)

    def test_valid_root_exits_0(self):
        self.write_configs()
        code,out,err=self.run_main()
        self.assertEqual((code,err),(0,''))
        self.assertTrue(json.loads(out)['passed'])


if __name__=='__main__':unittest.main()
