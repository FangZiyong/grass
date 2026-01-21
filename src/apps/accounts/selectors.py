"""
Accounts 查询层（只读操作）
"""
from typing import Optional

from apps.accounts.models.users import GlobalUser


def get_user_by_id(user_id: int) -> Optional[GlobalUser]:
    """
    根据用户 ID 获取 GlobalUser。
    """
    try:
        return GlobalUser.objects.get(user_id=user_id)
    except GlobalUser.DoesNotExist:
        return None
