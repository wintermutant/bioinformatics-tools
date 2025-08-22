"""
Tests for the main CLI functionality (dane command).
"""
import subprocess
import sys
from pathlib import Path
import pytest


class TestCLI:
    """Test cases for the main CLI interface."""
    
    def test_dane_help_command(self):
        """Test that dane help command works and returns expected output."""
        result = subprocess.run(
            ["dane", "help"], 
            capture_output=True, 
            text=True
        )
        
        assert result.returncode == 0
        assert "Available file types:" in result.stdout
        assert "Fasta" in result.stdout
        assert "Fastq" in result.stdout
    
    def test_dane_help_with_file_type(self):
        """Test that dane help with specific file type works."""
        result = subprocess.run(
            ["dane", "help", "type:", "fasta"], 
            capture_output=True, 
            text=True
        )
        
        assert result.returncode == 0
        assert "valid" in result.stdout
        assert "basic stats" in result.stdout
        assert "total seqs" in result.stdout
    
    def test_dane_without_arguments(self):
        """Test that dane without arguments shows appropriate error."""
        result = subprocess.run(
            ["dane"], 
            capture_output=True, 
            text=True
        )
        
        # The application returns 0 but logs an error - that's fine
        assert result.returncode == 0
        assert "No file type provided" in result.stdout
    
    def test_dane_with_invalid_file_type(self):
        """Test that dane with invalid file type shows appropriate error."""
        result = subprocess.run(
            ["dane", "help", "type:", "invalidtype"], 
            capture_output=True, 
            text=True
        )
        
        # The application returns 0 but logs an error - that's fine
        assert result.returncode == 0  
        assert "Program not found" in result.stdout
    
    def test_dane_with_test_fasta_file(self):
        """Test basic functionality with the example fasta file."""
        test_file = Path("test-files/example.fasta")
        if not test_file.exists():
            pytest.skip("Test file not found: test-files/example.fasta")
        
        result = subprocess.run(
            ["dane", "valid", "type:", "fasta", "file:", str(test_file)], 
            capture_output=True, 
            text=True
        )
        
        assert result.returncode == 0
        assert "Success" in result.stdout
        assert "File was scrubbed and found to be True" in result.stdout