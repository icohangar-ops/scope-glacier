"""Basic smoke tests for scope-glacier models and services."""

import pytest


class TestEnergyCommodity:
    """Tests for the EnergyCommodity dataclass."""

    def test_create_commodity_default(self):
        from src.models.energy_commodity import EnergyCommodity
        c = EnergyCommodity(code="WTI", name="West Texas Intermediate")
        assert c.code == "WTI"
        assert c.commodity_id == "NRG_WTI"
        assert c.current_price == 0.0

    def test_create_all_commodities(self):
        from src.models.energy_commodity import EnergyCommodity
        all_c = EnergyCommodity.create_all()
        assert len(all_c) == 6
        codes = {c.code for c in all_c}
        assert "WTI" in codes
        assert "BRENT" in codes
        assert "HH" in codes

    def test_to_dict_roundtrip(self):
        from src.models.energy_commodity import EnergyCommodity
        c = EnergyCommodity(code="WTI", name="West Texas Intermediate", current_price=75.0)
        d = c.to_dict()
        assert d["code"] == "WTI"
        assert d["energy_type"] == "Crude Oil"
        restored = EnergyCommodity.from_dict(d)
        assert restored.code == "WTI"
        assert restored.current_price == 75.0

    def test_energy_type_enum(self):
        from src.models.energy_commodity import EnergyType
        assert EnergyType.CRUDE_OIL.value == "Crude Oil"
        assert EnergyType.NATURAL_GAS.value == "Natural Gas"


class TestGlacierIntelligenceService:
    """Tests for GlacierIntelligenceService scoring methods."""

    def test_supply_demand_score_high_utilization(self):
        from src.services.glacier_intelligence import GlacierIntelligenceService
        svc = GlacierIntelligenceService(bedrock_client=None)
        # Mock out the BedrockClient import to avoid errors
        svc._client = None
        score = svc.compute_supply_demand_score(balance_pct=97, inventory_days=20)
        assert 0 <= score <= 100
        assert score > 50  # tight supply = bullish

    def test_supply_demand_score_low_utilization(self):
        from src.services.glacier_intelligence import GlacierIntelligenceService
        svc = GlacierIntelligenceService(bedrock_client=None)
        svc._client = None
        score = svc.compute_supply_demand_score(balance_pct=70, inventory_days=70)
        assert 0 <= score <= 100
        assert score < 50  # oversupply = bearish

    def test_price_momentum_score_positive(self):
        from src.services.glacier_intelligence import GlacierIntelligenceService
        svc = GlacierIntelligenceService(bedrock_client=None)
        svc._client = None
        score = svc.compute_price_momentum_score(return_30d=20.0, volatility=15.0)
        assert 0 <= score <= 100
        assert score > 50

    def test_price_momentum_score_negative(self):
        from src.services.glacier_intelligence import GlacierIntelligenceService
        svc = GlacierIntelligenceService(bedrock_client=None)
        svc._client = None
        score = svc.compute_price_momentum_score(return_30d=-20.0, volatility=60.0)
        assert 0 <= score <= 100
        assert score < 50

    def test_geopolitical_score(self):
        from src.services.glacier_intelligence import GlacierIntelligenceService
        svc = GlacierIntelligenceService(bedrock_client=None)
        svc._client = None
        score = svc.compute_geopolitical_score(risk_level=80, opec_compliance=60)
        assert 0 <= score <= 100

    def test_seasonal_score_driving(self):
        from src.services.glacier_intelligence import GlacierIntelligenceService
        svc = GlacierIntelligenceService(bedrock_client=None)
        svc._client = None
        score = svc.compute_seasonal_score(month=6, is_driving_season=True)
        assert 0 <= score <= 100
        assert score > 50

    def test_generate_signal(self):
        from src.services.glacier_intelligence import GlacierIntelligenceService
        svc = GlacierIntelligenceService(bedrock_client=None)
        svc._client = None
        signal = svc.generate_signal("WTI", utilization_pct=95, inventory_days=25)
        assert signal.commodity_code == "WTI"
        assert 0 <= signal.glacier_score <= 100
