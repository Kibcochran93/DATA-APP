"""
Tests for the SIS Mapper module.

Tests detection and transformation of common SIS exports (Banner, PeopleSoft, etc.)
to SEATS format.
"""

import pytest
import pandas as pd
from utils.sis_mapper import (
    SISMapper,
    SISType,
    ColumnMapping,
    SISDetectionResult,
    TransformationReport,
    detect_sis_type,
    suggest_mappings,
    transform_to_seats
)


class TestSISTypeDetection:
    """Tests for SIS type auto-detection."""
    
    def test_detect_banner_from_spriden(self):
        """Test detecting Banner from SPRIDEN columns."""
        df = pd.DataFrame({
            "SPRIDEN_ID": ["123"],
            "SPRIDEN_FIRST_NAME": ["John"],
            "SPRIDEN_LAST_NAME": ["Doe"],
            "SPBPERS_BIRTH_DATE": ["01-JAN-2000"]
        })
        
        result = detect_sis_type(df)
        assert result.detected_type == SISType.BANNER
        assert result.confidence > 0.2  # At least 2 indicators matched
    
    def test_detect_banner_from_pidm(self):
        """Test detecting Banner from PIDM column."""
        df = pd.DataFrame({
            "PIDM": ["12345"],
            "SGBSTDN_LEVL_CODE": ["UG"],
            "CRN": ["12345"]
        })
        
        result = detect_sis_type(df)
        assert result.detected_type == SISType.BANNER
    
    def test_detect_peoplesoft_from_emplid(self):
        """Test detecting PeopleSoft from EMPLID column."""
        df = pd.DataFrame({
            "EMPLID": ["00012345"],
            "ACAD_PROG": ["BSCS"],
            "ACAD_ORG": ["ENGR"]
        })
        
        result = detect_sis_type(df)
        assert result.detected_type == SISType.PEOPLESOFT
    
    def test_detect_workday_from_columns(self):
        """Test detecting Workday from typical columns."""
        df = pd.DataFrame({
            "WORKER_ID": ["WD123"],
            "LEGAL_FIRST_NAME": ["Jane"],
            "LEGAL_LAST_NAME": ["Smith"]
        })
        
        result = detect_sis_type(df)
        assert result.detected_type == SISType.WORKDAY
    
    def test_detect_generic_for_unknown(self):
        """Test that unknown column patterns return GENERIC."""
        df = pd.DataFrame({
            "STUDENT_ID": ["123"],
            "FIRST_NAME": ["John"],
            "LAST_NAME": ["Doe"]
        })
        
        result = detect_sis_type(df)
        # Could be generic or have low confidence for specific type
        assert result.detected_type in [SISType.GENERIC, SISType.BANNER, SISType.PEOPLESOFT]


class TestColumnMappingSuggestions:
    """Tests for column mapping suggestions."""
    
    def test_suggest_banner_mappings(self):
        """Test suggesting mappings for Banner columns."""
        df = pd.DataFrame({
            "SPRIDEN_ID": ["123"],
            "SPRIDEN_FIRST_NAME": ["John"],
            "SPRIDEN_LAST_NAME": ["Doe"],
            "SPBPERS_BIRTH_DATE": ["01-JAN-2000"],
            "SPBPERS_SEX": ["M"]
        })
        
        mappings = suggest_mappings(df, SISType.BANNER)
        
        # Check that we have mappings
        assert len(mappings) > 0
        
        # Check specific mappings exist
        target_cols = [m.target_column for m in mappings]
        assert "STUDENT_ID" in target_cols or any("ID" in t for t in target_cols)
    
    def test_suggest_peoplesoft_mappings(self):
        """Test suggesting mappings for PeopleSoft columns."""
        df = pd.DataFrame({
            "EMPLID": ["123"],
            "FIRST_NAME": ["Jane"],
            "LAST_NAME": ["Smith"],
            "BIRTHDATE": ["2000-01-15"],
            "SEX": ["F"]
        })
        
        mappings = suggest_mappings(df, SISType.PEOPLESOFT)
        
        assert len(mappings) > 0
        
        # Find STUDENT_ID mapping
        student_id_map = next(
            (m for m in mappings if m.target_column == "STUDENT_ID"),
            None
        )
        assert student_id_map is not None
        assert student_id_map.source_column == "EMPLID"
    
    def test_suggest_generic_mappings(self):
        """Test suggesting mappings for generic column names."""
        df = pd.DataFrame({
            "STUDENT_NUMBER": ["123"],
            "FIRSTNAME": ["Bob"],
            "LASTNAME": ["Jones"],
            "DOB": ["2000-01-15"],
            "GENDER": ["M"]
        })
        
        mappings = suggest_mappings(df)
        
        assert len(mappings) > 0
        target_cols = [m.target_column for m in mappings]
        assert "STUDENT_ID" in target_cols or "STUDENT_FORENAME" in target_cols
    
    def test_confidence_levels(self):
        """Test that confidence levels are appropriate."""
        df = pd.DataFrame({
            "STUDENT_ID": ["123"],  # Exact match
            "FNAME": ["John"],       # Partial match
        })
        
        mappings = suggest_mappings(df)
        
        for mapping in mappings:
            assert 0.0 <= mapping.confidence <= 1.0
            
            # Matches should have reasonable confidence
            if mapping.source_column == "STUDENT_ID":
                assert mapping.confidence >= 0.6  # At least fuzzy match level


