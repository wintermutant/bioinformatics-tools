"""
Tests for WorkflowBase: _run_subprocess, build_executable,
_parse_snakemake_output, _run_pipeline, do_quick_example, do_fresh_test.

All tests are mocked — no snakemake installation required.
"""
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from bioinformatics_tools.workflow_tools.workflow import WorkflowBase, workflow_keys


# ---------------------------------------------------------------------------
# Fixture: create a WorkflowBase without triggering CLI __init__
# ---------------------------------------------------------------------------

@pytest.fixture
def wf():
    """Build a WorkflowBase instance without CLI init."""
    obj = WorkflowBase.__new__(WorkflowBase)
    conf = MagicMock()
    conf.get = MagicMock(side_effect=lambda key, default=None: {
        'margie_db': '/tmp/test-margie.db',
    }.get(key, default))
    obj.conf = conf
    obj.report = None
    obj.workflow_id = 'test'
    obj.timestamp = '010101-0000'
    return obj


# ---------------------------------------------------------------------------
# _parse_snakemake_output
# ---------------------------------------------------------------------------

class TestParseSnakemakeOutput:

    def test_parses_failed_rules(self):
        stderr = (
            "Error in rule run_pfam:\n"
            "    some details\n"
            "Error in rule run_cog:\n"
            "    more details\n"
            "2 of 5 steps (40%) done\n"
        )
        result = WorkflowBase._parse_snakemake_output(stderr)
        assert result['completed'] == 2
        assert result['total'] == 5
        assert result['failed'] == 2
        assert set(result['failed_rules']) == {'run_pfam', 'run_cog'}

    def test_full_success(self):
        stderr = "5 of 5 steps (100%) done\n"
        result = WorkflowBase._parse_snakemake_output(stderr)
        assert result['completed'] == 5
        assert result['total'] == 5
        assert result['failed'] == 0
        assert result['failed_rules'] == []

    def test_empty_stderr(self):
        result = WorkflowBase._parse_snakemake_output("")
        assert result == {'total': 0, 'completed': 0, 'failed': 0, 'failed_rules': []}

    def test_failed_rules_without_steps_line(self):
        stderr = "Error in rule step_flaky:\n    jobid: 2\n"
        result = WorkflowBase._parse_snakemake_output(stderr)
        assert result['failed_rules'] == ['step_flaky']
        assert result['failed'] == 1
        # total estimated from completed (0) + failed (1)
        assert result['total'] == 1


# ---------------------------------------------------------------------------
# _run_subprocess
# ---------------------------------------------------------------------------

class TestRunSubprocess:

    def test_success_returns_completed_process(self, wf):
        fake = subprocess.CompletedProcess(args=['snakemake'], returncode=0, stdout='ok\n', stderr='')
        with patch('bioinformatics_tools.workflow_tools.workflow.subprocess.run', return_value=fake):
            result = wf._run_subprocess(['snakemake', '-s', 'test.smk'])
        assert result is fake
        assert result.returncode == 0

    def test_nonzero_still_returns(self, wf):
        fake = subprocess.CompletedProcess(args=['snakemake'], returncode=1, stdout='', stderr='Error in rule x:\n')
        with patch('bioinformatics_tools.workflow_tools.workflow.subprocess.run', return_value=fake):
            result = wf._run_subprocess(['snakemake', '-s', 'test.smk'])
        assert result is fake
        assert result.returncode == 1

    def test_launch_failure_returns_none(self, wf):
        with patch('bioinformatics_tools.workflow_tools.workflow.subprocess.run',
                   side_effect=FileNotFoundError('snakemake not found')):
            result = wf._run_subprocess(['snakemake', '-s', 'test.smk'])
        assert result is None
        # failed() should have been called
        assert wf.report is not None
        assert wf.report.status.indicates_failure


# ---------------------------------------------------------------------------
# build_executable
# ---------------------------------------------------------------------------

