"""
update_market_data.py
独立盘前/盘后数据自动增量更新与 Data Quality 校验任务 (不依赖 Streamlit UI)
"""

import sys
import os
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.data.akshare_provider import AkShareProvider
from src.data.cache import LocalCache
from src.data.quality.checker import DataQualityChecker
from src.runs.run_manager import RunManager


def main():
    rm = RunManager()
    run_id = f"job_update_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}"
    rec = rm.start_run(run_id=run_id, run_type="Daily Update")

    try:
        cache = LocalCache()
        provider = AkShareProvider(cache=cache, use_cache=True)
        symbols = ["600519", "000001", "600690"]
        for sym in symbols:
            df = provider.get_history(sym, force_refresh=False)
            report = DataQualityChecker.check_dataframe(sym, df)
            print(f"[{sym}] Data Quality Status: {report.status}")

        rm.complete_run(rec, status="SUCCESS")
        print("✅ Daily Market Data Update Completed Successfully.")
    except Exception as e:
        rm.complete_run(rec, status="FAILED", error=str(e))
        print(f"❌ Daily Market Data Update Failed: {e}")


if __name__ == "__main__":
    main()
