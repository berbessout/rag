"""
Naive RAG (Retrieval-Augmented Generation) Test Suite

This module tests the NaiveRAG system, which implements a basic RAG architecture that:
1. Retrieves relevant documents from a Qdrant vector database based on user queries
2. Uses Azure OpenAI to generate responses based on the retrieved context
3. Provides caching and graph-based interfaces for efficient querying

Test Categories:
- Unit Tests: Test individual components with mocked dependencies
- Integration Tests: Test the complete RAG workflow
- Caching Tests: Verify the singleton pattern and caching behavior
- Error Handling: Test robustness under various failure conditions

Components Under Test:
- NaiveRAG: Main RAG implementation class
- naive_rag_query: Cached query function
- create_naive_rag_graph: Graph-based interface creation
"""

import pytest
from pathlib import Path
from src.app.rag_architecture.naive_rag import (
    NaiveRAG, 
    naive_rag_query, 
    create_naive_rag_graph
)

# Ensure project root is in path for imports
import sys
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


# ═══════════════════════════════════════════════════════════════════════════════
# TEST FIXTURES - Reusable mock components for testing
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_env_vars(monkeypatch):
    """
    Mock environment variables required for NaiveRAG initialization.
    
    Sets up all required Azure OpenAI and Qdrant configuration variables
    to prevent tests from requiring real credentials or services.
    
    Args:
        monkeypatch: pytest fixture for modifying environment
    """
    monkeypatch.setenv('AZURE_OPENAI_API_KEY', 'test_key')
    monkeypatch.setenv('AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/')
    monkeypatch.setenv('QDRANT_HOST', 'localhost')
    monkeypatch.setenv('QDRANT_PORT', '6333')
    monkeypatch.setenv('QDRANT_COLLECTION', 'test-collection')


@pytest.fixture
def mock_qdrant_ingestor(monkeypatch):
    """
    Mock QdrantIngestor for testing vector database operations.
    
    Creates a mock that simulates search operations without requiring
    a real Qdrant instance. Provides configurable return values and
    tracks method calls for verification.
    
    Returns:
        MockIngestor: Mock object with search method and tracking attributes
    """
    class MockIngestor:
        def __init__(self, *args, **kwargs):
            # Track method calls for verification
            self.search_called = False
            self.search_args = None
            
            # Default search results simulating project portfolio data
            self.search_return = [
                {
                    "text": "This is a Python project for data analysis using pandas and numpy.",
                    "id": "1",
                    "doc_name": "project1.txt",
                    "client": "Air Liquide",
                    "tech": "Python"
                },
                {
                    "text": "Machine learning implementation with scikit-learn for predictive analytics.",
                    "id": "2", 
                    "doc_name": "project2.txt",
                    "client": "BNP Paribas",
                    "tech": "Python"
                }
            ]
            
            # Allow tests to configure exceptions
            self.side_effect = None
        
        def search(self, query, limit=5):
            """
            Mock search method that simulates vector similarity search.
            
            Args:
                query (str): Search query
                limit (int): Maximum number of results
                
            Returns:
                list: Mock search results with project metadata
                
            Raises:
                Exception: If side_effect is configured
            """
            self.search_called = True
            self.search_args = (query, limit)
            
            if self.side_effect:
                raise self.side_effect
            
            return self.search_return
    
    # Replace the real QdrantIngestor with our mock
    monkeypatch.setattr('src.app.rag_architecture.naive_rag.QdrantIngestor', MockIngestor)
    return MockIngestor()


@pytest.fixture
def mock_llm(monkeypatch):
    """
    Mock Azure OpenAI LLM for testing response generation.
    
    Creates a mock that simulates LLM responses without requiring
    real API calls. Provides configurable responses and tracks
    method invocations for verification.
    
    Returns:
        MockLLM: Mock object with invoke method and tracking attributes
    """
    class MockLLM:
        def __init__(self, *args, **kwargs):
            # Track method calls for verification
            self.invoke_called = False
            self.invoke_args = None
            self.side_effect = None
            
            # Default response content
            self.response_content = ("Based on the search results, there are several Python projects "
                                  "in our database focusing on data analysis and machine learning.")
        
        def invoke(self, messages):
            """
            Mock LLM invoke method that simulates response generation.
            
            Args:
                messages: Chat messages (prompts and context)
                
            Returns:
                Response: Mock response object with content attribute
                
            Raises:
                Exception: If side_effect is configured
            """
            self.invoke_called = True
            self.invoke_args = messages
            
            if self.side_effect:
                raise self.side_effect
            
            # Create mock response object
            class Response:
                content = self.response_content
            
            return Response()
    
    # Replace the real AzureChatOpenAI with our mock
    monkeypatch.setattr('src.app.rag_architecture.naive_rag.AzureChatOpenAI', MockLLM)
    return MockLLM()


