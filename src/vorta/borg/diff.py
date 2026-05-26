from vorta.i18n import trans_late

from .borg_job import BorgJob


class BorgDiffJob(BorgJob):
    def started_event(self):
        self.app.backup_started_event.emit()
        self.app.backup_progress_event.emit(
            f"[{self.params['profile_name']}] {self.tr('Requesting differences between archives…')}"
        )

    def finished_event(self, result):
        self.app.backup_finished_event.emit(result)
        self.app.backup_progress_event.emit(
            f"[{self.params['profile_name']}] {self.tr('Obtained differences between archives.')}"
        )
        self.result.emit(result)

    @classmethod
    def prepare(cls, profile, archive_name_1, archive_name_2):
        ret = super().prepare(profile)
        if not ret['ok']:
            return ret

        ret['message'] = trans_late(
            'messages',
            'Archive diff in this UI is currently unavailable with Restic backend.',
        )
        ret['ok'] = False
        ret['archive_name_older'] = archive_name_1
        ret['archive_name_newer'] = archive_name_2

        return ret
