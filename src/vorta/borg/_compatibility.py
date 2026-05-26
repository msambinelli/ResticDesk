from packaging.version import Version

MIN_BORG_FOR_FEATURE = {
    "BLAKE2": Version("0.12.0"),
    "ZSTD": Version("0.16.0"),
    "JSON_LOG": Version("0.9.0"),
    "DIFF_JSON_LINES": Version("0.13.0"),
    "COMPACT_SUBCOMMAND": Version("99.0.0"),
    "V122": Version("0.12.0"),
    "V2": Version("0.12.0"),
    'CHANGE_PASSPHRASE': Version('0.9.0'),
    # add new version-checks here.
}


class BorgCompatibility:
    """
    An internal class that keeps details of the Borg version
    in use and allows checking for specific features. Could be used
    to customize Borg commands by version in the future.
    """

    version = "0.16.0"
    path = ""

    def set_version(self, version, path):
        self.version = version
        self.path = path

    def check(self, feature_name):
        return Version(self.version) >= MIN_BORG_FOR_FEATURE[feature_name]

    def get_version(self):
        """Returns the version and path of the restic binary."""
        return self.version, self.path


class ResticCompatibility(BorgCompatibility):
    """Preferred compatibility wrapper name for the Restic backend."""
