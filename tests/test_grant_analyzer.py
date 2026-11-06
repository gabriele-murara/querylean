"""Tests of the fail-closed analysis of ``SHOW GRANTS`` output."""

import pytest

from querylean.database.privileges.grant_analyzer import GrantAnalyzer


class TestGrantAnalyzer:
    """MySQL and MariaDB grant lines, roles, column lists, grant option."""

    READ_ONLY = [
        ["GRANT USAGE ON *.* TO `ro`@`%`"],
        [
            "GRANT USAGE ON *.* TO `ro`@`%`",
            "GRANT SELECT ON `app`.* TO `ro`@`%`",
        ],
        ["GRANT SELECT, SHOW VIEW ON `app`.* TO 'ro'@'localhost'"],
        ["GRANT SELECT (`id`, `name`) ON `app`.`users` TO `ro`@`%`"],
        ["GRANT SHOW DATABASES ON *.* TO `ro`@`%`"],
        # MariaDB, with the password hash in the line.
        [
            "GRANT USAGE ON *.* TO `ro`@`%` IDENTIFIED BY PASSWORD '*AB12'",
            "GRANT SELECT ON `app`.* TO `ro`@`%`",
        ],
        # Names that contain keywords or separators.
        ["GRANT SELECT ON `on update, x`.* TO `ro`@`%`"],
        ["grant select on app.* to ro@'%'"],
        # A partial revoke only removes privileges.
        [
            "GRANT SELECT ON *.* TO `ro`@`%`",
            "REVOKE SELECT ON `mysql`.* FROM `ro`@`%`",
        ],
        ["", "  "],
    ]

    @pytest.mark.parametrize("lines", READ_ONLY)
    def test_read_only_accounts(self, lines):
        privileges = GrantAnalyzer.analyze(lines)
        assert privileges.read_only, privileges

    @pytest.mark.parametrize(
        ("lines", "expected"),
        [
            (
                ["GRANT SELECT, INSERT, UPDATE ON `app`.* TO `rw`@`%`"],
                ("INSERT", "UPDATE"),
            ),
            (
                ["GRANT ALL PRIVILEGES ON *.* TO `root`@`localhost`"],
                ("ALL PRIVILEGES",),
            ),
            (
                ["GRANT SELECT, UPDATE (`name`) ON `app`.`t` TO `rw`@`%`"],
                ("UPDATE",),
            ),
            (
                ["GRANT SELECT ON `app`.* TO `ro`@`%` WITH GRANT OPTION"],
                (GrantAnalyzer.GRANT_OPTION,),
            ),
            (
                ["GRANT EXECUTE ON `app`.* TO `ro`@`%`"],
                ("EXECUTE",),
            ),
            (
                ["GRANT PROXY ON ''@'' TO 'root'@'localhost'"],
                ("PROXY",),
            ),
            (
                ["GRANT BACKUP_ADMIN,XA_RECOVER_ADMIN ON *.* TO `a`@`%`"],
                ("BACKUP_ADMIN", "XA_RECOVER_ADMIN"),
            ),
            (
                [
                    "GRANT DELETE ON `a`.* TO `rw`@`%`",
                    "GRANT DELETE, DROP ON `b`.* TO `rw`@`%`",
                ],
                ("DELETE", "DROP"),
            ),
        ],
    )
    def test_write_privileges_are_reported(self, lines, expected):
        privileges = GrantAnalyzer.analyze(lines)
        assert not privileges.read_only
        assert privileges.verified
        assert privileges.write_privileges == expected

    @pytest.mark.parametrize(
        "lines",
        [
            # MySQL 8 and MariaDB roles: their privileges are not listed.
            ["GRANT `reader`@`%` TO `ro`@`%`"],
            ["GRANT `reader` TO `ro`@`%`"],
            ["SET DEFAULT ROLE `reader` FOR `ro`@`%`"],
            ["GRANT SELECT"],
            ["something unexpected"],
        ],
    )
    def test_unrecognised_lines_are_not_read_only(self, lines):
        privileges = GrantAnalyzer.analyze(
            ["GRANT USAGE ON *.* TO `ro`@`%`", *lines]
        )
        assert not privileges.verified
        assert not privileges.read_only

    @pytest.mark.parametrize(
        ("line", "database"),
        [
            ("GRANT INSERT ON *.* TO `u`@`%`", None),
            ("GRANT INSERT ON `app`.* TO `u`@`%`", "app"),
            ("GRANT INSERT ON `app`.`t` TO `u`@`%`", "app"),
            ("GRANT INSERT ON app.* TO u@'%'", "app"),
            ("GRANT INSERT ON `a``b`.* TO `u`@`%`", "a`b"),
            ("GRANT INSERT ON `on db`.* TO `u`@`%`", "on db"),
            ("GRANT EXECUTE ON PROCEDURE `app`.`p` TO `u`@`%`", "app"),
            ("GRANT EXECUTE ON FUNCTION `app`.`f` TO `u`@`%`", "app"),
            ("GRANT PROXY ON ''@'' TO 'root'@'localhost'", None),
            ("GRANT PROXY ON `x`@`%` TO `u`@`%`", None),
            ("GRANT INSERT ON `app\\_x`.* TO `u`@`%`", "app\\_x"),
        ],
    )
    def test_database_of_each_grant(self, line, database):
        privileges = GrantAnalyzer.analyze([line])
        assert [s.database for s in privileges.scopes] == [database]

    def test_privileges_by_database(self):
        privileges = GrantAnalyzer.analyze(
            [
                "GRANT SELECT, PROCESS ON *.* TO `u`@`%`",
                "GRANT INSERT ON `app`.* TO `u`@`%`",
                "GRANT SELECT ON `ro`.* TO `u`@`%` WITH GRANT OPTION",
                "GRANT SELECT ON `clean`.* TO `u`@`%`",
            ]
        )
        assert privileges.privileges_on("app") == ("PROCESS", "INSERT")
        assert privileges.privileges_on("ro") == (
            "PROCESS",
            GrantAnalyzer.GRANT_OPTION,
        )
        assert privileges.privileges_on("clean") == ("PROCESS",)
        assert privileges.writable("clean")

    def test_read_grants_do_not_make_a_database_writable(self):
        privileges = GrantAnalyzer.analyze(
            [
                "GRANT USAGE ON *.* TO `u`@`%`",
                "GRANT SELECT, SHOW VIEW ON `app`.* TO `u`@`%`",
                "GRANT INSERT ON `other`.* TO `u`@`%`",
            ]
        )
        assert not privileges.writable("app")
        assert privileges.writable("other")
        assert privileges.describe_database("other") == "INSERT"
