# your_module/utils/gantt_utils.py
from datetime import datetime
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import pytz
utc = pytz.UTC

# ------------------------------------------------------------------
# 1. CLOSED_STATES – lấy từ project_task gốc (Community có sẵn)
# ------------------------------------------------------------------
try:
    from odoo.addons.project.models.project_task import CLOSED_STATES
except ImportError:
    # Odoo 15 trở xuống dùng tên khác
    CLOSED_STATES = ('1_done', '1_canceled', 'done', 'canceled')

# ------------------------------------------------------------------
# 2. string_to_datetime – copy từ resource/utils.py (Community không có)
# ------------------------------------------------------------------
def string_to_datetime(value):
    """ Convert a string to a datetime in UTC. """
    if not value:
        return False
    # Giả sử value luôn ở UTC hoặc naive
    if isinstance(value, str):
        if len(value) == 10:  # chỉ có ngày
            value += " 00:00:00"
        dt = datetime.strptime(value, DEFAULT_SERVER_DATETIME_FORMAT)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=None)  # naive → giữ nguyên
        return dt.astimezone(utc).replace(tzinfo=None)
    return value


# ------------------------------------------------------------------
# 3. Intervals + sum_intervals – copy từ resource/models/utils.py
# ------------------------------------------------------------------
from bisect import bisect_left, bisect_right
from datetime import timedelta

class Intervals:
    """ Tập hợp các khoảng thời gian không chồng lấn, được sắp xếp """
    def __init__(self, intervals=()):
        self._items = []
        for start, stop, data in sorted(intervals, key=lambda i: i[0]):
            if self._items and self._items[-1][1] >= start:
                self._items[-1] = (self._items[-1][0], max(self._items[-1][1], stop), self._items[-1][2])
            else:
                self._items.append((start, stop, data))

    def __and__(self, other):
        """ Giao của 2 Intervals """
        items = []
        i = j = 0
        while i < len(self._items) and j < len(other._items):
            s1, e1, d1 = self._items[i]
            s2, e2, d2 = other._items[j]
            start = max(s1, s2)
            end = min(e1, e2)
            if start < end:
                items.append((start, end, d1))
            if e1 < e2:
                i += 1
            else:
                j += 1
        return Intervals(items)

    def __or__(self, other):
        return Intervals(list(self._items) + list(other._items))

    def __sub__(self, other):
        """ Trừ: lấy phần không giao nhau """
        return self & ~other

    def __invert__(self):
        """ Phủ định – dùng trong trừ """
        return Intervals()

    def __bool__(self):
        return bool(self._items)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    @property
    def _items(self):
        return self.__dict__.setdefault('_items_cache', self._calculate_items())

    @_items.setter
    def _items(self, value):
        self.__dict__['_items_cache'] = value


def sum_intervals(intervals):
    """ Tổng số giờ (float) của các khoảng """
    return sum((stop - start).total_seconds() / 3600.0
               for start, stop, _ in intervals)


# ------------------------------------------------------------------
# 4. filter_domain_leaf – Community không có → tự viết đơn giản
# ------------------------------------------------------------------
def is_leaf(element):
    return isinstance(element, (tuple, list)) and len(element) == 3 and element[1] in expression.TERM_OPERATORS

def filter_domain_leaf(domain, filter_func):
    """
    Lọc các leaf của domain theo filter_func(field_name)
    Ví dụ: filter_domain_leaf(domain, lambda f: f not in ['planned_date_begin', 'date_deadline'])
    """
    if not domain:
        return []
    result = []
    for elem in domain:
        if is_leaf(elem) and not filter_func(elem[0]):
            continue
        if isinstance(elem, list) and elem:
            if elem[0] in ('&', '|', '!'):
                result.append(elem[0])
                result.extend(filter_domain_leaf(elem[1:], filter_func))
            else:
                result.append(elem)
        else:
            result.append(elem)
    # Đảm bảo luôn có & ở đầu nếu thiếu
    if result and result[0] not in ('&', '|', '!'):
        result.insert(0, '&')
    return result or expression.TRUE_DOMAIN