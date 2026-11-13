"""Regression cases for archived packages leaking into active build discovery."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

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


if __name__=='__main__':unittest.main()
