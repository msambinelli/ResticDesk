import logging
import os

from vorta.store.models import SettingsModel
from vorta.i18n import trans_late

from .borg_job import BorgJob

logger = logging.getLogger(__name__)


class BorgMountJob(BorgJob):
    def started_event(self):
        self.updated.emit(self.tr('Mounting archive into folder…'))

    @classmethod
    def prepare(cls, profile, archive: str = None):
        ret = super().prepare(profile)
        if not ret['ok']:
            return ret
        else:
            ret['ok'] = False  # Set back to false, so we can do our own checks here.

        if archive:
            ret['message'] = trans_late(
                'messages', 'Mounting a single archive is not supported by Restic. Mount the whole repository.'
            )
            return ret

        cmd = ['restic', 'mount']

        # Try to override existing permissions when mounting an archive. May help to read
        # files that come from a different system, like a restrictive NAS.
        override_mount_permissions = SettingsModel.get(key='override_mount_permissions').value
        if override_mount_permissions:
            cmd += ['-o', f"umask=0277,uid={os.getuid()}"]

        cmd.extend(["-r", profile.repo.url])

        if archive:
            ret['mounted_archive'] = archive

        ret['ok'] = True
        ret['cmd'] = cmd

        return ret
