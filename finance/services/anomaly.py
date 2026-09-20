"""Rule-based anomaly detection for spending data."""
import statistics
from typing import List, Dict, Optional
from finance.models.transaction import Transaction
from finance.models.anomaly import Anomaly
from finance.services.categories import category_label

# Tunable thresholds
ZSCORE_THRESHOLD = 2.5
ZSCORE_CRITICAL = 3.0
MIN_GLOBAL_SAMPLE = 5
MIN_CATEGORY_SAMPLE = 4
SPIKE_PCT_WARNING = 0.5
SPIKE_PCT_CRITICAL = 1.0
SPIKE_MIN_DELTA = 100.0


class AnomalyService:
    @staticmethod
    def _zscores(amounts: List[float]) -> Optional[tuple]:
        if len(amounts) < 2:
            return None
        std = statistics.stdev(amounts)
        if std <= 0:
            return None
        return statistics.mean(amounts), std

    @classmethod
    def detect(
        cls,
        current_expenses: List[Transaction],
        previous_expenses: Optional[List[Transaction]] = None
    ) -> List[Anomaly]:
        """Detect anomalies in the current period.

        Rules:
        1. Global z-score outlier among current-period expenses.
        2. Per-category z-score outlier using current + previous samples.
        3. Category total spike versus the previous period.
        """
        anomalies: List[Anomaly] = []
        flagged_ids = set()
        previous_expenses = previous_expenses or []

        # Rule 1: global outliers
        current_amounts = [t.amount for t in current_expenses]
        global_stats = (
            cls._zscores(current_amounts)
            if len(current_amounts) >= MIN_GLOBAL_SAMPLE else None
        )
        if global_stats:
            mean, std = global_stats
            for tx in current_expenses:
                z = (tx.amount - mean) / std
                if abs(z) >= ZSCORE_THRESHOLD:
                    cat = tx.category.value if tx.category else 'other'
                    flagged_ids.add(tx.id)
                    anomalies.append(Anomaly(
                        kind='large_transaction',
                        severity='critical' if abs(z) >= ZSCORE_CRITICAL else 'warning',
                        category=cat,
                        amount=tx.amount,
                        expected=round(mean, 2),
                        score=round(z, 2),
                        message=(
                            f"¥{tx.amount:,.2f}的{category_label(cat)}消费明显高于本周期常规水平"
                            f"（均值 ¥{mean:,.2f}，z={z:.1f}）"
                        )
                    ))

        # Rule 2: per-category outliers
        category_groups: Dict[str, List[float]] = {}
        current_by_category: Dict[str, List[Transaction]] = {}
        for tx in previous_expenses:
            cat = tx.category.value if tx.category else 'other'
            category_groups.setdefault(cat, []).append(tx.amount)
        for tx in current_expenses:
            cat = tx.category.value if tx.category else 'other'
            category_groups.setdefault(cat, []).append(tx.amount)
            current_by_category.setdefault(cat, []).append(tx)

        for cat, amounts in category_groups.items():
            if len(amounts) < MIN_CATEGORY_SAMPLE:
                continue
            stats = cls._zscores(amounts)
            if not stats:
                continue
            mean, std = stats
            for tx in current_by_category.get(cat, []):
                if tx.id in flagged_ids:
                    continue
                z = (tx.amount - mean) / std
                if abs(z) >= ZSCORE_THRESHOLD:
                    flagged_ids.add(tx.id)
                    anomalies.append(Anomaly(
                        kind='category_outlier',
                        severity='critical' if abs(z) >= ZSCORE_CRITICAL else 'warning',
                        category=cat,
                        amount=tx.amount,
                        expected=round(mean, 2),
                        score=round(z, 2),
                        message=(
                            f"一笔 ¥{tx.amount:,.2f}的{category_label(cat)}消费，超出该类别常规区间"
                            f"（均值 ¥{mean:,.2f}，z={z:.1f}）"
                        )
                    ))

        # Rule 3: category total spikes
        previous_totals: Dict[str, float] = {}
        for tx in previous_expenses:
            cat = tx.category.value if tx.category else 'other'
            previous_totals[cat] = previous_totals.get(cat, 0.0) + tx.amount

        current_totals: Dict[str, float] = {}
        for tx in current_expenses:
            cat = tx.category.value if tx.category else 'other'
            current_totals[cat] = current_totals.get(cat, 0.0) + tx.amount

        for cat, cur_total in current_totals.items():
            prev_total = previous_totals.get(cat, 0.0)
            if prev_total <= 0:
                continue
            change_pct = (cur_total - prev_total) / prev_total
            if change_pct >= SPIKE_PCT_WARNING and (cur_total - prev_total) >= SPIKE_MIN_DELTA:
                anomalies.append(Anomaly(
                    kind='category_spike',
                    severity='critical' if change_pct >= SPIKE_PCT_CRITICAL else 'warning',
                    category=cat,
                    amount=round(cur_total, 2),
                    expected=round(prev_total, 2),
                    score=round(change_pct, 2),
                    message=(
                        f"{category_label(cat)}本周期共花 ¥{cur_total:,.2f}，"
                        f"较上周期 ¥{prev_total:,.2f} 增加 {change_pct * 100:.0f}%"
                    )
                ))

        severity_rank = {'critical': 0, 'warning': 1, 'info': 2}
        anomalies.sort(key=lambda a: severity_rank.get(a.severity, 3))
        return anomalies

    @staticmethod
    def format_anomalies(anomalies: List[Anomaly], period_label: str) -> str:
        if not anomalies:
            return f"## 🔍 {period_label} 异常检测\n\n✅ 未发现明显异常消费。"

        icon = {'critical': '🔴', 'warning': '🟠', 'info': '🔵'}
        lines = [f"## 🔍 {period_label} 异常检测", "", f"共发现 **{len(anomalies)}** 个可疑信号：", ""]
        for item in anomalies:
            lines.append(f"{icon.get(item.severity, '🔵')} **{item.message}**")
        return "\n".join(lines)
