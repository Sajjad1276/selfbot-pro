from __future__ import annotations


def telegram_profile_view_tracking_available() -> bool:
    return False


def status_message() -> str:
    return "تلگرام اطلاعات بازدیدکنندگان پروفایل را از API عمومی در اختیار کلاینت قرار نمی‌دهد."
