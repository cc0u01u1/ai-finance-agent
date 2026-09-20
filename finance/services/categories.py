from typing import Optional
from finance.models.enums import TransactionCategory

# Chinese display labels for categories
CATEGORY_LABELS = {
    'food': '餐饮美食',
    'transport': '交通出行',
    'entertainment': '休闲娱乐',
    'utilities': '居家缴费',
    'healthcare': '医疗健康',
    'shopping': '购物消费',
    'education': '学习教育',
    'income': '收入',
    'other': '其他',
}


def category_label(category: Optional[str]) -> str:
    if not category:
        return CATEGORY_LABELS['other']
    return CATEGORY_LABELS.get(category.lower(), category)


class CategoryService:
    @staticmethod
    def map_to_category(text: str) -> TransactionCategory:
        """
        Professional mapping of natural language to financial categories.
        """
        text = text.lower()
        
        # Mapping clusters
        mappings = {
            'food': ['lunch', 'dinner', 'breakfast', 'restaurant', 'cafe', 'grocery', 'food', 'starbucks', 'mcdonalds'],
            'transport': ['uber', 'taxi', 'fuel', 'gas', 'metro', 'bus', 'train', 'parking', 'flight'],
            'entertainment': ['movie', 'cinema', 'game', 'netflix', 'spotify', 'concert', 'bar', 'club'],
            'utilities': ['rent', 'electricity', 'water', 'gas', 'internet', 'phone', 'bill'],
            'healthcare': ['doctor', 'medicine', 'pharmacy', 'hospital', 'dentist', 'clinic'],
            'shopping': ['shopping', 'amazon', 'clothes', 'shoes', 'electronics', 'gift'],
            'education': ['course', 'book', 'tuition', 'school', 'workshop'],
        }

        for category, keywords in mappings.items():
            if any(kw in text for kw in keywords):
                return TransactionCategory(category)
        
        return TransactionCategory.OTHER
