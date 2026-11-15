import json, tempfile, unittest
from pathlib import Path
from lab.promotion import setup,prepare,execute,read,atomic,canonical,digest

class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        setup(self.root)
    def candidate(self, operation='release', source='2'*40):
        path = self.root / (operation + '.json')
        sha = prepare(self.root, source, operation, path)
        return path, sha
    def test_release_and_exact_rollback_preserve_settings(self):
        initial = read(self.root/'runtime.json')
        path, sha = self.candidate()
        execute(self.root,path,sha)
        path, sha = self.candidate('rollback','1'*40)
        result = execute(self.root,path,sha)
        self.assertEqual(read(self.root/'runtime.json')['active'],initial['active'])
        self.assertTrue(result['settings_preserved'])
    def test_wrong_approval_and_duplicate_execution_rejected(self):
        path, sha = self.candidate()
        with self.assertRaisesRegex(ValueError,'exact candidate'):execute(self.root,path,'0'*64)
        execute(self.root,path,sha)
        with self.assertRaisesRegex(ValueError,'Runtime changed'):execute(self.root,path,sha)
    def test_drift_rejected(self):
        path, sha = self.candidate()
        state=read(self.root/'runtime.json');state['settings']['email']=True
        atomic(self.root/'runtime.json',state)
        with self.assertRaisesRegex(ValueError,'Runtime changed'):execute(self.root,path,sha)
    def test_package_tamper_rejected(self):
        path, sha = self.candidate()
        (self.root/'archive'/('2'*40)/'api.zip').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):execute(self.root,path,sha)
    def test_schema_conflict_rejected(self):
        state=read(self.root/'runtime.json');state['schema']=2
        atomic(self.root/'runtime.json',state)
        with self.assertRaisesRegex(ValueError,'Schema compatibility'):self.candidate()
    def test_expired_candidate_rejected(self):
        path, sha = self.candidate()
        data=read(path);data['created']=0;data['expires']=1
        path.write_bytes(canonical(data))
        with self.assertRaisesRegex(ValueError,'expired'):execute(self.root,path,digest(path.read_bytes()))
    def test_concurrent_publication_lock_rejected(self):
        path, sha = self.candidate()
        lock=self.root/'.publication.lock';lock.touch()
        with self.assertRaises(FileExistsError):execute(self.root,path,sha)
        self.assertTrue(lock.exists())
    def test_same_target_rejected(self):
        with self.assertRaisesRegex(ValueError,'already selected'):self.candidate(source='1'*40)

if __name__=='__main__':unittest.main()