class TestBuildExecutable:

    def test_has_keep_going(self, wf):
        key = workflow_keys['selftest']
        cmd = wf.build_executable(key, mode='dev')
        assert '--keep-going' in cmd

    def test_dev_mode_no_slurm_executor(self, wf):
        key = workflow_keys['selftest']
        cmd = wf.build_executable(key, mode='dev')
        assert '--executor=slurm' not in cmd

    def test_non_dev_has_slurm_executor(self, wf):
        key = workflow_keys['selftest']
        cmd = wf.build_executable(key, mode='notdev')
        # Should appear exactly once
        assert cmd.count('--executor=slurm') == 1

    def test_config_dict_appended(self, wf):
        key = workflow_keys['selftest']
        cmd = wf.build_executable(key, config_dict={'foo': 'bar', 'baz': '42'}, mode='dev')
        assert '--config' in cmd
        idx = cmd.index('--config')
        assert 'foo=bar' in cmd[idx + 1:]
        assert 'baz=42' in cmd[idx + 1:]

    def test_dev_mode_no_default_resources(self, wf):
        key = workflow_keys['selftest']
        cmd = wf.build_executable(key, mode='dev')
        assert '--default-resources' not in cmd


# ---------------------------------------------------------------------------
# _run_pipeline
# ---------------------------------------------------------------------------

class TestRunPipeline:

    def test_unknown_key_fails(self, wf):
        ret = wf._run_pipeline('nonexistent_workflow', {})
        assert ret == 1
        assert wf.report is not None
        assert wf.report.status.indicates_failure

    @patch('bioinformatics_tools.workflow_tools.workflow.cache_sif_files')
    def test_success_path(self, mock_cache, wf):
        fake_proc = subprocess.CompletedProcess(
            args=['snakemake'], returncode=0,
            stdout='Building DAG\n', stderr='5 of 5 steps (100%) done\n',
        )
        with patch.object(wf, '_run_subprocess', return_value=fake_proc):
            wf._run_pipeline('example', {'input_fasta': 'test.fa'})

        assert wf.report is not None
        assert wf.report.status.indicates_success
        assert wf.report.data['workflow'] == 'example'
        assert wf.report.data['returncode'] == 0
        assert wf.report.data['rules_summary']['completed'] == 5

    @patch('bioinformatics_tools.workflow_tools.workflow.cache_sif_files')
    def test_failure_path_does_not_call_succeeded(self, mock_cache, wf):
        """Regression test: when snakemake fails, self.succeeded() must NOT be called."""
        fake_proc = subprocess.CompletedProcess(
            args=['snakemake'], returncode=1,
            stdout='', stderr='Error in rule run_pfam:\n    jobid: 3\n1 of 3 steps (33%) done\n',
        )
        with patch.object(wf, '_run_subprocess', return_value=fake_proc):
            ret = wf._run_pipeline('example', {'input_fasta': 'test.fa'})

        assert ret == 1
        assert wf.report.status.indicates_failure
        assert wf.report.data['rules_summary']['failed_rules'] == ['run_pfam']

    @patch('bioinformatics_tools.workflow_tools.workflow.cache_sif_files')
    def test_launch_failure_returns_early(self, mock_cache, wf):
        with patch.object(wf, '_run_subprocess', return_value=None):
            ret = wf._run_pipeline('example', {'input_fasta': 'test.fa'})
        assert ret == 1

    @patch('bioinformatics_tools.workflow_tools.workflow.cache_sif_files')
    @patch('bioinformatics_tools.workflow_tools.workflow.log_workflow_run')
    @patch('bioinformatics_tools.workflow_tools.workflow.store_all')
    def test_store_all_skipped_on_failure(self, mock_store, mock_log, mock_cache, wf):
        fake_proc = subprocess.CompletedProcess(
            args=['snakemake'], returncode=1, stdout='', stderr='Error in rule x:\n',
        )
        cache_map = {'prodigal': ['out.tkn']}
        smk_config = {'input_fasta': 'test.fa', 'margie_db': '/tmp/test.db'}
        with patch.object(wf, '_run_subprocess', return_value=fake_proc):
            wf._run_pipeline('example', smk_config, cache_map)
        mock_store.assert_not_called()
        mock_log.assert_called_once()
        assert mock_log.call_args.kwargs['status'] == 'failed'

    @patch('bioinformatics_tools.workflow_tools.workflow.cache_sif_files')
    @patch('bioinformatics_tools.workflow_tools.workflow.log_workflow_run')
    @patch('bioinformatics_tools.workflow_tools.workflow.store_all')
    @patch('bioinformatics_tools.workflow_tools.workflow.restore_all', return_value={})
    def test_store_all_called_on_success(self, mock_restore, mock_store, mock_log, mock_cache, wf):
        fake_proc = subprocess.CompletedProcess(
            args=['snakemake'], returncode=0, stdout='', stderr='',
        )
        cache_map = {'prodigal': ['out.tkn']}
        smk_config = {'input_fasta': 'test.fa', 'margie_db': '/tmp/test.db'}
        with patch.object(wf, '_run_subprocess', return_value=fake_proc):
            wf._run_pipeline('example', smk_config, cache_map)
        mock_store.assert_called_once()
        mock_log.assert_called_once()
        assert mock_log.call_args.kwargs['status'] == 'success'

    def test_selftest_skips_cache_sif(self, wf):
        """selftest has empty sif_files, so cache_sif_files should not be called."""
        fake_proc = subprocess.CompletedProcess(
            args=['snakemake'], returncode=0, stdout='', stderr='',
        )
        with patch('bioinformatics_tools.workflow_tools.workflow.cache_sif_files') as mock_cache, \
             patch.object(wf, '_run_subprocess', return_value=fake_proc):
            wf._run_pipeline('selftest', {'workdir': '/tmp'}, mode='dev')
        mock_cache.assert_not_called()

    @patch('bioinformatics_tools.workflow_tools.workflow.cache_sif_files',
           side_effect=__import__('bioinformatics_tools.workflow_tools.bapptainer',
                                  fromlist=['CacheSifError']).CacheSifError('download failed'))
    def test_cache_sif_failure(self, mock_cache, wf):
        ret = wf._run_pipeline('example', {'input_fasta': 'test.fa'})
        assert ret == 1
        assert wf.report.status.indicates_failure

    @patch('bioinformatics_tools.workflow_tools.workflow.log_workflow_run')
    @patch('bioinformatics_tools.workflow_tools.workflow.store_all')
    @patch('bioinformatics_tools.workflow_tools.workflow.restore_all', return_value={})
    def test_pipeline_with_input_file_key(self, mock_restore, mock_store, mock_log, wf):
        """_run_pipeline uses input_file key when input_fasta is absent (selftest path)."""
        fake_proc = subprocess.CompletedProcess(
            args=['snakemake'], returncode=0, stdout='', stderr='',
        )
        cache_map = {'step_a': ['step_a/sample-a-step_a.out']}
        smk_config = {'input_file': '/tmp/sample-a.txt', 'margie_db': '/tmp/sample.db'}
        with patch.object(wf, '_run_subprocess', return_value=fake_proc):
            wf._run_pipeline('selftest', smk_config, cache_map, mode='dev')
        mock_restore.assert_called_once_with('/tmp/sample.db', '/tmp/sample-a.txt', cache_map)
        mock_log.assert_called_once()
        assert mock_log.call_args.kwargs['status'] == 'success'


