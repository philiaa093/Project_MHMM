"""Small assertion helpers shared by the self-check suites."""


def rejected(operation, exception=ValueError):
    try:
        operation()
    except exception:
        return
    raise AssertionError("Đầu vào không hợp lệ đã được chấp nhận")
