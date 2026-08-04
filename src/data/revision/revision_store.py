"""
revision_store.py — Immutable Point-in-Time Revision Store & Audit Engine with Snapshot Isolation.
"""

from datetime import datetime
from typing import List, Dict, Tuple, Optional
from src.data.revision.revision_model import DataRevision


class RevisionStore:
    """
    Stores and queries data revisions adhering strictly to Point-in-Time (PIT) semantics.
    Enforces the rule: NEW DATA != DELETE OLD DATA -> NEW REVISION -> NEW VERSION.
    Guarantees snapshot isolation by enforcing available_at <= as_of AND received_at <= as_of.
    """

    def __init__(self):
        # Key: (symbol, field, effective_date) -> List of DataRevision sorted by available_at
        self._store: Dict[Tuple[str, str, str], List[DataRevision]] = {}

    def add_revision(self, revision: DataRevision) -> str:
        """
        Adds a new revision for a data point. Updates previous latest revision's is_current status.
        """
        key = (revision.symbol, revision.field, revision.effective_date)
        if key not in self._store:
            self._store[key] = []
        
        existing_revisions = self._store[key]
        superseded_id = None
        if existing_revisions:
            latest_existing = existing_revisions[-1]
            superseded_id = latest_existing.revision_id
            
            updated_list = []
            for r in existing_revisions:
                if r.is_current:
                    r_updated = DataRevision(
                        record_id=r.record_id,
                        symbol=r.symbol,
                        field=r.field,
                        effective_date=r.effective_date,
                        value=r.value,
                        provider=r.provider,
                        available_at=r.available_at,
                        received_at=r.received_at,
                        revision_id=r.revision_id,
                        dataset_version=r.dataset_version,
                        is_current=False,
                        supersedes_revision_id=r.supersedes_revision_id,
                        provenance=r.provenance,
                        quality_status=r.quality_status,
                        provider_field=r.provider_field,
                        provider_timestamp=r.provider_timestamp,
                        as_of_limit=r.as_of_limit
                    )
                    updated_list.append(r_updated)
                else:
                    updated_list.append(r)
            existing_revisions = updated_list

        if revision.supersedes_revision_id is None and superseded_id is not None:
            revision = DataRevision(
                record_id=revision.record_id,
                symbol=revision.symbol,
                field=revision.field,
                effective_date=revision.effective_date,
                value=revision.value,
                provider=revision.provider,
                available_at=revision.available_at,
                received_at=revision.received_at,
                revision_id=revision.revision_id,
                dataset_version=revision.dataset_version,
                is_current=revision.is_current,
                supersedes_revision_id=superseded_id,
                provenance=revision.provenance,
                quality_status=revision.quality_status,
                provider_field=revision.provider_field,
                provider_timestamp=revision.provider_timestamp,
                as_of_limit=revision.as_of_limit
            )

        existing_revisions.append(revision)
        existing_revisions.sort(key=lambda r: (r.available_at, r.revision_id))
        self._store[key] = existing_revisions
        return revision.revision_id

    def query_pit(
        self,
        symbol: str,
        field: str,
        effective_date: str,
        as_of: datetime,
        received_before: Optional[datetime] = None,
        dataset_version: Optional[str] = None
    ) -> Optional[DataRevision]:
        """
        Queries the legally available revision of (symbol, field, effective_date) as of cutoff time `as_of`.
        Filters out any revision with available_at > as_of OR received_at > as_of.
        Filters out revisions with received_at > received_before for strict Snapshot Isolation.
        Returns the latest revision satisfying constraints.
        If no revision is available at as_of, returns None.
        """
        key = (symbol, field, effective_date)
        revisions = self._store.get(key, [])
        
        # Core PIT & System System Ingestion Filter
        valid_revisions = [
            r for r in revisions
            if r.available_at <= as_of and r.received_at <= as_of
        ]
        
        if received_before is not None:
            valid_revisions = [r for r in valid_revisions if r.received_at <= received_before]
        if dataset_version is not None:
            exact_version_revisions = [r for r in valid_revisions if r.dataset_version == dataset_version]
            if exact_version_revisions:
                valid_revisions = exact_version_revisions

        if not valid_revisions:
            return None
        return valid_revisions[-1]

    def query_pit_range(
        self,
        symbol: str,
        field: str,
        start_date: str,
        end_date: str,
        as_of: datetime,
        received_before: Optional[datetime] = None,
        dataset_version: Optional[str] = None
    ) -> List[DataRevision]:
        """
        Queries PIT revisions for symbol and field over an effective_date range [start_date, end_date].
        """
        results = []
        matching_keys = [
            k for k in self._store.keys()
            if k[0] == symbol and k[1] == field and start_date <= k[2] <= end_date
        ]
        matching_keys.sort(key=lambda k: k[2])
        for k in matching_keys:
            rev = self.query_pit(symbol, field, k[2], as_of, received_before=received_before, dataset_version=dataset_version)
            if rev is not None:
                results.append(rev)
        return results

    def get_revision_history(
        self, symbol: str, field: str, effective_date: str
    ) -> List[DataRevision]:
        """
        Returns full chronological history of all revisions for a data point.
        """
        key = (symbol, field, effective_date)
        return list(self._store.get(key, []))

    def clear(self):
        self._store.clear()
