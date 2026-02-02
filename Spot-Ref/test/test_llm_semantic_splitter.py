"""
LLM Semantic Splitter Test Suite

This module contains comprehensive tests for the semantic document splitting functionality, which handles:
- Semantic splitting of documents using LLM-based analysis
- Metadata extraction from document content (client, technology, location)
- Environment variable validation for Azure OpenAI integration
- Integration with file conversion and document processing pipeline

Test Categories:
- Basic Functionality Tests: Verify core semantic splitting operations
- Metadata Extraction Tests: Test extraction of structured metadata
- Environment Validation Tests: Test Azure OpenAI configuration validation
- Integration Tests: Test with real document processing workflows

Components Under Test:
- semantic_split(): Main function for LLM-based document segmentation
"""

import os
import pytest
from pathlib import Path
from src.convert_files import convert_files
import src.llm_semantic_splitter as lss


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FIXTURES - Reusable test setup components
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    """
    Set up environment variables required for Azure OpenAI integration.
    
    This fixture automatically configures the necessary environment variables
    for LLM-based semantic splitting functionality. It runs for every test
    to ensure consistent environment setup.
    
    Args:
        monkeypatch: pytest fixture for modifying environment variables
    """
    # Ensure Azure OpenAI environment variables are available
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", os.getenv("AZURE_OPENAI_API_KEY", "your-api-key"))
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", os.getenv("AZURE_OPENAI_ENDPOINT", "your-endpoint"))
    monkeypatch.setenv("OPENAI_API_VERSION", os.getenv("OPENAI_API_VERSION", "2024-02-15-preview"))


# ═══════════════════════════════════════════════════════════════════════════════
# BASIC FUNCTIONALITY TESTS - Verify core semantic splitting operations
# ═══════════════════════════════════════════════════════════════════════════════

class TestSemanticSplitting:
    """
    Test the core semantic splitting functionality.
    
    These tests verify that the semantic_split function correctly processes
    documents and returns properly structured chunks and metadata.
    """
    
    def test_semantic_split_basic(self):
        """
        Test basic semantic splitting with simple document content.
        
        This test verifies that the semantic splitting function:
        1. Accepts document source and content parameters
        2. Returns chunks and metadata in the expected format
        3. Maintains proper data structure relationships
        4. Handles basic document processing workflow
        """
        # Test input parameters
        document_source = "test_doc.txt"
        document_context = "This is a test document for semantic splitting."
        
        # Perform semantic splitting with specified chunk size
        chunks, metadata = lss.semantic_split(document_source, document_context, max_chunk_size=1000)
        
        # Verify return value structure and types
        assert isinstance(chunks, list), "Chunks should be returned as a list"
        assert isinstance(metadata, list), "Metadata should be returned as a list"
        assert len(chunks) == len(metadata), "Number of chunks should match number of metadata entries"
        
        # Verify metadata structure contains required fields
        for meta in metadata:
            assert "doc_name" in meta, "Metadata should contain doc_name field"
            assert meta["doc_name"] == document_source, "doc_name should match input document source"
            assert "chunk_id" in meta, "Metadata should contain chunk_id field for tracking"

    def test_semantic_split_env_missing(self, monkeypatch):
        """
        Test error handling when required environment variables are missing.
        
        The semantic splitting function requires Azure OpenAI credentials.
        When these are missing, it should raise appropriate errors rather than fail silently.
        """
        # Remove critical environment variables to simulate missing configuration
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        
        # Should raise RuntimeError for missing environment configuration
        with pytest.raises(RuntimeError) as excinfo:
            lss.semantic_split("doc.txt", "context")
            
        # Verify error message mentions missing environment variables
        assert "Missing environment variable" in str(excinfo.value), "Error should mention missing environment variables"


# ═══════════════════════════════════════════════════════════════════════════════
# METADATA EXTRACTION TESTS - Test extraction of structured metadata
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetadataExtraction:
    """
    Test metadata extraction from real document content.
    
    These tests verify that the semantic splitter correctly extracts
    structured metadata from actual project documents.
    """
    
    def test_semantic_split_with_real_document(self):
        """
        Test semantic splitting with real PowerPoint document content.
        
        This integration test uses an actual project document to verify:
        1. File conversion integration works correctly
        2. Metadata extraction identifies correct project details
        3. Client, technology, and other fields are properly parsed
        4. Document structure is maintained through the pipeline
        """
        # Use real document from test data
        input_path = Path('public/Customer_pdf')
        input_text = convert_files(filename='Air Liquide - Data Migration.pptx', input_path=input_path)
        
        # Perform semantic splitting on real document content
        chunks, metadata = lss.semantic_split('Air Liquide - Data Migration.pptx', input_text)
        
        # Verify basic structure
        assert len(metadata) > 0, "Metadata list should not be empty for real document"
        
        # Verify metadata contains expected project information
        for meta in metadata:
            # Verify required metadata fields are present
            assert "doc_name" in meta, "Metadata should contain doc_name field"
            assert meta["doc_name"] == "Air Liquide - Data Migration.pptx", "doc_name should match input filename"
            
            # Verify client information extraction
            assert "client" in meta, "Metadata should contain client field"
            assert meta["client"] == "Air Liquide", "Client should be correctly extracted from filename"
            
            # Verify industry/field classification
            assert "field" in meta, "Metadata should contain field field"
            assert meta["field"] == "Energy", "Field should be correctly classified for Air Liquide"
            
            # Verify technology stack extraction
            assert "tech" in meta, "Metadata should contain tech field"
            tech_stack = meta["tech"]
            assert "Python" in tech_stack, "Technology stack should include Python"
            assert "Power BI" in tech_stack, "Technology stack should include Power BI"
            
            # Verify location/geography information
            assert "localisation" in meta, "Metadata should contain localisation field"


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS - Test with document processing workflows
# ═══════════════════════════════════════════════════════════════════════════════

