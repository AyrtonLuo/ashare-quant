# Data Revision Specification (Phase 7)

## 1. Overview
Financial and market data continuously undergo revisions, restatements, earnings corrections, split adjustments, and provider backfills. In standard databases, updating a record in-place overwrites historical state, introducing look-ahead bias and destroying backtest reproducibility.

The Data Revision Layer (`src/data/revision/`) enforces the **Data Immutability Principle**:
$$\text{NEW DATA} \neq \text{DELETE/OVERWRITE OLD DATA} \implies \text{NEW REVISION} \rightarrow \text{NEW VERSION}$$

## 2. `DataRevision` Structure
```python
@dataclass(frozen=True)
class DataRevision:
    record_id: str
    symbol: str
    field: str                          # e.g., "close", "pe_ttm", "net_income"
    effective_date: str                 # Date described ("YYYY-MM-DD")
    value: Any                          # Observed value
    provider: str                       # e.g., "tushare_pro"
    available_at: datetime              # Timestamp when legally visible
    received_at: datetime               # Timestamp when payload arrived
    revision_id: str                    # Sequence/version e.g., "rev_001"
    dataset_version: str                # Dataset version e.g., "ds_v1.0"
    is_current: bool = True             # Latest version at present real-time
    supersedes_revision_id: Optional[str] = None
    provenance: MetricProvenance = MetricProvenance.PROVIDER_REPORTED
    quality_status: str = "VALID"
```

## 3. Point-in-Time Revision Query Semantics
For any query `query_pit(symbol, field, effective_date, as_of = T)`:
1. Filter all revisions for `(symbol, field, effective_date)` where $\text{available\_at} \le T$.
2. If no revision satisfies $\text{available\_at} \le T$, return `None` or `UNAVAILABLE`.
3. If multiple revisions satisfy $\text{available\_at} \le T$, select the revision with the latest $\text{available\_at}$ (or highest `revision_id`).

## 4. Provenance & Audit Trail
`RevisionStore.get_revision_history(symbol, field, effective_date)` returns the full chronological sequence of revisions, allowing quantitative researchers to audit exactly when restatements occurred and how metric values evolved over time.