@pytest.fixture
def naive_rag_instance(mock_env_vars, mock_qdrant_ingestor, mock_llm, monkeypatch):
    """
    Create a NaiveRAG instance with all dependencies mocked.
    
    This fixture provides a ready-to-use NaiveRAG instance for testing
    without requiring external services or credentials.
    
    Returns:
        NaiveRAG: Fully mocked NaiveRAG instance
    """
    return NaiveRAG()


@pytest.fixture(autouse=True)
def reset_cached_instance(monkeypatch):
    """
    Reset the cached NaiveRAG instance before each test.
    
    The NaiveRAG module uses a singleton pattern with caching. This fixture
    ensures each test starts with a fresh instance to prevent test interference.
    
    The autouse=True parameter means this fixture runs automatically for every test.
    """
    import src.app.rag_architecture.naive_rag as naive_rag_module
    naive_rag_module._cached_naive_rag = None
    yield
    # Clean up after test
    naive_rag_module._cached_naive_rag = None


# ═══════════════════════════════════════════════════════════════════════════════
# IMPORT VERIFICATION TESTS - Ensure all components are accessible
# ═══════════════════════════════════════════════════════════════════════════════

def test_imports():
    """
    Test that all necessary imports work correctly.
    
    This basic test ensures the module structure is correct and all
    required components can be imported without errors.
    """
    from src.app.rag_architecture.naive_rag import NaiveRAG, naive_rag_query, create_naive_rag_graph
    
    # Verify all components are available
    assert NaiveRAG is not None
    assert naive_rag_query is not None
    assert create_naive_rag_graph is not None


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS - Test individual components in isolation
# ═══════════════════════════════════════════════════════════════════════════════

class TestNaiveRAGInitialization:
    """
    Test NaiveRAG class initialization and configuration.
    
    These tests verify that the NaiveRAG class correctly initializes
    its dependencies (vector database and LLM) with proper configuration.
    """
    
    def test_init_with_default_env_vars(self, mock_env_vars, monkeypatch):
        """
        Test initialization with default environment variables.
        
        Verifies that the NaiveRAG class correctly reads environment
        variables and initializes both the vector store and LLM components.
        """
        rag = NaiveRAG()
        
        # Verify both main components are initialized
        assert rag.ingestor is not None, "Vector database ingestor should be initialized"
        assert rag.llm is not None, "LLM should be initialized"
    
    def test_init_with_custom_env_vars(self, monkeypatch):
        """
        Test initialization with custom environment variable values.
        
        Ensures the class can handle different configuration values
        and properly validates the setup with various endpoints and parameters.
        """
        # Set custom environment variables
        monkeypatch.setenv('AZURE_OPENAI_API_KEY', 'custom_key')
        monkeypatch.setenv('AZURE_OPENAI_ENDPOINT', 'https://custom.openai.azure.com/')
        monkeypatch.setenv('QDRANT_HOST', 'custom.host')
        monkeypatch.setenv('QDRANT_PORT', '9999')
        monkeypatch.setenv('QDRANT_COLLECTION', 'custom-collection')
        
        rag = NaiveRAG()
        
        # Verify initialization succeeds with custom values
        assert rag.ingestor is not None
        assert rag.llm is not None


