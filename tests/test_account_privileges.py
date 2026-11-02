"""Tests of the privilege check outcome."""

from querylean.database.privileges.account_privileges import AccountPrivileges


class TestAccountPrivileges:
    """Read-only only when verified and without write privileges."""

    def test_read_only(self):
        privileges = AccountPrivileges()
        assert privileges.read_only and privileges.describe() == ""

    def test_write_privileges_are_described(self):
        privileges = AccountPrivileges(("INSERT", "DELETE"))
        assert not privileges.read_only
        assert "INSERT, DELETE" in privileges.describe()

    def test_unverified_is_never_read_only(self):
        privileges = AccountPrivileges.unverified()
        assert not privileges.read_only and not privileges.verified
        assert "could not be verified" in privileges.describe()

    def test_value_equality(self):
        assert AccountPrivileges(("DROP",)) == AccountPrivileges(("DROP",))
        assert AccountPrivileges() != AccountPrivileges.unverified()
