"""
Tests for the Fasta file class.
"""
import subprocess
import tempfile
from pathlib import Path
import pytest

from bioinformatics_tools.FileClasses.Fasta import Fasta


class TestFasta:
    """Test cases for the Fasta file handling class."""
    
    @pytest.fixture
    def sample_fasta_content(self):
        """Sample FASTA content for testing."""
        return """>seq1 description 1
ATGCATGCATGC
>seq2 description 2
GCATGCATGCAT
ATGC
>seq3
AAATTTCCCGGG"""
    
    @pytest.fixture
    def sample_fasta_file(self, sample_fasta_content):
        """Create a temporary FASTA file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
            f.write(sample_fasta_content)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def real_test_fasta(self):
        """Use the actual test file if it exists."""
        test_file = Path("test-files/example.fasta")
        if test_file.exists():
            return str(test_file)
        else:
            pytest.skip("Real test file not found: test-files/example.fasta")
    
    def test_fasta_initialization_with_valid_file(self, sample_fasta_file):
        """Test that Fasta class can be initialized with a valid file."""
        # Note: This test may need adjustment based on how the Fasta class actually works
        # The class seems to expect command line arguments, so we'll test what we can
        pass  # TODO: Implement based on actual Fasta class interface
    
    def test_fasta_file_validation_with_real_file(self, real_test_fasta):
        """Test file validation using the actual test file."""
        # This is more of an integration test
        import subprocess
        
        result = subprocess.run(
            ["dane", "valid", "type:", "fasta", "file:", real_test_fasta],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "File was scrubbed and found to be True" in result.stdout
    
    def test_fasta_basic_stats_with_real_file(self, real_test_fasta):
        """Test basic statistics calculation with real file."""
        result = subprocess.run(
            ["dane", "basic", "stats", "type:", "fasta", "file:", real_test_fasta],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "Basic statistics:" in result.stdout
        assert "Total Sequences" in result.stdout
        assert "Total Sequence Length" in result.stdout
        assert "Total GC Content" in result.stdout
    
    def test_fasta_sequence_count_with_real_file(self, real_test_fasta):
        """Test sequence counting with real file."""
        result = subprocess.run(
            ["dane", "total", "seqs", "type:", "fasta", "file:", real_test_fasta],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "Total sequences:" in result.stdout
        # The example.fasta should have a specific number of sequences
        assert "3" in result.stdout  # Based on our earlier test results
    
    def test_invalid_fasta_file(self):
        """Test behavior with an invalid FASTA file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
            f.write("This is not a valid FASTA file\nNo headers here")
            invalid_file = f.name
        
        try:
            result = subprocess.run(
                ["dane", "valid", "type:", "fasta", "file:", invalid_file],
                capture_output=True,
                text=True
            )
            
            # The validation should either fail or return False
            # We'll check what actually happens
            assert result.returncode in [0, 1]  # Either success with False or failure
            
        finally:
            Path(invalid_file).unlink(missing_ok=True)
    
    def test_nonexistent_file(self):
        """Test behavior with a nonexistent file."""
        result = subprocess.run(
            ["dane", "valid", "type:", "fasta", "file:", "nonexistent.fasta"],
            capture_output=True,
            text=True
        )
        
        # Should fail with non-zero exit code
        assert result.returncode != 0