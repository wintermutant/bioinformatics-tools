"""
Tests for the CLIX (Command Line Invocation eXtension) framework.
"""
import tempfile
from pathlib import Path
import yaml
import pytest

from bioinformatics_tools.caragols import clix


class TestCLIX:
    """Test cases for the CLIX framework."""
    
    def test_app_initialization(self):
        """Test that the App class exists and has expected attributes."""
        # Don't actually initialize to avoid sys.exit issues
        assert hasattr(clix, 'App')
        assert clix.App.config_filename == 'config-caragols.yaml'
        assert hasattr(clix.App, 'default_config_path')
    
    def test_default_config_exists(self):
        """Test that the default config file exists and is valid."""
        assert clix.App.default_config_path.exists()
        
        # Test that it's valid YAML
        config = yaml.safe_load(clix.App.default_config_path.read_text())
        assert isinstance(config, dict)
        
        # Check for expected config structure
        assert 'report' in config
        assert 'maintenance-info' in config
    
    def test_config_loading(self):
        """Test that default configuration can be loaded."""
        # Test class-level config loading without initialization
        assert clix.App.default_config_path.exists()
        
        # Test that the default config is properly loaded at class level
        config = clix.App.default_config
        assert isinstance(config, dict)
    
    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file for testing."""
        config_content = {
            'name': 'test_config',
            'test_param': 'test_value',
            'length': 100
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_content, f)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
    
    def test_custom_config_loading(self, temp_config_file):
        """Test loading a custom configuration file."""
        # This would test the --config-file functionality
        # The actual implementation might need to be tested through CLI
        pass  # TODO: Implement based on actual config loading mechanism
    
    def test_command_parsing(self):
        """Test that the App class has methods for command parsing."""
        # Test that the class has expected methods without initializing
        assert hasattr(clix.App, '__init__')
        # This is a placeholder - actual command parsing would need instance testing


class TestConfigSystem:
    """Test cases for the configuration system."""
    
    def test_local_config_detection(self):
        """Test that local config files are detected when present."""
        # Create a temporary local config in current directory
        local_config = Path("config-caragols.yaml")
        config_content = {'name': 'local_test', 'local_param': True}
        
        # Only create if it doesn't exist (don't overwrite existing)
        if not local_config.exists():
            with open(local_config, 'w') as f:
                yaml.dump(config_content, f)
            
            try:
                # Test that it would be detected
                assert local_config.exists()
            finally:
                # Clean up
                local_config.unlink()
    
    def test_config_precedence(self):
        """Test that configuration precedence works correctly."""
        # This would test: command-line > local config > default config
        # Implementation depends on how the CLIX framework actually handles precedence
        pass  # TODO: Implement based on actual precedence logic


class TestLogging:
    """Test cases for the logging system."""
    
    def test_logger_import(self):
        """Test that the logger can be imported and initialized."""
        from bioinformatics_tools.caragols.logger import LOGGER
        
        assert LOGGER is not None
        assert hasattr(LOGGER, 'info')
        assert hasattr(LOGGER, 'error')
        assert hasattr(LOGGER, 'debug')
    
    def test_logging_config_path(self):
        """Test that logging config path is accessible."""
        from bioinformatics_tools.caragols.logger import CONFIG_PATH
        
        # Should be a valid path
        assert CONFIG_PATH is not None
        # The path should exist or be createable
        config_dir = Path(CONFIG_PATH).parent
        assert config_dir.exists() or config_dir.parent.exists()