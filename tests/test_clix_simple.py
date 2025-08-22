"""
Simplified tests for the CLIX framework that avoid initialization issues.
"""
import yaml
from pathlib import Path
import pytest


class TestCLIXSimple:
    """Simplified test cases for the CLIX framework."""
    
    def test_default_config_file_exists(self):
        """Test that the default config file exists and is valid YAML."""
        config_path = Path("bioinformatics_tools/caragols/config-caragols.yaml")
        assert config_path.exists(), "Default config file should exist"
        
        # Test that it's valid YAML
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert isinstance(config, dict)
        # Check for expected structure
        assert 'report' in config
        assert 'maintenance-info' in config
    
    def test_logger_import(self):
        """Test that the logger can be imported."""
        from bioinformatics_tools.caragols.logger import LOGGER
        
        assert LOGGER is not None
        assert hasattr(LOGGER, 'info')
        assert hasattr(LOGGER, 'debug')
        assert hasattr(LOGGER, 'error')
    
    def test_clix_module_import(self):
        """Test that the clix module can be imported."""
        from bioinformatics_tools.caragols import clix
        
        assert hasattr(clix, 'App')
        assert clix.App.config_filename == 'config-caragols.yaml'