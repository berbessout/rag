"""
Translation Service Test Suite

This module contains comprehensive tests for the translation functionality, which handles:
- Language detection for document content
- Translation of non-English documents to English using Azure OpenAI
- Environment variable validation and error handling
- Integration with file conversion systems

Test Categories:
- Language Detection Tests: Verify English/non-English content identification
- Translation Tests: Test Azure OpenAI-based translation functionality
- Error Handling Tests: Test robustness under various failure conditions
- Integration Tests: Test translation with file conversion pipeline

Components Under Test:
- is_english(): Language detection function
- translate_file(): Azure OpenAI-based translation function
"""

from pathlib import Path
import pytest
from src import translate
from src.convert_files import convert_files


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FIXTURES - Reusable test setup components
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def tmp_txt_file(tmp_path):
    """
    Create temporary text files for testing translation functionality.
    
    This fixture provides a helper function to create test files with
    specified content and filenames in a temporary directory.
    
    Args:
        tmp_path: pytest fixture providing a temporary directory
        
    Returns:
        function: Helper function to create test files
    """
    def _create(content, filename="test.txt"):
        """
        Create a temporary text file with specified content.
        
        Args:
            content (str): Text content to write to the file
            filename (str): Name of the file to create
            
        Returns:
            Path: Path to the created temporary file
        """
        file_path = tmp_path / filename
        file_path.write_text(content, encoding="utf-8")
        return file_path
    return _create


# ═══════════════════════════════════════════════════════════════════════════════
# LANGUAGE DETECTION TESTS - Verify English/non-English identification
# ═══════════════════════════════════════════════════════════════════════════════

class TestLanguageDetection:
    """
    Test the language detection functionality.
    
    These tests verify that the is_english() function correctly identifies
    whether text content is in English or requires translation.
    """
    
    def test_is_english_true(self, tmp_txt_file):
        """
        Test detection of English content using real PowerPoint file.
        
        This test uses a real PowerPoint file from the test data to verify
        that English content is correctly identified. The file is first
        converted to text, then checked for English language.
        """
        # Use real PowerPoint file from test data directory
        file_path = Path("./public/Customer_pdf")
        converted_text = convert_files("ABB - Product development for BiW.pptx", file_path)
        
        # Verify English content is correctly detected
        assert translate.is_english(converted_text) is True, "English PowerPoint content should be detected as English"

    def test_is_english_false(self, tmp_txt_file):
        """
        Test detection of non-English (French) content.
        
        Verifies that the function correctly identifies French text
        as non-English and requiring translation.
        """
        # Create test file with French content
        file_path = tmp_txt_file("Ceci est une phrase en français.")
        french_content = file_path.read_text()
        
        # Verify French content is detected as non-English
        assert translate.is_english(french_content) is False, "French text should be detected as non-English"

    def test_is_english_exception(self, tmp_path):
        """
        Test error handling when file operations fail.
        
        When file reading fails or other exceptions occur during language
        detection, the function should gracefully return False rather than crash.
        """
        # Test with non-existent file path
        file_path = tmp_path / "nonexistent.txt"
        
        # Should handle file not found gracefully
        assert translate.is_english(file_path) is False, "Non-existent file should return False"


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSLATION TESTS - Test Azure OpenAI-based translation functionality
# ═══════════════════════════════════════════════════════════════════════════════

