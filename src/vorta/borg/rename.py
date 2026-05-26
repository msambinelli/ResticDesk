from vorta.store.models import ArchiveModel, RepoModel
from vorta.i18n import trans_late

from .borg_job import BorgJob


class BorgRenameJob(BorgJob):
    def started_event(self):
        self.app.backup_started_event.emit()
        self.app.backup_progress_event.emit(f"[{self.params['profile_name']}] {self.tr('Renaming archive…')}")

    def log_event(self, msg):
        self.app.backup_log_event.emit(msg)

    @classmethod
    def prepare(cls, profile, old_archive_name, new_archive_name):
        ret = super().prepare(profile)
        if not ret['ok']:
            return ret
        else:
            ret['ok'] = False  # Set back to false, so we can do our own checks here.

        ret['old_archive_name'] = old_archive_name
        ret['new_archive_name'] = new_archive_name
        ret['repo_url'] = profile.repo.url
        ret['message'] = trans_late(
            'messages',
            'Renaming snapshots is not supported by Restic. Use tags for labeling snapshots.',
        )
        ret['ok'] = False

        return ret

    def process_result(self, result):
        if result['returncode'] == 0:
            repo = RepoModel.get(url=result['params']['repo_url'])
            renamed_archive = ArchiveModel.get(name=result['params']['old_archive_name'], repo=repo)
            renamed_archive.name = result['params']['new_archive_name']
            renamed_archive.save()

            self.app.backup_progress_event.emit(f"[{self.params['profile_name']}] {self.tr('Archive renamed.')}")