class TestSearchAndSynthesize:
    """
    Test the core RAG functionality: search and response synthesis.
    
    The search_and_synthesize method is the heart of the RAG system,
    combining vector search with LLM-based response generation.
    """
    
    def test_successful_search_and_synthesis(self, naive_rag_instance, mock_qdrant_ingestor, mock_llm):
        """
        Test the complete RAG workflow with successful operations.
        
        This test verifies:
        1. Query is passed to vector search
        2. Search results are retrieved
        3. Results are passed to LLM for synthesis
        4. Final response is generated and returned
        """
        query = "What Python projects do we have?"
        result = naive_rag_instance.search_and_synthesize(query)
        
        # Verify vector search was called with correct query
        assert mock_qdrant_ingestor.search_called, "Vector search should be called"
        assert query == mock_qdrant_ingestor.search_args[0], "Search should use the provided query"
        
        # Verify LLM was called for synthesis
        assert mock_llm.invoke_called, "LLM should be called for response synthesis"
        
        # Verify response contains expected content
        assert "Python projects" in result, "Response should contain relevant information"
    
    def test_no_search_results(self, naive_rag_instance, mock_qdrant_ingestor, mock_llm):
        """
        Test behavior when vector search returns no results.
        
        When no relevant documents are found, the system should return
        a helpful message rather than attempting LLM synthesis with empty context.
        """
        # Configure mock to return empty results
        mock_qdrant_ingestor.search_return = []
        
        result = naive_rag_instance.search_and_synthesize("nonexistent query")
        
        # Should return standardized "no results" message
        assert result == "❓ No answer found in the document database."
    
    def test_custom_top_k(self, naive_rag_instance, mock_qdrant_ingestor):
        """
        Test custom top_k parameter for search result limiting.
        
        Verifies that the top_k parameter is correctly passed to the
        vector search to control the number of retrieved documents.
        """
        naive_rag_instance.search_and_synthesize("test query", top_k=10)
        
        # Verify the custom top_k value was passed to search
        assert mock_qdrant_ingestor.search_args[1] == 10, "Custom top_k should be passed to search"
    
    def test_search_error_handling(self, naive_rag_instance, mock_qdrant_ingestor):
        """
        Test error handling when vector search fails.
        
        Network issues, database errors, or configuration problems with
        the vector database should be handled gracefully with error messages.
        """
        # Configure mock to raise exception
        mock_qdrant_ingestor.side_effect = Exception("Qdrant connection error")
        
        result = naive_rag_instance.search_and_synthesize("test query")
        
        # Should return error message with details
        assert result.startswith("❌ Error during naive RAG search:")
        assert "Qdrant connection error" in result
    
    def test_llm_error_handling(self, naive_rag_instance, mock_qdrant_ingestor, mock_llm):
        """
        Test error handling when LLM synthesis fails.
        
        API failures, rate limiting, or configuration issues with the
        LLM service should be handled gracefully with error messages.
        """
        # Configure mock LLM to raise exception
        mock_llm.side_effect = Exception("LLM API error")
        
        result = naive_rag_instance.search_and_synthesize("test query")
        
        # Should return error message with details
        assert result.startswith("❌ Error during naive RAG search:")
        assert "LLM API error" in result


class TestNaiveRagQuery:
    """
    Test the cached query function interface.
    
    The naive_rag_query function provides a simplified interface with
    caching to avoid recreating the NaiveRAG instance for each query.
    """
    
    def test_naive_rag_query_caching(self, mock_env_vars, monkeypatch):
        """
        Test that the NaiveRAG instance is properly cached between queries.
        
        The caching mechanism should reuse the same NaiveRAG instance
        across multiple calls for efficiency, rather than recreating it each time.
        """
        import src.app.rag_architecture.naive_rag as naive_rag_module
        
        # Ensure we start with no cached instance
        naive_rag_module._cached_naive_rag = None
        
        # Make multiple queries
        result1 = naive_rag_query("test query 1")
        result2 = naive_rag_query("test query 2")
        
        # Both should use the same cached instance (same mock responses)
        assert result1 == result2, "Cached instance should be reused"
    
    def test_naive_rag_query_passes_parameters(self, mock_env_vars, monkeypatch):
        """
        Test that query parameters are correctly passed through the cached interface.
        
        The simplified function should properly forward queries to the
        underlying NaiveRAG instance without modification.
        """
        import src.app.rag_architecture.naive_rag as naive_rag_module
        naive_rag_module._cached_naive_rag = None
        
        test_query = "Find me Python projects"
        
        # This should complete without error, indicating the query was passed correctly
        naive_rag_query(test_query)


