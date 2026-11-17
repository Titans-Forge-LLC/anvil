import contextlib,io,json,os,subprocess,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
from anvil_workbench import pre_draft

class CompactTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name);self.root=self.dir/'repo';self.root.mkdir()
        self.git('init','-q');self.git('config','user.name','Synthetic');self.git('config','user.email','synthetic@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        (self.root/'a.py').write_bytes(b'a = 1\nb = 2\nc = 3\n')
        (self.root/'task.txt').write_text('long task text should not be emitted')
        (self.root/'notes.txt').write_text('long historical content should not be emitted')
        self.git('add','.');self.git('commit','-qm','synthetic base')
        (self.root/'a.py').write_bytes(b'a = 1\nb = 9\nc = 3\n')
        self.handoff=self.dir/'handoff.json'
    def git(self,*args):
        return subprocess.run(['git',*args],cwd=self.root,check=True,capture_output=True)
    def capture(self,**kwargs):
        return pre_draft.capture(self.root,'task.txt',['notes.txt'],self.handoff,**kwargs)
    def compact(self):
        return pre_draft._compact_view(self.root,pre_draft.inspect(self.root,self.handoff,show_content=True))
    def test_exact_recorded_hints_and_current_line_no_payload(self):
        command='python3 -m unittest tests.test_thing -v; echo "not executed"'
        self.capture(failed_check=command,dead_end='Do not retry the rejected regex-only patch')
        text=self.compact();lines=text.splitlines();self.assertEqual(len(lines),4)
        self.assertIn('"a.py:2"',lines[1]);self.assertEqual(json.loads(lines[2].split(': ',1)[1]),command)
        self.assertIn('recorded',lines[2]);self.assertIn('recorded',lines[3]);self.assertNotIn('long task',text);self.assertNotIn('long historical',text)
    def test_v1_packet_compatible_and_no_invented_check(self):
        self.capture();packet=json.loads(self.handoff.read_text());self.assertEqual(packet['body']['schema'],'anvil-predraft-v1')
        self.assertIn('failed-check (recorded): "unavailable"',self.compact())
        self.assertNotIn('historical_continuation',pre_draft.inspect(self.root,self.handoff))
    def test_stale_shows_new_dirty_location(self):
        self.capture(failed_check='python3 -m unittest')
        (self.root/'a.py').write_bytes(b'a = 1\nb = 2\nc = 4\n')
        text=self.compact();self.assertIn('state: stale',text);self.assertIn('"a.py:3"',text);self.assertNotIn('"a.py:2"',text)
    def test_staged_untracked_and_deleted(self):
        self.capture();self.git('add','a.py');(self.root/'notes.txt').unlink();(self.root/'new.py').write_text('x=1\n')
        text=self.compact();self.assertIn('"a.py:2"',text);self.assertIn('"notes.txt:?"',text);self.assertIn('"new.py:1"',text)
    def test_binary_location_unknown_and_literal_pathspec(self):
        name='[glob].py' if os.name == 'nt' else ':(glob)*.py'
        (self.root/name).write_bytes(b'x=1\n');(self.root/'image.bin').write_bytes(b'\x00a')
        self.git('add','.');self.git('commit','-qm','add fixtures')
        (self.root/name).write_bytes(b'x=2\n');(self.root/'image.bin').write_bytes(b'\x00b')
        self.capture();text=self.compact();self.assertIn(json.dumps(name+':1'),text);self.assertIn('"image.bin:?"',text)
    def test_only_first_sixteen_dirty_files_are_diffed(self):
        self.capture();result=pre_draft.inspect(self.root,self.handoff,show_content=True)
        state=dict(result['current_git']);state['status']=[{'path':str(n)+'.py','status':' M'} for n in range(20)];result['current_git']=state
        with patch.object(pre_draft,'_git',return_value=b'@@ -1 +2 @@\n') as git,patch.object(pre_draft,'_state',return_value=state):
            text=pre_draft._compact_view(self.root,result)
        self.assertEqual(git.call_count,16);self.assertIn('+4 dirty files; inspect Git',text)
    def test_hints_private_unless_content_requested(self):
        self.capture(failed_check='private check',dead_end='private dead end')
        result=pre_draft.inspect(self.root,self.handoff);self.assertNotIn('private check',json.dumps(result));self.assertNotIn('historical_continuation',result)
    def test_refuse_multiline_and_escape_terminal_controls_in_paths(self):
        for value in ('a\nb','a\rb','a\x1bb','a\x00b'):
            with self.assertRaises(ValueError): self.capture(failed_check=value)
        if os.name == 'nt':
            return  # Windows rejects terminal-control characters in filenames.
        name='new\x1b.py';(self.root/name).write_text('x=1')
        self.capture(failed_check='python3 -m unittest');text=self.compact();self.assertNotIn('\x1b',text);self.assertIn('\\u001b',text)
    def test_corrupt_hints_fail_closed(self):
        self.capture(failed_check='python3 -m unittest');p=json.loads(self.handoff.read_text());p['body']['continuation']['failed_check']='x\ny';p['checksum_sha256']=pre_draft._digest(pre_draft._canonical(p['body']));self.handoff.write_text(json.dumps(p))
        with self.assertRaises(ValueError):pre_draft.inspect(self.root,self.handoff)
    def test_cli_compact_only_four_lines_and_no_execution(self):
        marker=self.root/'never-created';check='touch '+str(marker)
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(pre_draft.main(['capture','--project-root',str(self.root),'--task-file','task.txt','--output',str(self.handoff),'--failed-check',check,'--dead-end','skip bogus fix']),0)
        out=io.StringIO()
        with contextlib.redirect_stdout(out):self.assertEqual(pre_draft.main(['inspect','--project-root',str(self.root),'--handoff',str(self.handoff),'--compact']),0)
        self.assertEqual(len(out.getvalue().splitlines()),4);self.assertFalse(marker.exists())
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):pre_draft.main(['inspect','--project-root',str(self.root),'--handoff',str(self.handoff),'--compact','--show-content'])

if __name__=='__main__':unittest.main(verbosity=2)