# ---------------------------------------------------------------------------
# do_quick_example
# ---------------------------------------------------------------------------

class TestDoQuickExample:

    @patch('bioinformatics_tools.workflow_tools.workflow.log_workflow_run')
    @patch('bioinformatics_tools.workflow_tools.workflow.store_all')
    @patch('bioinformatics_tools.workflow_tools.workflow.restore_all', return_value={
        'step_a': True, 'step_a_db': True,
        'step_b': True, 'step_b_db': True,
        'step_c': True, 'step_c_db': True,
    })
    def test_quick_example_passes_cache_map(self, mock_restore, mock_store, mock_log, wf):
        """do_quick_example should call _run_pipeline with a cache_map matching the step keys."""
        fake_proc = subprocess.CompletedProcess(
            args=['snakemake'], returncode=0, stdout='', stderr='',
        )
        with patch.object(wf, '_run_subprocess', return_value=fake_proc):
            wf.do_quick_example()

        # restore_all was called with a cache_map containing all step keys
        call_args = mock_restore.call_args
        cache_map = call_args[0][2]
        assert set(cache_map.keys()) == {
            'step_a', 'step_a_db', 'step_b', 'step_b_db', 'step_c', 'step_c_db',
        }
        # Each value should be a list of output path strings
        assert len(cache_map['step_a']) == 2  # .out and .extra
        assert len(cache_map['step_c']) == 2  # .tsv and _count.tsv

        # store_all and log_workflow_run should both be called on success
        mock_store.assert_called_once()
        mock_log.assert_called_once()
        assert mock_log.call_args.kwargs['status'] == 'success'

    def test_quick_example_uses_selftest_workflow_key(self, wf):
        """do_quick_example runs the 'selftest' workflow key (no sif files)."""
        fake_proc = subprocess.CompletedProcess(
            args=['snakemake'], returncode=0, stdout='', stderr='',
        )
        with patch('bioinformatics_tools.workflow_tools.workflow.restore_all', return_value={}), \
             patch('bioinformatics_tools.workflow_tools.workflow.store_all'), \
             patch.object(wf, '_run_subprocess', return_value=fake_proc) as mock_sub, \
             patch('bioinformatics_tools.workflow_tools.workflow.cache_sif_files') as mock_cache:
            wf.do_quick_example()

        # selftest has no sif_files, so cache_sif_files should not be called
        mock_cache.assert_not_called()
        # _run_subprocess was called (snakemake command was built)
        mock_sub.assert_called_once()


