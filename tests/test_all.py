"""Tests for Scope.Glacier domain models and services."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from src.models.energy_commodity import EnergyCommodity, EnergyType, ENERGY_COMMODITIES
from src.models.price_series import PriceSeries, PricePoint
from src.models.supply_demand import SupplyDemandBalance
from src.models.refinery import Refinery, RefineryStatus
from src.models.pipeline import Pipeline, PipelineStatus
from src.models.glacier_signal import GlacierSignal, SignalRating, SCORE_WEIGHTS
from src.services.eia_service import EIAService
from src.services.pricing_service import EnergyPricingService
from src.services.glacier_intelligence import GlacierIntelligenceService


# ==================== MODELS ====================
class TestEnergyCommodity:
    def test_create(self):
        c = EnergyCommodity(code="WTI", name="West Texas Intermediate", energy_type=EnergyType.CRUDE_OIL, current_price=78.50)
        assert c.code == "WTI"
        assert c.commodity_id == "NRG_WTI"

    def test_create_all(self):
        commodities = EnergyCommodity.create_all()
        assert len(commodities) == 6
        codes = [c.code for c in commodities]
        assert "WTI" in codes
        assert "HH" in codes

    def test_serialization(self):
        c = EnergyCommodity(code="BRENT", energy_type=EnergyType.CRUDE_OIL)
        d = c.to_dict()
        assert d["energy_type"] == "Crude Oil"

    def test_deserialization(self):
        d = {"code": "HH", "name": "Henry Hub", "energy_type": "Natural Gas"}
        c = EnergyCommodity.from_dict(d)
        assert c.energy_type == EnergyType.NATURAL_GAS


class TestPriceSeries:
    def _make_series(self, n=30):
        ps = PriceSeries(commodity_code="WTI")
        for i in range(n):
            ps.add_point(f"2024-{i//30+1:02d}-{i%28+1:02d}", 70.0 + i * 0.5)
        return ps

    def test_add_point(self):
        ps = PriceSeries(commodity_code="WTI")
        ps.add_point("2024-01-01", 75.0)
        assert len(ps.points) == 1
        assert ps.latest_price == 75.0

    def test_return_pct(self):
        ps = self._make_series(35)
        ret = ps.get_return_pct(30)
        assert ret is not None

    def test_return_insufficient_data(self):
        ps = self._make_series(10)
        assert ps.get_return_pct(30) is None

    def test_volatility(self):
        ps = self._make_series(30)
        vol = ps.get_volatility(20)
        assert vol >= 0

    def test_moving_avg(self):
        ps = self._make_series(25)
        ma = ps.get_moving_avg(20)
        assert ma is not None

    def test_moving_avg_short(self):
        ps = self._make_series(10)
        assert ps.get_moving_avg(20) is None

    def test_empty(self):
        ps = PriceSeries()
        assert ps.latest_price is None
        assert ps.get_return_pct(30) is None


class TestSupplyDemandBalance:
    def test_create(self):
        sd = SupplyDemandBalance(commodity_code="WTI", production_mbd=80, consumption_mbd=100,
                                  imports_mbd=8, exports_mbd=3, inventory_mmbl=4200)
        assert sd.implied_balance_mbd == pytest.approx(-15.0)
        assert sd.inventory_coverage_days == pytest.approx(42.0)
        assert sd.drawdown_risk == "Adequate"

    def test_critical_inventory(self):
        sd = SupplyDemandBalance(consumption_mbd=100, inventory_mmbl=1500)
        assert sd.drawdown_risk == "Critical"

    def test_serialization(self):
        sd = SupplyDemandBalance(commodity_code="HH", production_mbd=100, consumption_mbd=95)
        d = sd.to_dict()
        assert d["implied_balance_mbd"] == 5.0

    def test_zero_consumption(self):
        sd = SupplyDemandBalance(inventory_mmbl=1000, consumption_mbd=0)
        assert sd.inventory_coverage_days == 0.0


class TestRefinery:
    def test_create(self):
        r = Refinery(name="Motiva", region="Gulf Coast", capacity_bpd=600000, utilization_pct=90,
                      status=RefineryStatus.OPERATING)
        assert r.throughput_bpd == pytest.approx(540000)
        assert r.offline_bpd == pytest.approx(60000)

    def test_shutdown(self):
        r = Refinery(capacity_bpd=200000, utilization_pct=0, status=RefineryStatus.SHUTDOWN)
        assert r.offline_bpd == 200000

    def test_serialization(self):
        r = Refinery(name="Baytown", status=RefineryStatus.MAINTENANCE)
        d = r.to_dict()
        assert d["status"] == "Maintenance"

    def test_deserialization(self):
        d = {"name": "Port Arthur", "status": "Operating", "capacity_bpd": 300000}
        r = Refinery.from_dict(d)
        assert r.status == RefineryStatus.OPERATING


class TestPipeline:
    def test_create(self):
        p = Pipeline(name="Keystone", commodity="Crude Oil", origin="Canada", destination="US",
                      capacity_bpd=590000, current_flow_bpd=500000)
        assert p.utilization_pct == pytest.approx(84.7, rel=0.1)
        assert not p.is_disrupted

    def test_disrupted(self):
        p = Pipeline(status=PipelineStatus.FORCE_MAJEURE)
        assert p.is_disrupted

    def test_serialization(self):
        p = Pipeline(name="Colonial", status=PipelineStatus.REDUCED)
        d = p.to_dict()
        assert d["is_disrupted"] is True

    def test_deserialization(self):
        d = {"name": "Nord Stream", "status": "Shutdown"}
        p = Pipeline.from_dict(d)
        assert p.status == PipelineStatus.SHUTDOWN


class TestGlacierSignal:
    def test_create(self):
        s = GlacierSignal(commodity_code="WTI", supply_demand_score=80, price_momentum_score=70,
                           geopolitical_score=60, seasonal_score=55)
        assert s.glacier_score > 60
        assert s.signal_rating in (SignalRating.BUY, SignalRating.STRONG_BUY)

    def test_hold(self):
        s = GlacierSignal(commodity_code="HH", supply_demand_score=50, price_momentum_score=50,
                           geopolitical_score=50, seasonal_score=50)
        assert s.signal_rating == SignalRating.HOLD

    def test_weights(self):
        assert sum(SCORE_WEIGHTS.values()) == pytest.approx(1.0)

    def test_serialization(self):
        s = GlacierSignal(commodity_code="WTI")
        d = s.to_dict()
        assert d["signal_rating"] == "Hold"

    def test_deserialization(self):
        d = {"commodity_code": "BRENT", "glacier_score": 20.0, "supply_demand_score": 20.0,
             "price_momentum_score": 20.0, "geopolitical_score": 20.0, "seasonal_score": 20.0,
             "signal_rating": "Sell"}
        s = GlacierSignal.from_dict(d)
        assert s.signal_rating == SignalRating.SELL


# ==================== SERVICES ====================
@pytest.fixture
def mock_bedrock():
    c = MagicMock()
    c.chat.return_value = "Crude oil markets are tightening with OPEC+ cuts and strong demand."
    return c


class TestEIAService:
    def test_init(self):
        svc = EIAService(api_key="test")
        assert svc.api_key == "test"

    @patch.object(EIAService, "_get", return_value=None)
    def test_get_spot_prices_empty(self, mock_get):
        svc = EIAService()
        ps = svc.get_spot_prices("PET.RWTC.D")
        assert len(ps.points) == 0


class TestEnergyPricingService:
    def test_init(self):
        svc = EnergyPricingService(fred_key="test")
        assert svc.fred_key == "test"

    def test_get_natural_gas_no_key(self):
        import os
        old = os.environ.pop("FRED_API_KEY", None)
        old_eia = os.environ.pop("EIA_API_KEY", None)
        try:
            svc = EnergyPricingService()
            assert svc.fred_key == ""
            assert svc.get_natural_gas_price() is None
        finally:
            if old: os.environ["FRED_API_KEY"] = old
            if old_eia: os.environ["EIA_API_KEY"] = old_eia

    @patch("src.services.pricing_service.requests.Session.get")
    def test_get_crude_prices(self, mock_get):
        mock_get.return_value.json.return_value = {"observations": [{"value": "78.50"}]}
        svc = EnergyPricingService(fred_key="key")
        prices = svc.get_crude_oil_prices()
        assert prices["WTI"] == 78.50

    @patch("src.services.pricing_service.requests.Session.get")
    def test_get_crude_prices_error(self, mock_get):
        mock_get.return_value.json.return_value = {"observations": [{"value": "."}]}
        svc = EnergyPricingService(fred_key="key")
        prices = svc.get_crude_oil_prices()
        assert prices["WTI"] is None


class TestGlacierIntelligenceService:
    def test_supply_demand_score(self, mock_bedrock):
        svc = GlacierIntelligenceService(bedrock_client=mock_bedrock)
        assert svc.compute_supply_demand_score(95, 20) > 70

    def test_price_momentum_score(self, mock_bedrock):
        svc = GlacierIntelligenceService(bedrock_client=mock_bedrock)
        assert svc.compute_price_momentum_score(15, 15) > 60

    def test_geopolitical_score(self, mock_bedrock):
        svc = GlacierIntelligenceService(bedrock_client=mock_bedrock)
        assert svc.compute_geopolitical_score(80, 60) < 40

    def test_seasonal_score(self, mock_bedrock):
        svc = GlacierIntelligenceService(bedrock_client=mock_bedrock)
        assert svc.compute_seasonal_score(is_driving_season=True) > 60

    def test_generate_signal(self, mock_bedrock):
        svc = GlacierIntelligenceService(bedrock_client=mock_bedrock)
        sig = svc.generate_signal("WTI", utilization_pct=95, inventory_days=25, return_30d=12)
        assert sig.commodity_code == "WTI"
        assert sig.glacier_score > 0

    def test_generate_ai_analysis(self, mock_bedrock):
        svc = GlacierIntelligenceService(bedrock_client=mock_bedrock)
        sig = svc.generate_signal("WTI")
        analysis = svc.generate_ai_analysis(sig)
        assert "tightening" in analysis or len(analysis) > 10

    def test_set_services(self, mock_bedrock):
        svc = GlacierIntelligenceService(bedrock_client=mock_bedrock)
        svc.set_services(eia_svc=MagicMock())
        assert svc._eia_svc is not None
