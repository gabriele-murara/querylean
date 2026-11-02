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