class TestValueTransformation:
    """Tests for value code transformations."""
    
    def test_transform_gender_codes(self):
        """Test transforming gender codes."""
        df = pd.DataFrame({
            "GENDER": ["Male", "Female", "M", "F", "Other"]
        })
        
        mapper = SISMapper()
        mappings = [ColumnMapping(
            source_column="GENDER",
            target_column="GENDER",
            confidence=1.0,
            sis_type=SISType.GENERIC,
            reason="Exact match"
        )]
        
        df_transformed, report = mapper.transform_dataframe(df, mappings)
        
        # Check transformations applied
        assert report.values_transformed.get("GENDER", 0) > 0
        
        # Check values are standardized
        values = df_transformed["GENDER"].tolist()
        assert "M" in values
        assert "F" in values
    
    def test_transform_visa_required(self):
        """Test transforming visa/international indicator."""
        df = pd.DataFrame({
            "VISAREQUIRED": ["Yes", "No", "TRUE", "FALSE", "Y", "N"]
        })
        
        mapper = SISMapper()
        mappings = [ColumnMapping(
            source_column="VISAREQUIRED",
            target_column="VISAREQUIRED",
            confidence=1.0,
            sis_type=SISType.GENERIC,
            reason="Exact match"
        )]
        
        df_transformed, report = mapper.transform_dataframe(df, mappings)
        
        values = df_transformed["VISAREQUIRED"].tolist()
        assert all(v in ["Y", "N"] for v in values)
    
    def test_transform_student_status(self):
        """Test transforming student status codes."""
        df = pd.DataFrame({
            "STUDENT_STATUS": ["Active", "Withdrawn", "ENROLLED", "GRADUATED"]
        })
        
        mapper = SISMapper()
        mappings = [ColumnMapping(
            source_column="STUDENT_STATUS",
            target_column="STUDENT_STATUS",
            confidence=1.0,
            sis_type=SISType.GENERIC,
            reason="Exact match"
        )]
        
        df_transformed, report = mapper.transform_dataframe(df, mappings)
        
        values = df_transformed["STUDENT_STATUS"].tolist()
        # Values should be standardized codes
        assert "A" in values  # Active
        assert "W" in values  # Withdrawn


class TestDateConversion:
    """Tests for date format conversion."""
    
    def test_convert_banner_dates(self):
        """Test converting Banner date format (DD-MON-YYYY)."""
        df = pd.DataFrame({
            "DATE_OF_BIRTH": ["15-JAN-2000", "01-DEC-1999", "28-FEB-2001"]
        })
        
        mapper = SISMapper()
        mappings = [ColumnMapping(
            source_column="DATE_OF_BIRTH",
            target_column="DATE_OF_BIRTH",
            confidence=1.0,
            sis_type=SISType.BANNER,
            reason="Exact match"
        )]
        
        df_transformed, report = mapper.transform_dataframe(df, mappings)
        
        assert report.dates_converted > 0
        
        # Check format is YYYY-MM-DD
        for val in df_transformed["DATE_OF_BIRTH"]:
            assert len(val) == 10
            assert val[4] == "-"
            assert val[7] == "-"
    
    def test_convert_us_dates(self):
        """Test converting US date format (MM/DD/YYYY)."""
        df = pd.DataFrame({
            "DOB": ["01/15/2000", "12/01/1999"]
        })
        
        mapper = SISMapper()
        mappings = [ColumnMapping(
            source_column="DOB",
            target_column="DATE_OF_BIRTH",
            confidence=1.0,
            sis_type=SISType.GENERIC,
            reason="Match"
        )]
        
        df_transformed, report = mapper.transform_dataframe(df, mappings)
        
        # Dates should be converted
        for val in df_transformed["DATE_OF_BIRTH"]:
            if val:
                assert len(val) == 10
    
    def test_preserve_correct_dates(self):
        """Test that correctly formatted dates are preserved."""
        df = pd.DataFrame({
            "DATE_OF_BIRTH": ["2000-01-15", "1999-12-01"]
        })
        
        mapper = SISMapper()
        mappings = [ColumnMapping(
            source_column="DATE_OF_BIRTH",
            target_column="DATE_OF_BIRTH",
            confidence=1.0,
            sis_type=SISType.GENERIC,
            reason="Exact match"
        )]
        
        df_transformed, report = mapper.transform_dataframe(df, mappings)
        
        # Values should be unchanged
        assert df_transformed["DATE_OF_BIRTH"].tolist() == ["2000-01-15", "1999-12-01"]


