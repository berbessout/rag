"""
SharePoint Integration Test Suite

This module contains comprehensive tests for the SharePoint class, which handles:
- Authentication and connection to SharePoint Online
- File listing and filtering (PowerPoint files)
- File downloading (to memory or disk)
- Error handling and edge cases

Test Categories:
- Unit Tests: Mock all external dependencies
- Integration Tests: Use real SharePoint credentials (marked with @pytest.mark.integration)
- Edge Cases: Test error scenarios and boundary conditions
"""

import pytest
import os
from unittest.mock import Mock, patch, mock_open
from io import BytesIO
import tempfile
import shutil
from dotenv import load_dotenv

# Import the class under test
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from src.ingestion.get_sharepoint_files import SharePoint

load_dotenv()


def pytest_configure(config):
    """Configure pytest with custom markers for integration tests."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test requiring real SharePoint access"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS - Mock all external dependencies
# ═══════════════════════════════════════════════════════════════════════════════

class TestSharePointUnit:
    """
    Unit tests for SharePoint class methods with all external dependencies mocked.
    
    These tests verify the logic without requiring actual SharePoint connectivity.
    """
    
    # ───────────────────────────────────────────────────────────────────────────
    # Test Fixtures - Reusable test setup components
    # ───────────────────────────────────────────────────────────────────────────
    
    @pytest.fixture
    def mock_env_vars(self):
        """
        Mock environment variables for SharePoint configuration.
        
        Provides a complete set of valid environment variables to test
        the SharePoint class initialization without requiring real credentials.
        """
        with patch.dict(os.environ, {
            'SHAREPOINT_SITE_URL': 'https://test-my.sharepoint.com/personal/user_domain_com',
            'SHAREPOINT_USERNAME': 'user@domain.com',
            'SHAREPOINT_PASSWORD': 'password123',
            'SHAREPOINT_LIBRARY_NAME': 'TestLibrary'
        }):
            yield
    
    @pytest.fixture
    def mock_sharepoint_context(self):
        """
        Mock SharePoint ClientContext and web objects.
        
        This fixture creates a mock SharePoint context that simulates successful
        authentication and connection without requiring actual SharePoint access.
        
        Returns:
            tuple: (mock_context, mock_web) - Mocked SharePoint objects
        """
        with patch('src.ingestion.get_sharepoint_files.ClientContext') as mock_ctx_class:
            # Create mock context instance
            mock_ctx = Mock()
            mock_ctx.with_credentials.return_value = mock_ctx
            mock_ctx_class.return_value = mock_ctx
            
            # Create mock web object (represents the SharePoint site)
            mock_web = Mock()
            mock_ctx.web = mock_web
            mock_ctx.load.return_value = None
            mock_ctx.execute_query.return_value = None
            
            yield mock_ctx, mock_web
    
    # ───────────────────────────────────────────────────────────────────────────
    # Initialization Tests - Verify SharePoint class setup
    # ───────────────────────────────────────────────────────────────────────────
    
    def test_init_missing_env_vars(self):
        """
        Test SharePoint initialization fails when required environment variables are missing.
        
        The SharePoint class should validate that all required environment variables
        are present and raise a ValueError with descriptive message if any are missing.
        """
        # Clear all environment variables to simulate missing configuration
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                SharePoint()
            
            # Verify the error message is helpful and mentions missing variables
            error_message = str(exc_info.value)
            assert "Missing required environment variables" in error_message
            assert "SHAREPOINT_SITE_URL" in error_message
    
    def test_init_partial_missing_env_vars(self):
        """
        Test initialization fails when only some environment variables are provided.
        
        This ensures the class validates the complete set of required variables,
        not just the presence of any variables.
        """
        # Provide only partial environment configuration
        with patch.dict(os.environ, {
            'SHAREPOINT_SITE_URL': 'https://test.sharepoint.com',
            'SHAREPOINT_USERNAME': 'user@domain.com'
            # Missing SHAREPOINT_PASSWORD and SHAREPOINT_LIBRARY_NAME
        }, clear=True):
            with pytest.raises(ValueError) as exc_info:
                SharePoint()
            
            # Verify specific missing variables are mentioned
            error_message = str(exc_info.value)
            assert "SHAREPOINT_PASSWORD" in error_message
            assert "SHAREPOINT_LIBRARY_NAME" in error_message
    
    @patch('builtins.print')  # Suppress console output during tests
    def test_init_personal_site_success(self, mock_print, mock_env_vars, mock_sharepoint_context):
        """
        Test successful initialization with personal SharePoint site URL.
        
        Personal sites have a different URL structure and base path compared to team sites.
        This test verifies the class correctly handles personal site URLs.
        """
        mock_ctx, mock_web = mock_sharepoint_context
        
        sharepoint = SharePoint()
        
        # Verify all configuration is correctly parsed and stored
        assert sharepoint.site_url == 'https://test-my.sharepoint.com/personal/user_domain_com'
        assert sharepoint.username == 'user@domain.com'
        assert sharepoint.password == 'password123'
        assert sharepoint.library_name == 'TestLibrary'
        
        # Personal sites use a specific base path structure
        assert sharepoint.base_path == '/personal/user_domain_com/Documents'
        assert sharepoint.ctx == mock_ctx
    
    @patch('builtins.print')
    def test_init_team_site_success(self, mock_print, mock_sharepoint_context):
        """
        Test successful initialization with team SharePoint site URL.
        
        Team sites have a different URL structure (/sites/sitename) and the base path
        is derived from the site's server relative path.
        """
        # Configure environment for team site
        with patch.dict(os.environ, {
            'SHAREPOINT_SITE_URL': 'https://test.sharepoint.com/sites/teamsite',
            'SHAREPOINT_USERNAME': 'user@domain.com',
            'SHAREPOINT_PASSWORD': 'password123',
            'SHAREPOINT_LIBRARY_NAME': 'TestLibrary'
        }):
            mock_ctx, mock_web = mock_sharepoint_context
            # Team sites provide their base path through the web object
            mock_web.server_relative_path = '/sites/teamsite'
            
            sharepoint = SharePoint()
            
            # Team sites use the server relative path as base path
            assert sharepoint.base_path == '/sites/teamsite'
    
    def test_init_authentication_failure(self, mock_env_vars):
        """
        Test initialization handles authentication failures gracefully.
        
        When SharePoint authentication fails (wrong credentials, MFA required, etc.),
        the class should provide a clear error message.
        """
        with patch('src.ingestion.get_sharepoint_files.ClientContext') as mock_ctx_class:
            mock_ctx = Mock()
            mock_ctx.with_credentials.return_value = mock_ctx
            mock_ctx_class.return_value = mock_ctx
            # Simulate authentication failure
            mock_ctx.execute_query.side_effect = Exception("401 Unauthorized")
            
            with pytest.raises(Exception) as exc_info:
                SharePoint()
            assert "Authentication failed" in str(exc_info.value)
    
    def test_init_site_not_found(self, mock_env_vars):
        """
        Test initialization handles site not found errors.
        
        When the specified SharePoint site doesn't exist or isn't accessible,
        the class should provide a clear error message.
        """
        with patch('src.ingestion.get_sharepoint_files.ClientContext') as mock_ctx_class:
            mock_ctx = Mock()
            mock_ctx.with_credentials.return_value = mock_ctx
            mock_ctx_class.return_value = mock_ctx
            # Simulate site not found
            mock_ctx.execute_query.side_effect = Exception("404 Not Found")
            
            with pytest.raises(Exception) as exc_info:
                SharePoint()
            assert "SharePoint site not found" in str(exc_info.value)
    
    # ───────────────────────────────────────────────────────────────────────────
    # File Listing Tests - Verify PowerPoint file discovery
    # ───────────────────────────────────────────────────────────────────────────
    
    @patch('builtins.print')
    def test_list_ppt_files_success(self, mock_print, mock_env_vars, mock_sharepoint_context):
        """
        Test successful listing of PowerPoint files with proper filtering.
        
        The method should:
        1. Connect to the specified SharePoint library
        2. Retrieve all files
        3. Filter for PowerPoint files (.ppt, .pptx)
        4. Return server relative URLs
        """
        mock_ctx, mock_web = mock_sharepoint_context
        
        # Mock SharePoint folder and file objects
        mock_folder = Mock()
        mock_ctx.web.get_folder_by_server_relative_url.return_value = mock_folder
        
        # Create mock files with different extensions to test filtering
        mock_file1 = self._create_mock_file("presentation1.pptx", "/path/to/presentation1.pptx")
        mock_file2 = self._create_mock_file("document.docx", "/path/to/document.docx")  # Should be filtered out
        mock_file3 = self._create_mock_file("presentation2.ppt", "/path/to/presentation2.ppt")
        
        mock_folder.files.get.return_value.execute_query.return_value = [mock_file1, mock_file2, mock_file3]
        
        sharepoint = SharePoint()
        files = sharepoint.list_ppt_files()
        
        # Verify only PowerPoint files are returned
        assert len(files) == 2
        assert "/path/to/presentation1.pptx" in files
        assert "/path/to/presentation2.ppt" in files
        assert "/path/to/document.docx" not in files  # Should be filtered out
    
    def _create_mock_file(self, filename, server_url):
        """
        Helper method to create mock file objects for testing.
        
        Args:
            filename (str): Name of the file
            server_url (str): Server relative URL of the file
            
        Returns:
            Mock: Mock file object with name and serverRelativeUrl attributes
        """
        mock_file = Mock()
        mock_file.name = filename
        mock_file.serverRelativeUrl = server_url
        return mock_file
    
    @patch('builtins.print')
    def test_list_ppt_files_with_folder_path(self, mock_print, mock_env_vars, mock_sharepoint_context):
        """
        Test listing PowerPoint files from a specific subfolder.
        
        The method should accept an optional folder path parameter and
        construct the correct server relative URL for the subfolder.
        """
        mock_ctx, mock_web = mock_sharepoint_context
        
        mock_folder = Mock()
        mock_ctx.web.get_folder_by_server_relative_url.return_value = mock_folder
        mock_folder.files.get.return_value.execute_query.return_value = []
        
        sharepoint = SharePoint()
        sharepoint.list_ppt_files("subfolder")
        
        # Verify the correct subfolder path is constructed and used
        expected_path = "/personal/user_domain_com/Documents/TestLibrary/subfolder"
        mock_ctx.web.get_folder_by_server_relative_url.assert_called_with(expected_path)
    
    @patch('builtins.print')
    def test_list_ppt_files_error_handling(self, mock_print, mock_env_vars, mock_sharepoint_context):
        """
        Test error handling when listing files fails.
        
        Network issues, permission problems, or folder not found errors
        should be handled gracefully by returning an empty list.
        """
        mock_ctx, mock_web = mock_sharepoint_context
        # Simulate access denied or folder not found
        mock_ctx.web.get_folder_by_server_relative_url.side_effect = Exception("Access denied")
        
        sharepoint = SharePoint()
        files = sharepoint.list_ppt_files()
        
        # Should return empty list on error, not crash
        assert files == []
        # Should log the error for debugging
        mock_print.assert_called()
    
    # ───────────────────────────────────────────────────────────────────────────
    # File Download Tests - Verify file retrieval functionality
    # ───────────────────────────────────────────────────────────────────────────
    
    @patch('builtins.print')
    def test_download_file_to_bytesio(self, mock_print, mock_env_vars, mock_sharepoint_context):
        """
        Test downloading file content to memory (BytesIO object).
        
        This is the default behavior when no local path is specified.
        The file content should be returned as a BytesIO object for in-memory processing.
        """
        mock_ctx, mock_web = mock_sharepoint_context
        
        # Mock SharePoint File.open_binary method
        with patch('src.ingestion.get_sharepoint_files.File.open_binary') as mock_open_binary:
            # Simulate file download response
            mock_response = Mock()
            mock_response.content = b"test file content"
            mock_open_binary.return_value = mock_response
            
            sharepoint = SharePoint()
            result = sharepoint.download_file("/path/to/file.pptx")
            
            # Verify file is downloaded to BytesIO and content is correct
            assert isinstance(result, BytesIO)
            assert result.getvalue() == b"test file content"
            mock_open_binary.assert_called_with(mock_ctx, "/path/to/file.pptx")
    
    @patch('builtins.print')
    def test_download_file_to_local_path(self, mock_print, mock_env_vars, mock_sharepoint_context):
        """
        Test downloading file to local filesystem.
        
        When a local path is provided, the file should be saved to disk
        and the method should return None to indicate file was saved.
        """
        mock_ctx, mock_web = mock_sharepoint_context
        
        with patch('src.ingestion.get_sharepoint_files.File.open_binary') as mock_open_binary, \
             patch('builtins.open', mock_open()) as mock_file_open:
            
            # Simulate file download response
            mock_response = Mock()
            mock_response.content = b"test file content"
            mock_open_binary.return_value = mock_response
            
            sharepoint = SharePoint()
            result = sharepoint.download_file("/path/to/file.pptx", "local_file.pptx")
            
            # Should return None when saving to disk
            assert result is None
            # Should create local file and write content
            mock_file_open.assert_called_with("local_file.pptx", "wb")
            mock_file_open().write.assert_called_with(b"test file content")
    
    @patch('builtins.print')
    def test_download_file_error_handling(self, mock_print, mock_env_vars, mock_sharepoint_context):
        """
        Test error handling during file download.
        
        Network issues, file not found, or permission errors should be
        handled gracefully with appropriate error messages.
        """
        mock_ctx, mock_web = mock_sharepoint_context
        
        with patch('src.ingestion.get_sharepoint_files.File.open_binary') as mock_open_binary:
            # Simulate download failure
            mock_open_binary.side_effect = Exception("Download failed")
            
            sharepoint = SharePoint()
            
            with pytest.raises(Exception):
                sharepoint.download_file("/path/to/file.pptx")
            
            # Should log error for debugging
            mock_print.assert_called_with("[ERROR] Failed to download file : Download failed")
    
    # ───────────────────────────────────────────────────────────────────────────
    # Bulk Download Tests - Verify batch file operations
    # ───────────────────────────────────────────────────────────────────────────
    
    @patch('builtins.print')
    def test_download_all_ppt_files_to_bytesio(self, mock_print, mock_env_vars, mock_sharepoint_context):
        """
        Test downloading all PowerPoint files to memory.
        
        Should list all PowerPoint files and download each one to BytesIO objects.
        Returns a list of (filename, BytesIO) tuples.
        """
        mock_ctx, mock_web = mock_sharepoint_context
        
        sharepoint = SharePoint()
        
        # Mock the list and download operations
        with patch.object(sharepoint, 'list_ppt_files') as mock_list, \
             patch.object(sharepoint, 'download_file') as mock_download:
            
            # Setup mock return values
            mock_list.return_value = ["/path/file1.pptx", "/path/file2.ppt"]
            mock_download.side_effect = [BytesIO(b"content1"), BytesIO(b"content2")]
            
            results = sharepoint.download_all_ppt_files()
            
            # Verify all files are downloaded and returned correctly
            assert len(results) == 2
            assert results[0][0] == "file1.pptx"  # Filename extracted from path
            assert results[1][0] == "file2.ppt"
            assert results[0][1].getvalue() == b"content1"  # BytesIO content
            assert results[1][1].getvalue() == b"content2"
    
    @patch('builtins.print')
    def test_download_all_ppt_files_to_local_dir(self, mock_print, mock_env_vars, mock_sharepoint_context):
        """
        Test downloading all PowerPoint files to local directory.
        
        When local_dir is specified, files should be saved to disk with
        proper filename handling and path construction.
        """
        mock_ctx, mock_web = mock_sharepoint_context
        
        sharepoint = SharePoint()
        
        with patch.object(sharepoint, 'list_ppt_files') as mock_list, \
             patch.object(sharepoint, 'download_file') as mock_download:
            
            mock_list.return_value = ["/path/file1.pptx"]
            mock_download.return_value = None  # Indicates file saved to disk
            
            results = sharepoint.download_all_ppt_files(local_dir="/local/dir")
            
            # When saving to disk, should return empty list
            assert results == []
            # Should construct proper local file path
            expected_path = os.path.join("/local/dir", "file1.pptx")
            mock_download.assert_called_with("/path/file1.pptx", expected_path)
    
    @patch('builtins.print')
    def test_download_all_ppt_files_no_files(self, mock_print, mock_env_vars, mock_sharepoint_context):
        """
        Test bulk download when no PowerPoint files are found.
        
        Should handle empty file list gracefully and return empty results.
        """
        mock_ctx, mock_web = mock_sharepoint_context
        
        sharepoint = SharePoint()
        
        with patch.object(sharepoint, 'list_ppt_files') as mock_list:
            mock_list.return_value = []  # No files found
            
            results = sharepoint.download_all_ppt_files()
            
            assert results == []


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS - Use real SharePoint connectivity
# ═══════════════════════════════════════════════════════════════════════════════

class TestSharePointIntegration:
    """
    Integration tests that require real SharePoint credentials and connectivity.
    
    These tests are marked with @pytest.mark.integration and will be skipped
    if real SharePoint credentials are not available in environment variables.
    
    To run these tests:
    1. Set up real SharePoint environment variables
    2. Run: pytest -m integration
    """
    
    @pytest.fixture
    def temp_dir(self):
        """
        Create a temporary directory for file download testing.
        
        Automatically cleans up the directory after the test completes.
        """
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def real_env_vars(self):
        """
        Validate and provide real SharePoint environment variables.
        
        Skips the test if any required environment variables are missing,
        preventing test failures in CI/CD environments without SharePoint access.
        """
        required_vars = [
            'SHAREPOINT_SITE_URL',
            'SHAREPOINT_USERNAME', 
            'SHAREPOINT_PASSWORD',
            'SHAREPOINT_LIBRARY_NAME'
        ]
        
        # Check if all required variables are present
        if not all(os.getenv(var) for var in required_vars):
            pytest.skip("Real SharePoint credentials not available")
        
        return {var: os.getenv(var) for var in required_vars}
    
    @pytest.mark.integration
    def test_real_sharepoint_connection(self, real_env_vars):
        """
        Test actual connection to SharePoint with real credentials.
        
        Verifies that the SharePoint class can successfully authenticate
        and establish a connection to the real SharePoint environment.
        """
        try:
            sharepoint = SharePoint()
            assert sharepoint.ctx is not None
            assert sharepoint.base_path is not None
            print(f"Successfully connected to: {sharepoint.base_path}")
        except Exception as e:
            pytest.fail(f"Failed to connect to real SharePoint: {e}")
    
    @pytest.mark.integration
    def test_real_list_files(self, real_env_vars):
        """
        Test listing files from real SharePoint library.
        
        Verifies file listing functionality and validates that only
        PowerPoint files are returned from the real SharePoint site.
        """
        try:
            sharepoint = SharePoint()
            files = sharepoint.list_ppt_files()
            
            assert isinstance(files, list)
            print(f"Found {len(files)} PPT files")
            
            # Verify all returned files are actually PowerPoint files
            for file_url in files:
                filename = os.path.basename(file_url)
                assert filename.lower().endswith(('.ppt', '.pptx')), \
                    f"Non-PPT file found: {filename}"
                
        except Exception as e:
            pytest.fail(f"Failed to list files from real SharePoint: {e}")
    
    @pytest.mark.integration
    def test_real_download_file(self, real_env_vars, temp_dir):
        """
        Test downloading a real file from SharePoint.
        
        Tests both download modes:
        1. Download to BytesIO (in-memory)
        2. Download to local file (disk storage)
        
        Requires at least one PowerPoint file to be present in the SharePoint library.
        """
        try:
            sharepoint = SharePoint()
            files = sharepoint.list_ppt_files()
            
            if not files:
                pytest.skip("No PPT files available for download testing")
            
            # Test with the first available file
            test_file = files[0]
            filename = os.path.basename(test_file)
            local_path = os.path.join(temp_dir, filename)
            
            # Test download to BytesIO
            content = sharepoint.download_file(test_file)
            assert isinstance(content, BytesIO)
            assert len(content.getvalue()) > 0
            
            # Test download to local file
            result = sharepoint.download_file(test_file, local_path)
            assert result is None  # Should return None when saving to disk
            assert os.path.exists(local_path)
            assert os.path.getsize(local_path) > 0
            
            print(f"Successfully downloaded {filename} ({os.path.getsize(local_path)} bytes)")
            
        except Exception as e:
            pytest.fail(f"Failed to download file from real SharePoint: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASE TESTS - Test boundary conditions and error scenarios
# ═══════════════════════════════════════════════════════════════════════════════

class TestSharePointEdgeCases:
    """
    Test edge cases, boundary conditions, and error scenarios.
    
    These tests verify the robustness of the SharePoint class when
    dealing with unusual inputs or error conditions.
    """
    
    @patch('builtins.print')
    def test_empty_library_name(self, mock_print):
        """
        Test behavior with empty library name.
        
        An empty library name should be rejected as it would result
        in invalid SharePoint paths.
        """
        with patch.dict(os.environ, {
            'SHAREPOINT_SITE_URL': 'https://test.sharepoint.com',
            'SHAREPOINT_USERNAME': 'user@domain.com',
            'SHAREPOINT_PASSWORD': 'password123',
            'SHAREPOINT_LIBRARY_NAME': ''  # Empty library name
        }):
            with pytest.raises(ValueError):
                SharePoint()
    
    @patch('builtins.print')
    def test_malformed_url(self, mock_print):
        """
        Test behavior with malformed SharePoint URL.
        
        Invalid URLs should be detected and result in appropriate
        error handling during connection attempts.
        """
        with patch.dict(os.environ, {
            'SHAREPOINT_SITE_URL': 'not-a-valid-url',
            'SHAREPOINT_USERNAME': 'user@domain.com',
            'SHAREPOINT_PASSWORD': 'password123',
            'SHAREPOINT_LIBRARY_NAME': 'TestLibrary'
        }):
            with patch('src.ingestion.get_sharepoint_files.ClientContext') as mock_ctx_class:
                mock_ctx = Mock()
                mock_ctx.with_credentials.return_value = mock_ctx
                mock_ctx_class.return_value = mock_ctx
                # Simulate URL validation failure
                mock_ctx.execute_query.side_effect = Exception("Invalid URL")
                
                with pytest.raises(Exception):
                    SharePoint()
    
    @patch('builtins.print')
    def test_unicode_library_name(self, mock_print):
        """
        Test behavior with Unicode characters in library name.
        
        SharePoint should handle international characters in library names
        correctly, as these are common in non-English SharePoint sites.
        """
        with patch.dict(os.environ, {
            'SHAREPOINT_SITE_URL': 'https://test-my.sharepoint.com/personal/user_domain_com',
            'SHAREPOINT_USERNAME': 'user@domain.com',
            'SHAREPOINT_PASSWORD': 'password123',
            'SHAREPOINT_LIBRARY_NAME': 'Présentation_projets'  # Unicode characters
        }):
            with patch('src.ingestion.get_sharepoint_files.ClientContext') as mock_ctx_class:
                mock_ctx = Mock()
                mock_ctx.with_credentials.return_value = mock_ctx
                mock_ctx_class.return_value = mock_ctx
                mock_ctx.web = Mock()
                mock_ctx.load.return_value = None
                mock_ctx.execute_query.return_value = None
                
                sharepoint = SharePoint()
                # Unicode library name should be preserved correctly
                assert sharepoint.library_name == 'Présentation_projets'


# ═══════════════════════════════════════════════════════════════════════════════
# TEST RUNNER - For standalone execution
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Run tests when script is executed directly.
    
    Usage:
    - Run all tests: python test_get_sharepoint.py
    - Run with verbose output: python test_get_sharepoint.py -v
    - Run only integration tests: python test_get_sharepoint.py -m integration
    """
    pytest.main([__file__, "-v"])
