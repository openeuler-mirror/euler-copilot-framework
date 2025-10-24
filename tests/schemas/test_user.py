"""UserInfo模型的单元测试"""

from apps.schemas.user import UserListItem


def test_user_info_creation() -> None:
    """测试UserInfo对象的创建"""
    # 测试默认值
    user = UserListItem()
    assert user.user_sub == ""
    assert user.user_name == ""

    # 测试指定值
    user = UserListItem(user_sub="sub123", user_name="test_user")  # pyright: ignore[reportCallIssue]
    assert user.user_sub == "sub123"
    assert user.user_name == "test_user"


def test_user_info_alias() -> None:
    """测试UserInfo的别名功能"""
    # 测试使用别名创建对象
    user = UserListItem(userSub="sub123", userName="test_user")
    assert user.user_sub == "sub123"
    assert user.user_name == "test_user"


def test_user_info_validation() -> None:
    """测试UserInfo的数据验证"""
    # 测试正常情况
    user = UserListItem(userSub="sub123", userName="test_user")
    assert user.user_sub == "sub123"
    assert user.user_name == "test_user"

    # 测试空字符串
    user = UserListItem(userSub="", userName="")
    assert user.user_sub == ""
    assert user.user_name == ""


def test_user_info_str_representation() -> None:
    """测试UserInfo的字符串表示"""
    user = UserListItem(userSub="sub123", userName="test_user")
    # 确保对象可以正确转换为字符串
    str_repr = str(user)
    assert "UserInfo" in str_repr
    assert "sub123" in str_repr
    assert "test_user" in str_repr