class TestSemanticSplitterIntegration:
    """
    Integration tests for semantic splitter with broader document processing.
    
    These tests verify that semantic splitting works correctly when integrated
    with file conversion, translation, and other document processing steps.
    """
    
    def test_chunking_consistency(self):
        """
        Test that semantic chunking produces consistent results.
        
        Multiple runs with the same input should produce consistent
        chunk boundaries and metadata extraction results.
        """
        document_source = "consistency_test.txt"
        document_context = "This is a longer test document that should be split into multiple chunks for consistency testing."
        
        # Run semantic splitting multiple times
        chunks1, metadata1 = lss.semantic_split(document_source, document_context, max_chunk_size=500)
        chunks2, metadata2 = lss.semantic_split(document_source, document_context, max_chunk_size=500)
        
        # Results should be consistent across runs
        assert len(chunks1) == len(chunks2), "Chunk count should be consistent across runs"
        assert len(metadata1) == len(metadata2), "Metadata count should be consistent across runs"

    def test_chunk_size_parameter(self):
        """
        Test that the max_chunk_size parameter affects splitting behavior.
        
        Different chunk size limits should produce different numbers of chunks
        while maintaining content integrity and metadata consistency.
        """
        document_source = "chunk_size_test.txt"
        # Create longer content to test chunking behavior
        document_context = "This is a test document with sufficient content to test chunk size parameters. " * 20
        
        # Test with different chunk sizes
        small_chunks, small_metadata = lss.semantic_split(document_source, document_context, max_chunk_size=100)
        large_chunks, large_metadata = lss.semantic_split(document_source, document_context, max_chunk_size=1000)
        
        # Smaller chunk size should generally produce more chunks
        # (though LLM-based splitting may vary based on semantic boundaries)
        assert len(small_chunks) >= len(large_chunks), "Smaller chunk size should not produce fewer chunks"
        
        # All chunks should have consistent metadata structure
        for metadata_list in [small_metadata, large_metadata]:
            for meta in metadata_list:
                assert "doc_name" in meta, "All metadata should contain doc_name"
                assert meta["doc_name"] == document_source, "All metadata should reference correct document"


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLING TESTS - Test robustness under various failure conditions
# ═══════════════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    """
    Test error handling and edge cases for semantic splitting.
    
    These tests ensure the system handles various error conditions
    and edge cases gracefully without crashing.
    """
    
    def test_empty_document_content(self):
        """
        Test handling of empty or minimal document content.
        
        Empty or very short documents should be handled gracefully
        without causing errors in the semantic splitting process.
        """
        # Test with empty content
        chunks_empty, metadata_empty = lss.semantic_split("empty.txt", "")
        assert isinstance(chunks_empty, list), "Should return list for empty content"
        assert isinstance(metadata_empty, list), "Should return metadata list for empty content"
        
        # Test with minimal content
        chunks_minimal, metadata_minimal = lss.semantic_split("minimal.txt", "Short.")
        assert isinstance(chunks_minimal, list), "Should return list for minimal content"
        assert isinstance(metadata_minimal, list), "Should return metadata list for minimal content"

    def test_special_characters_in_content(self):
        """
        Test handling of special characters and encoding in document content.
        
        Documents with special characters, emojis, or non-ASCII content
        should be processed correctly without encoding errors.
        """
        # Test content with special characters and emojis
        special_content = "Document with special chars: àáâãäå, 中文, русский, 🚀📊💼"
        
        chunks, metadata = lss.semantic_split("special_chars.txt", special_content)
        
        # Should handle special characters without errors
        assert isinstance(chunks, list), "Should handle special characters in content"
        assert isinstance(metadata, list), "Should generate metadata for special character content"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST EXECUTION HELPERS - Utilities for running tests
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Run tests when script is executed directly.
    
    Usage examples:
    - Run all tests: python test_llm_semantic_splitter.py
    - Run with verbose output: python test_llm_semantic_splitter.py -v
    - Run specific test class: python test_llm_semantic_splitter.py::TestMetadataExtraction -v
    - Run integration tests: python test_llm_semantic_splitter.py::TestSemanticSplitterIntegration -v
    """
    import pytest
    pytest.main([__file__, "-v"])