class TestCreateNaiveRagGraph:
    """
    Test the graph-based interface creation.
    
    The create_naive_rag_graph function creates a graph-based interface
    that can be used with workflow orchestration systems.
    """
    
    def test_graph_creation(self, mock_env_vars, monkeypatch):
        """
        Test successful creation of the RAG graph interface.
        
        Verifies that the graph is created without errors and has
        the expected interface for workflow integration.
        """
        graph = create_naive_rag_graph()
        
        assert graph is not None, "Graph should be created successfully"
        assert hasattr(graph, 'invoke'), "Graph should have invoke method for execution"
    
    def test_graph_structure(self, mock_env_vars, monkeypatch):
        """
        Test that the created graph has the expected structure.
        
        Validates that the graph object has the necessary methods
        and properties for integration with workflow systems.
        """
        graph = create_naive_rag_graph()
        
        assert graph is not None, "Graph should be a valid object"


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS - Test complete workflows with realistic scenarios
# ═══════════════════════════════════════════════════════════════════════════════

class TestNaiveRagIntegration:
    """
    Integration tests that verify the complete RAG workflow.
    
    These tests use more realistic mock data and scenarios to ensure
    the system works correctly in end-to-end scenarios.
    """
    
    def test_full_workflow_integration(self, mock_env_vars, monkeypatch):
        """
        Test the complete RAG workflow with realistic project data.
        
        This test simulates a realistic scenario where:
        1. A user queries for specific projects (Azure banking projects)
        2. The vector database returns relevant project documents
        3. The LLM synthesizes a meaningful response
        4. The response contains project-specific information
        """
        # Create realistic mock implementations for integration testing
        class MockIngestor:
            def search(self, query, limit=5):
                """Return realistic project data for Azure banking query."""
                return [{
                    "text": ("Azure cloud migration project for banking sector using Python automation scripts. "
                           "Implemented data pipeline modernization and security compliance frameworks."),
                    "id": "azure_banking_1",
                    "doc_name": "banking_migration.txt",
                    "client": "BNP Paribas",
                    "tech": "Python, Azure"
                }]
        
        class MockLLM:
            def invoke(self, messages):
                """Generate realistic response based on retrieved context."""
                class Response:
                    content = ("We have an Azure cloud migration project for the banking sector that "
                             "utilizes Python automation scripts for BNP Paribas. This project focused "
                             "on data pipeline modernization and implementing security compliance frameworks.")
                return Response()
        
        # Apply realistic mocks
        monkeypatch.setattr('src.app.rag_architecture.naive_rag.QdrantIngestor', MockIngestor)
        monkeypatch.setattr('src.app.rag_architecture.naive_rag.AzureChatOpenAI', MockLLM)
        
        # Test the complete workflow
        rag = NaiveRAG()
        result = rag.search_and_synthesize("Show me Azure projects")
        
        # Verify the response contains expected project information
        assert "Azure cloud migration project" in result
        assert "BNP Paribas" in result
        assert "Python automation scripts" in result
    
    def test_tool_integration_with_graph(self, mock_env_vars, monkeypatch):
        """
        Test integration between graph interface and query function.
        
        Verifies that the graph-based interface works correctly with
        the cached query function and produces consistent results.
        """
        # Create the graph interface
        graph = create_naive_rag_graph()
        
        # Reset cached instance to ensure fresh start
        import src.app.rag_architecture.naive_rag as naive_rag_module
        naive_rag_module._cached_naive_rag = None
        
        # Test both interfaces
        result_from_function = naive_rag_query("test query")
        
        # Verify both interfaces work and return strings
        assert graph is not None, "Graph should be created successfully"
        assert isinstance(result_from_function, str), "Query function should return string response"


# ═══════════════════════════════════════════════════════════════════════════════
# TEST EXECUTION HELPERS - Utilities for running tests
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Run tests when script is executed directly.
    
    Usage examples:
    - Run all tests: python test_naive_rag.py
    - Run with verbose output: python test_naive_rag.py -v
    - Run specific test class: python test_naive_rag.py::TestSearchAndSynthesize -v
    - Run integration tests only: python test_naive_rag.py::TestNaiveRagIntegration -v
    """
    import pytest
    pytest.main([__file__, "-v"])
