"""
split.py
时间序列数据切分器与 Walk-Forward 验证划分器 (TimeSeriesSplitter & WalkForwardSplitter)
严格保证无未来信息泄漏，禁止随机打乱 (random shuffle)。
"""

import pandas as pd
from typing import Tuple, List, Dict, Any


class TimeSeriesSplitter:
    @staticmethod
    def train_val_test_split(
        df_x: pd.DataFrame,
        df_y: pd.Series,
        train_end: str = "2023-12-31",
        val_end: str = "2024-12-31"
    ) -> Tuple[Tuple[pd.DataFrame, pd.Series], Tuple[pd.DataFrame, pd.Series], Tuple[pd.DataFrame, pd.Series]]:
        """
        按日期精确切分 Train / Validation / Test
        """
        if df_x.empty:
            return (df_x, df_y), (df_x, df_y), (df_x, df_y)

        dates = df_x.index.get_level_values('date')

        train_mask = dates <= train_end
        val_mask = (dates > train_end) & (dates <= val_end)
        test_mask = dates > val_end

        x_train, y_train = df_x[train_mask], df_y[train_mask]
        x_val, y_val = df_x[val_mask], df_y[val_mask]
        x_test, y_test = df_x[test_mask], df_y[test_mask]

        return (x_train, y_train), (x_val, y_val), (x_test, y_test)


class WalkForwardSplitter:
    @staticmethod
    def generate_folds(
        dates: List[str],
        train_window_years: int = 3,
        test_window_years: int = 1
    ) -> List[Dict[str, Any]]:
        """
        生成 Walk-Forward Validation 训练/测试时间窗口序列
        例如:
        Fold 1: Train 2020-2022, Test 2023
        Fold 2: Train 2020-2023, Test 2024
        Fold 3: Train 2020-2024, Test 2025
        """
        years = sorted(list(set([int(str(d)[:4]) for d in dates])))
        folds = []
        if len(years) < train_window_years + test_window_years:
            return folds

        for i in range(train_window_years, len(years)):
            train_end_yr = years[i - 1]
            test_yr = years[i]

            folds.append({
                "fold": len(folds) + 1,
                "train_start": f"{years[0]}-01-01",
                "train_end": f"{train_end_yr}-12-31",
                "test_start": f"{test_yr}-01-01",
                "test_end": f"{test_yr}-12-31"
            })
        return folds