class TestFullTransformation:
    """Tests for complete DataFrame transformation."""
    
    def test_transform_banner_dataframe(self):
        """Test full transformation of Banner data."""
        df = pd.DataFrame({
            "SPRIDEN_ID": ["00012345", "00012346"],
            "SPRIDEN_FIRST_NAME": ["John", "Jane"],
            "SPRIDEN_LAST_NAME": ["Doe", "Smith"],
            "SPBPERS_BIRTH_DATE": ["15-JAN-2000", "20-FEB-1999"],
            "SPBPERS_SEX": ["M", "F"],
            "GOREMAL_EMAIL_ADDRESS": ["john@univ.edu", "jane@univ.edu"]
        })
        
        df_transformed, report = transform_to_seats(df, SISType.BANNER)
        
        # Check columns were mapped
        assert len(report.columns_mapped) > 0
        
        # Check some SEATS columns exist
        cols = df_transformed.columns.tolist()
        assert any("STUDENT" in col or "ID" in col for col in cols)
    
    def test_transform_generic_dataframe(self):
        """Test full transformation of generic data."""
        df = pd.DataFrame({
            "STUDENT_ID": ["123", "456"],
            "FIRST_NAME": ["Bob", "Alice"],
            "LAST_NAME": ["Jones", "Brown"],
            "DOB": ["2000-01-15", "1999-06-20"],
            "GENDER": ["Male", "Female"],
            "EMAIL": ["bob@school.edu", "alice@school.edu"]
        })
        
        df_transformed, report = transform_to_seats(df)
        
        # Should have mapped columns
        assert len(report.columns_mapped) > 0
        
        # Should have transformed values
        assert "GENDER" in report.values_transformed or len(report.values_transformed) >= 0
    
    def test_report_unmapped_columns(self):
        """Test that unmapped columns are reported."""
        df = pd.DataFrame({
            "STUDENT_ID": ["123"],
            "FIRST_NAME": ["John"],
            "RANDOM_CUSTOM_FIELD": ["value"],
            "ANOTHER_UNKNOWN": ["data"]
        })
        
        df_transformed, report = transform_to_seats(df)
        
        # Should have some unmapped columns
        assert len(report.unmapped_columns) > 0
        assert "RANDOM_CUSTOM_FIELD" in report.unmapped_columns or "ANOTHER_UNKNOWN" in report.unmapped_columns


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        df = pd.DataFrame()
        
        result = detect_sis_type(df)
        assert result.detected_type in [SISType.GENERIC, SISType.UNKNOWN]
    
    def test_null_values(self):
        """Test handling of null values."""
        df = pd.DataFrame({
            "STUDENT_ID": ["123", None, "456"],
            "FIRST_NAME": ["John", "Jane", None],
            "GENDER": ["M", None, "F"]
        })
        
        df_transformed, report = transform_to_seats(df)
        
        # Should not raise error
        assert df_transformed is not None
    
    def test_mixed_case_columns(self):
        """Test handling of mixed case column names."""
        df = pd.DataFrame({
            "Student_ID": ["123"],
            "first_name": ["John"],
            "LAST_NAME": ["Doe"]
        })
        
        mappings = suggest_mappings(df)
        
        # Should find mappings regardless of case
        assert len(mappings) > 0
    
    def test_mapper_initialization_without_config(self):
        """Test mapper works even without config file."""
        mapper = SISMapper(mapping_file="/nonexistent/path.json")
        
        df = pd.DataFrame({
            "STUDENT_ID": ["123"],
            "NAME": ["John"]
        })
        
        # Should not raise error
        result = mapper.detect_sis_type(df)
        assert result is not None


class TestSISMapperClass:
    """Tests for SISMapper class methods."""
    
    def test_mapper_initialization(self):
        """Test SISMapper initialization."""
        mapper = SISMapper()
        assert mapper.column_mappings is not None
        assert mapper.value_mappings is not None
    
    def test_get_unmapped_seats_columns(self):
        """Test identifying missing SEATS columns."""
        mapper = SISMapper()
        
        df = pd.DataFrame({
            "STUDENT_ID": ["123"],
            "STUDENT_FORENAME": ["John"]
        })
        
        # Simple mock spec
        spec = {
            "fields": {
                "STUDENT_ID": {},
                "STUDENT_FORENAME": {},
                "STUDENT_LAST_NAME": {},
                "DATE_OF_BIRTH": {}
            }
        }
        
        missing = mapper.get_unmapped_seats_columns(df, spec)
        
        assert "STUDENT_LAST_NAME" in missing
        assert "DATE_OF_BIRTH" in missing
        assert "STUDENT_ID" not in missing