# ---------------------------------------------------------------------------
# do_fresh_test
# ---------------------------------------------------------------------------

class TestDoFreshTest:

    @patch('bioinformatics_tools.workflow_tools.workflow.log_workflow_run')
    @patch('bioinformatics_tools.workflow_tools.workflow.store_all')
    @patch('bioinformatics_tools.workflow_tools.workflow.restore_all', return_value={})
    def test_fresh_test_uses_cache_map(self, mock_restore, mock_store, mock_log, wf):
        """do_fresh_test passes cache_map and uses real margie_db for store/restore."""
        fake_proc = subprocess.CompletedProcess(
            args=['snakemake'], returncode=0, stdout='', stderr='',
        )
        with patch.object(wf, '_run_subprocess', return_value=fake_proc):
            wf.do_fresh_test()

        # restore_all, store_all, and log_workflow_run should all be called on success
        mock_restore.assert_called_once()
        mock_store.assert_called_once()
        mock_log.assert_called_once()
        assert mock_log.call_args.kwargs['status'] == 'success'

        # cache_map should have all step keys
        cache_map = mock_restore.call_args[0][2]
        assert set(cache_map.keys()) == {
            'step_a', 'step_a_db', 'step_b', 'step_b_db', 'step_c', 'step_c_db',
        }

    @patch('bioinformatics_tools.workflow_tools.workflow.store_all')
    @patch('bioinformatics_tools.workflow_tools.workflow.restore_all', return_value={})
    def test_fresh_test_passes_inject_failure(self, mock_restore, mock_store, wf):
        """do_fresh_test should pass inject_failure through to smk_config."""
        fake_proc = subprocess.CompletedProcess(
            args=['snakemake'], returncode=0, stdout='', stderr='',
        )
        with patch.object(wf, '_run_subprocess', return_value=fake_proc) as mock_sub:
            wf.do_fresh_test(inject_failure=True)

        # Check the snakemake command includes inject_failure=true in config
        cmd = mock_sub.call_args[0][0]
        config_str = ' '.join(cmd)
        assert 'inject_failure=true' in config_str

    @patch('bioinformatics_tools.workflow_tools.workflow.store_all')
    @patch('bioinformatics_tools.workflow_tools.workflow.restore_all', return_value={})
    def test_fresh_test_runs_selftest_key(self, mock_restore, mock_store, wf):
        """do_fresh_test uses the 'selftest' workflow key."""
        fake_proc = subprocess.CompletedProcess(
            args=['snakemake'], returncode=0, stdout='', stderr='',
        )
        with patch.object(wf, '_run_subprocess', return_value=fake_proc) as mock_sub:
            wf.do_fresh_test()

        cmd = mock_sub.call_args[0][0]
        # Should reference selftest.smk
        assert any('selftest.smk' in arg for arg in cmd)


# ---------------------------------------------------------------------------
# _build_result
# ---------------------------------------------------------------------------

class TestBuildResult:

    def test_builds_structured_dict(self, wf):
        proc = subprocess.CompletedProcess(
            args=['snakemake'], returncode=1,
            stdout='some output', stderr='Error in rule bad_rule:\n2 of 3 steps (66%) done\n',
        )
        result = wf._build_result('margie', proc)
        assert result['workflow'] == 'margie'
        assert result['returncode'] == 1
        assert result['rules_summary']['failed_rules'] == ['bad_rule']
        assert result['rules_summary']['completed'] == 2
        assert 'some output' in result['stdout_tail']