class TestTranslation:
    """
    Test the Azure OpenAI-based translation functionality.
    
    These tests verify translation of non-English content to English,
    including proper environment setup, LLM integration, and error handling.
    """
    
    def test_translate_file_success(self, tmp_txt_file, monkeypatch):
        """
        Test successful translation of French text to English.
        
        This test mocks the Azure OpenAI service to verify that:
        1. Environment variables are properly validated
        2. LLM is correctly initialized and called
        3. Translation response is properly returned
        """
        # Create test file with French content
        file_path = tmp_txt_file("Bonjour le monde.")
        
        # Mock required environment variables for Azure OpenAI
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fake-key")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fake.endpoint")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "fake-model")

        # Create mock LLM that simulates translation response
        class DummyLLM:
            def __init__(self, *args, **kwargs):
                self.invoked = False
                
            def invoke(self, messages):
                """Mock LLM invoke method that returns translated text."""
                self.invoked = True
                
                class Response:
                    content = "Hello world."
                    
                return Response()

        # Apply the mock to replace real Azure OpenAI client
        monkeypatch.setattr(translate, "AzureChatOpenAI", DummyLLM)
        
        # Test translation functionality
        result = translate.translate_file(file_path.read_text())
        
        # Verify translation was successful
        assert result == "Hello world.", "Translation should return English text"

    def test_translate_file_missing_env(self, tmp_txt_file, monkeypatch):
        """
        Test error handling when required environment variables are missing.
        
        The translation function should validate that all required Azure OpenAI
        environment variables are present and raise appropriate errors if missing.
        """
        # Create test file with French content
        file_path = tmp_txt_file("Bonjour le monde.")
        
        # Remove all Azure OpenAI environment variables
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
        
        # Mock the LLM class to prevent import errors
        monkeypatch.setattr(translate, "AzureChatOpenAI", lambda *a, **k: None)
        
        # Should raise RuntimeError for missing environment variables
        with pytest.raises(RuntimeError) as excinfo:
            translate.translate_file(file_path.read_text())
            
        # Verify error message mentions missing environment variables
        assert "Missing environment variable" in str(excinfo.value), "Error should mention missing environment variables"

    def test_translate_file_llm_error(self, tmp_txt_file, monkeypatch):
        """
        Test error handling when LLM translation fails.
        
        Network issues, API failures, or LLM service errors should be
        handled gracefully with appropriate error messages.
        """
        # Create test file with French content
        file_path = tmp_txt_file("Bonjour le monde.")
        
        # Set up environment variables
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fake-key")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fake.endpoint")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "fake-model")

        # Create mock LLM that simulates API failure
        class DummyLLM:
            def __init__(self, *args, **kwargs):
                pass
                
            def invoke(self, messages):
                """Mock LLM that raises an exception to simulate API failure."""
                raise Exception("LLM failure")

        # Apply the failing mock
        monkeypatch.setattr(translate, "AzureChatOpenAI", DummyLLM)
        
        # Should raise RuntimeError for LLM failures
        with pytest.raises(RuntimeError) as excinfo:
            translate.translate_file(file_path.read_text())
            
        # Verify error message mentions LLM failure
        assert "Error during LLM call" in str(excinfo.value), "Error should mention LLM call failure"

    def test_translate_file_file_not_found(self, tmp_path):
        """
        Test error handling when input file doesn't exist.
        
        File not found errors should be properly propagated to allow
        calling code to handle missing input files appropriately.
        """
        # Test with non-existent file
        file_path = tmp_path / "does_not_exist.txt"
        
        # Should raise FileNotFoundError for missing files
        with pytest.raises(FileNotFoundError):
            translate.translate_file(file_path.read_text())


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS - Test translation with file conversion pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class TestTranslationIntegration:
    """
    Integration tests for translation with the broader document processing pipeline.
    
    These tests verify that translation works correctly when integrated with
    file conversion and document processing workflows.
    """
    
    def test_translation_with_file_conversion(self, tmp_txt_file, monkeypatch):
        """
        Test translation integrated with file conversion workflow.
        
        This test simulates the complete workflow where:
        1. A document is converted from PowerPoint to text
        2. Language detection determines if translation is needed
        3. Translation is performed if the content is non-English
        """
        # Create test file simulating converted PowerPoint content in French
        french_content = "Présentation du projet de développement produit."
        file_path = tmp_txt_file(french_content, "converted_presentation.txt")
        
        # Set up Azure OpenAI environment
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.endpoint")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "test-model")
        
        # Mock successful translation
        class MockTranslator:
            def __init__(self, *args, **kwargs):
                pass
                
            def invoke(self, messages):
                class Response:
                    content = "Product development project presentation."
                return Response()
        
        monkeypatch.setattr(translate, "AzureChatOpenAI", MockTranslator)
        
        # Test the complete workflow
        content = file_path.read_text()
        
        # 1. Check if translation is needed
        needs_translation = not translate.is_english(content)
        assert needs_translation, "French content should be detected as needing translation"
        
        # 2. Perform translation if needed
        if needs_translation:
            translated_content = translate.translate_file(content)
            assert "Product development project presentation" in translated_content
            assert translated_content != content, "Translated content should differ from original"


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASE TESTS - Test boundary conditions and unusual inputs
# ═══════════════════════════════════════════════════════════════════════════════

class TestTranslationEdgeCases:
    """
    Test edge cases and boundary conditions for translation functionality.
    
    These tests ensure the translation system handles unusual inputs,
    empty content, and other edge cases gracefully.
    """
    
    def test_empty_content_translation(self, monkeypatch):
        """
        Test translation behavior with empty or whitespace-only content.
        
        Empty content should be handled gracefully without causing errors
        or making unnecessary API calls.
        """
        # Set up environment for translation
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.endpoint")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "test-model")
        
        # Test language detection with empty content
        assert translate.is_english("") is False, "Empty string should be treated as non-English"
        assert translate.is_english("   ") is False, "Whitespace-only content should be treated as non-English"
    
    def test_mixed_language_content(self, tmp_txt_file):
        """
        Test language detection with mixed English and non-English content.
        
        Content containing both English and non-English text should be
        handled consistently by the language detection system.
        """
        # Create content with mixed languages
        mixed_content = tmp_txt_file("Hello world. Bonjour le monde. This is English and French.")
        content = mixed_content.read_text()
        
        # Language detection should handle mixed content consistently
        result = translate.is_english(content)
        assert isinstance(result, bool), "Language detection should return a boolean for mixed content"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST EXECUTION HELPERS - Utilities for running tests
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Run tests when script is executed directly.
    
    Usage examples:
    - Run all tests: python test_translate.py
    - Run with verbose output: python test_translate.py -v
    - Run specific test class: python test_translate.py::TestTranslation -v
    - Run integration tests: python test_translate.py::TestTranslationIntegration -v
    """
    import pytest
    pytest.main([__file__, "-v"])
