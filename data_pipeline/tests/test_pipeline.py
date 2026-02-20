"""Tests for data pipeline stages."""
import pandas as pd
import pytest

from stages.validate import validate_data
from stages.transform import transform_data
from stages.enrich import enrich_data
from stages.sample import stratified_sample


@pytest.fixture
def sample_df():
    """Create sample survey data for testing."""
    return pd.DataFrame({
        "ResponseId": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "Country": ["United States", "USA", "United Kingdom", "Germany", "India",
                    "United States", "Canada", "France", "Japan", "Brazil"],
        "DevType": [
            "Developer, full-stack",
            "Developer, back-end",
            "Developer, full-stack",
            "Data scientist",
            "Developer, back-end",
            "DevOps specialist",
            "Developer, full-stack",
            "Data scientist",
            "Developer, back-end",
            "Developer, full-stack"
        ],
        "survey_year": ["2024", "2024", "2024", "2024", "2024",
                        "2025", "2025", "2025", "2025", "2025"],
        "WorkExp": [5, 10, 3, 8, 2, 15, 7, 4, 6, 12],
        "ConvertedCompYearly": [100000, 150000, 80000, 120000, 50000,
                                200000, 90000, 110000, 130000, 95000],
    })


class TestValidate:
    def test_validate_removes_duplicates(self, sample_df):
        df_dup = pd.concat([sample_df, sample_df.iloc[[0]]])
        valid, quarantine, stats = validate_data(df_dup)
        assert len(valid) == 10
        assert "duplicate" in str(stats["issues"]).lower()
    
    def test_validate_returns_all_valid_rows(self, sample_df):
        valid, quarantine, stats = validate_data(sample_df)
        assert stats["rows_valid"] == 10
        assert stats["rows_quarantined"] == 0


class TestTransform:
    def test_transform_normalizes_country(self, sample_df):
        transformed, stats = transform_data(sample_df)
        assert (transformed["Country"] == "United States").sum() == 3  # USA normalized
    
    def test_transform_cleans_year(self):
        df = pd.DataFrame({"survey_year": ["2024.0", "2025.0", "2023"]})
        transformed, stats = transform_data(df)
        assert list(transformed["survey_year"]) == ["2024", "2025", "2023"]


class TestEnrich:
    def test_enrich_adds_region(self, sample_df):
        enriched, stats = enrich_data(sample_df)
        assert "region_group" in enriched.columns
        assert enriched.loc[enriched["Country"] == "United States", "region_group"].iloc[0] == "North America"
    
    def test_enrich_adds_year_label(self, sample_df):
        enriched, stats = enrich_data(sample_df)
        assert "year_label" in enriched.columns
        assert "year_label" in stats["fields_added"]


class TestSample:
    def test_sample_reduces_rows(self, sample_df):
        sampled, stats = stratified_sample(sample_df, sample_pct=0.5, seed=42)
        assert len(sampled) < len(sample_df)
        assert stats["reduction_pct"] > 0
    
    def test_sample_preserves_roles(self, sample_df):
        sampled, stats = stratified_sample(sample_df, sample_pct=0.5, min_per_stratum=1, seed=42)
        original_roles = sample_df["DevType"].str.split(";").str[0].unique()
        sampled_roles = sampled["DevType"].str.split(";").str[0].unique()
        # All original roles should be represented (min 1 per stratum)
        assert len(sampled_roles) == len(original_roles)
    
    def test_sample_respects_min_per_stratum(self, sample_df):
        sampled, stats = stratified_sample(sample_df, sample_pct=0.01, min_per_stratum=1, seed=42)
        # Even with very low pct, should have at least 1 per role
        role_counts = sampled["DevType"].str.split(";").str[0].value_counts()
        assert all(role_counts >= 1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
