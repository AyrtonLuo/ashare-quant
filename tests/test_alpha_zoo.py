"""
test_alpha_zoo.py
Phase 16 Step 2: Alpha Zoo & AlphaRegistry 全量断言断言集成测试
涵盖注册表、看后偏差、PIT 校验、Canonical Symbol 强隔离、Golden Determinism 等 18 项核心测试。
"""

import pytest
import numpy as np
import pandas as pd
from src.factors.alpha_zoo import (
    AlphaDefinition,
    AlphaRegistry,
    AlphaFactorAdapter,
    validate_alpha,
    validate_no_lookahead,
    validate_pit_compliance,
    validate_symbol_integrity,
    AlphaValidationError
)


@pytest.fixture(autouse=True)
def reset_registry():
    """每次测试前重置并初始化 AlphaRegistry"""
    AlphaRegistry.clear()
    from src.factors.alpha_zoo.metadata import load_initial_alphas
    load_initial_alphas(AlphaRegistry)


def test_registry_initialization_and_listing():
    alphas = AlphaRegistry.list_all()
    assert len(alphas) >= 8
    alpha_ids = [a.alpha_id for a in alphas]
    assert "MOM_20D" in alpha_ids
    assert "REV_20D" in alpha_ids
    assert "VOL_20D" in alpha_ids
    assert "TURNOVER_20D" in alpha_ids
    assert "EP_TTM" in alpha_ids


def test_duplicate_registration_rejection():
    mom = AlphaRegistry.get("MOM_20D")
    with pytest.raises(AlphaValidationError, match="已在注册表中存在"):
        AlphaRegistry.register(mom)


def test_unknown_alpha_rejection():
    with pytest.raises(KeyError, match="未找到 ID 为"):
        AlphaRegistry.get("NON_EXISTENT_ALPHA")


def test_alpha_metadata_completeness():
    for alpha in AlphaRegistry.list_all():
        assert alpha.alpha_id is not None
        assert alpha.name is not None
        assert alpha.category is not None
        assert alpha.license is not None
        assert alpha.attribution is not None
        assert isinstance(alpha.lookahead_safe, bool)


def test_momentum_calculation():
    df = pd.DataFrame({"close": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]})
    res = AlphaRegistry.compute("MOM_5D", df)
    assert pd.isna(res.iloc[4])
    assert res.iloc[5] == pytest.approx(0.5)  # (15 - 10) / 10


def test_reversal_calculation():
    df = pd.DataFrame({"close": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]})
    res = AlphaRegistry.compute("REV_5D", df)
    assert res.iloc[5] == pytest.approx(-0.5)


def test_volatility_calculation():
    df = pd.DataFrame({"close": np.linspace(10, 20, 25)})
    res = AlphaRegistry.compute("VOL_20D", df)
    assert len(res) == 25
    assert not pd.isna(res.iloc[24])


def test_liquidity_calculation():
    df = pd.DataFrame({"amount": [100.0] * 20})
    res = AlphaRegistry.compute("TURNOVER_20D", df)
    assert res.iloc[19] == pytest.approx(100.0)


def test_lookahead_validation_pass():
    alpha = AlphaRegistry.get("MOM_5D")
    dates = pd.date_range("2025-01-01", periods=30, freq="B")
    sample_df = pd.DataFrame({
        "timestamp": np.repeat(dates, 2),
        "symbol": ["600519.SH", "000001.SZ"] * 30,
        "close": np.random.uniform(10, 20, 60)
    })
    assert validate_no_lookahead(alpha, sample_df) is True


def test_future_price_contamination_rejection():
    # 构建包含未来价格注入函数的受污染 Alpha
    def contaminated_compute(df: pd.DataFrame) -> pd.Series:
        # 使用全全切片未来均值，触发 Lookahead 错误
        fut_mean = df["close"].iloc[-1]
        return df["close"] / fut_mean

    bad_def = AlphaDefinition(
        alpha_id="BAD_LOOKAHEAD_ALPHA",
        name="Bad Lookahead Alpha",
        category="Test",
        description="Test",
        formula="close / future_close",
        required_fields=["close"],
        warmup_period=5,
        source="Test",
        license="MIT",
        attribution="Test",
        compute_fn=contaminated_compute
    )

    dates = pd.date_range("2025-01-01", periods=40, freq="B")
    sample_df = pd.DataFrame({
        "timestamp": dates,
        "symbol": ["600519.SH"] * 40,
        "close": np.random.uniform(10, 20, 40)
    })

    with pytest.raises(AlphaValidationError, match="看后偏差"):
        validate_no_lookahead(bad_def, sample_df)


def test_canonical_symbol_enforcement():
    valid_symbols = ["000001.SH", "000001.SZ", "600519.SH", "300750.SZ"]
    assert validate_symbol_integrity(valid_symbols) is True

    with pytest.raises(AlphaValidationError, match="拒绝裸代码"):
        validate_symbol_integrity(["000001"])


def test_shanghai_index_and_ping_an_bank_separation():
    from src.data.symbol_utils import normalize_ashare_code
    sh_info = normalize_ashare_code("000001.SH")
    sz_info = normalize_ashare_code("000001.SZ")
    assert sh_info["name"] == "上证指数"
    assert sz_info["name"] == "平安银行"


def test_pit_compliance():
    value_alpha = AlphaRegistry.get("EP_TTM")
    assert validate_pit_compliance(value_alpha) is True

    bad_pit_alpha = AlphaDefinition(
        alpha_id="BAD_PIT_VALUE",
        name="Bad PIT Value",
        category="Value",
        description="Missing publication date",
        formula="eps / close",
        required_fields=["eps"],  # 缺少 publication_date
        warmup_period=1,
        source="Test",
        license="MIT",
        attribution="Test",
        requires_fundamental=True
    )
    with pytest.raises(AlphaValidationError, match="publication_date"):
        validate_pit_compliance(bad_pit_alpha)


def test_golden_deterministic_reproducibility():
    """Golden Deterministic Test: Run #1 == Run #2"""
    np.random.seed(42)
    df = pd.DataFrame({
        "close": np.random.uniform(100, 200, 50)
    })

    run1 = AlphaRegistry.compute("MOM_20D", df)
    run2 = AlphaRegistry.compute("MOM_20D", df)

    pd.testing.assert_series_equal(run1, run2)


def test_alpha_factor_adapter_pipeline():
    df = pd.DataFrame({
        "close": np.linspace(10, 30, 30)
    })
    res_df = AlphaFactorAdapter.process_alpha_pipeline("MOM_5D", df, winsorize=True, zscore=True)
    assert "MOM_5D" in res_df.columns
    assert "raw_MOM_5D" in res_df.columns
    assert res_df["MOM_5D"].std() == pytest.approx(1.0, abs=1e-2)
