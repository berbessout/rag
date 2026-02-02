"""
Document Ingestion Test Suite

Tests for file selection and ingestion pipeline functionality.

Components Under Test:
- select_files(): File selection function for ingestion pipeline
"""

from pathlib import Path
import pytest
from src.ingestion.ingest import select_files


@pytest.fixture
def dummy_data_dir(tmp_path):
    """
    Create a temporary directory with dummy text files for testing.
    
    Args:
        tmp_path: pytest fixture providing a temporary directory
        
    Returns:
        Path: Path to the temporary directory containing dummy files
    """
    # Create dummy .txt files that simulate real project documents
    test_files = [
        "ADECCO - Digital Workplace.txt",
        "Air Liquide - Data Migration.txt", 
        "AG Insurance - Cloud migration for all business lines, data & processes from SAS to Azure.txt",
        "Airbus - Techrequest Application Development.txt",
        "Allianz - Data Preparation Refinement.txt",
        "Extra.txt"
    ]
    
    # Create each test file with dummy content
    for filename in test_files:
        (tmp_path / filename).write_text("Dummy content")
    
    return tmp_path


class TestFileSelection:
    """Test the file selection functionality for the ingestion pipeline."""
    
    def test_select_files_1(self, dummy_data_dir):
        """Test selecting a single file from the directory."""
        files = select_files('1', dummy_data_dir)
        
        assert len(files) == 1, "Should return exactly one file when '1' is specified"
        assert files[0].name == "ALSTOM - Sustainability Workshop.pptx"

    def test_select_files_5(self, dummy_data_dir):
        """Test selecting five files from the directory."""
        files = select_files('5', dummy_data_dir)
        
        assert len(files) == 5, "Should return exactly 5 files when '5' is specified"
        
        # Verify expected files in alphabetical order (with .pptx extension)
        expected_files = [
            "ADECCO - Digital Workplace.pptx",
            "Air Liquide - Data Migration.pptx",
            "AG Insurance - Cloud migration for all business lines, data & processes from SAS to Azure.pptx",
            "Airbus - Techrequest Application Development.pptx",
            "Allianz - Data Preparation Refinement.pptx"
        ]
        
        for i, expected_name in enumerate(expected_files):
            assert files[i].name == expected_name

    def test_select_files_all(self, dummy_data_dir):
        """Test selecting all files, filtering non-text files."""
        # Add a non-txt file to ensure it's properly filtered out
        (dummy_data_dir / "not_a_text_file.pdf").write_text("Should be ignored")
        
        # Get expected txt files only
        expected = set(f.name for f in dummy_data_dir.glob("*"))
        files = select_files('all', dummy_data_dir)
        result = set(f.name for f in files)
        
        assert result == expected, "Should return all files in directory"
        
        # Verify all returned objects are Path instances and exist
        assert all(isinstance(f, Path) for f in files), "All items should be Path objects"
        assert all(f.exists() for f in files), "All returned files should exist"


if __name__ == "__main__":
    """Run tests when script is executed directly."""
    import pytest
    pytest.main([__file__, "-v"])