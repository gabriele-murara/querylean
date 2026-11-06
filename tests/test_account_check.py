"""Tests of the write access of an account to the databases of a
connection."""

from querylean.database.privileges.account_check import AccountCheck
from querylean.database.privileges.account_privileges import AccountPrivileges
from querylean.database.privileges.grant_analyzer import GrantAnalyzer


class TestAccountCheck:
    """Writable, accepted and refused databases."""

    PRIVILEGES = GrantAnalyzer.analyze(
        [
            "GRANT SELECT ON *.* TO `u`@`%`",
            "GRANT INSERT, UPDATE ON `shop`.* TO `u`@`%`",
            "GRANT DELETE ON `crm`.`notes` TO `u`@`%`",
        ]
    )

    def test_writable_and_refused(self):
        check = AccountCheck(
            self.PRIVILEGES, ["app", "shop", "crm"], accepted=["shop"]
        )
        assert check.databases == ("app", "shop", "crm")
        assert check.write_databases == ("shop", "crm")
        assert check.refused == ("crm",)
        assert check.caution
        assert check.reason("shop") == "INSERT, UPDATE"
        assert check.reason("app") == ""
        assert check.describe() == "shop (INSERT, UPDATE); crm (DELETE)"
        assert check.describe(["crm"]) == "crm (DELETE)"

    def test_read_only_account(self):
        check = AccountCheck(AccountPrivileges(), ["app"])
        assert not check.caution and check.refused == ()

    def test_information_schema_is_never_writable(self):
        privileges = GrantAnalyzer.analyze(["GRANT ALL ON *.* TO `r`@`%`"])
        check = AccountCheck(privileges, ["information_schema", "mysql"])
        assert check.write_databases == ("mysql",)

    def test_unverified_account_writes_everywhere(self):
        check = AccountCheck(AccountPrivileges.unverified(), ["a", "b"])
        assert check.write_databases == ("a", "b")
        assert check.reason("a") == AccountPrivileges.UNVERIFIED

    def test_accepted_names_are_exact(self):
        check = AccountCheck(self.PRIVILEGES, ["shop"], accepted=["SHOP"])
        assert check.refused == ("shop",)
